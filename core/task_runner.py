import threading
import time
import random
import os
from core.v2ray import V2rayAutomation
from core.weiba import WeibaAutomation
from core.tg_register import TGRegisterAutomation
from core.pw_email_setup import PwEmailSetupManager

class TaskRunner(threading.Thread):
    def __init__(self, manager, logger, config):
        super().__init__()
        self.manager = manager
        self.logger = logger
        self.config = config
        self.is_running = False
        self.success_count = 0
        self.active_tasks = {}
        self.lock = threading.Lock()
        self.window_slots = [None] * 8
        self.stop_requested = False
        self.stop_new_tasks = False
        
        self.proxy_pools = {} # { file_path: [proxy_list] }
        self.api_names = []
        
        # Helper to normalize paths
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Load default API names
        api_preset_file = self.normalize_path(self.config.get('api_app_preset'))
        if api_preset_file and os.path.exists(api_preset_file):
            try:
                for enc in ['utf-8', 'gbk', 'utf-8-sig']:
                    try:
                        with open(api_preset_file, "r", encoding=enc) as f:
                            self.api_names = [line.strip() for line in f if line.strip()]
                        break
                    except UnicodeDecodeError:
                        continue
                self.logger.info(f"成功读取API预设名称数量: {len(self.api_names)}", "系统控制")
            except Exception as e:
                self.logger.error(f"读取API预设名称文件失败: {e}", "系统控制")

    def normalize_path(self, path):
        if not path: return None
        if not os.path.isabs(path):
            return os.path.join(self.root_dir, path)
        return path

    def get_proxy_by_country(self, country, index):
        """根据国家获取代理，并从文件中移除已使用的代理"""
        with self.lock:
            # 确定代理文件路径
            proxy_file = None
            if country and country != "any":
                # 严格在 data/代理/ 下查找
                country_proxy = os.path.join(self.root_dir, "data", "代理", f"{country}.txt")
                if os.path.exists(country_proxy):
                    proxy_file = country_proxy
                else:
                    self.logger.error(f"[{index}] 未找到国家专属代理文件: {country_proxy}。根据要求，流程终止。", "系统控制")
                    return None
            else:
                proxy_file = self.normalize_path(self.config.get('proxy_file', "data/代理文件.txt"))

            if not proxy_file or not os.path.exists(proxy_file):
                self.logger.error(f"[{index}] 代理文件不存在: {proxy_file}", "系统控制")
                return None

            # 加载或取缓存
            if proxy_file not in self.proxy_pools:
                try:
                    with open(proxy_file, "r", encoding="utf-8") as f:
                        self.proxy_pools[proxy_file] = [line.strip() for line in f if line.strip()]
                except Exception as e:
                    self.logger.error(f"[{index}] 读取代理文件 {proxy_file} 失败: {e}", "系统控制")
                    return None

            pool = self.proxy_pools[proxy_file]
            if not pool:
                self.logger.warning(f"[{index}] 代理文件已耗尽: {proxy_file}", "系统控制")
                return None

            proxy_str = pool.pop(0)
            
            # 回写文件：保持原有的移除逻辑
            try:
                # 记录已使用
                used_file = os.path.join(os.path.dirname(proxy_file), "used_proxies.txt")
                with open(used_file, "a", encoding="utf-8") as f:
                    f.write(f"{proxy_str} ({country})\n")
                
                # 写回原文件 (移除已使用的)
                with open(proxy_file, "w", encoding="utf-8") as f:
                    for p in pool:
                        f.write(p + "\n")
            except Exception as e:
                self.logger.warning(f"[{index}] 更新代理文件异常: {e}", "流水线")
            
            return proxy_str

    def run(self):
        self.is_running = True
        self.manager.stop_flag = False
        self.logger.info("总控任务已启动...", "系统控制")
        
        while self.is_running and not self.stop_requested and not self.stop_new_tasks:
            if self.success_count >= self.config['target_count']:
                self.logger.info("🎉 已达到目标注册数量，任务圆满完成！", "系统控制")
                break
                
            with self.lock:
                dead_indices = [idx for idx, t in self.active_tasks.items() if not t.is_alive()]
                for idx in dead_indices:
                    del self.active_tasks[idx]
                current_active = len(self.active_tasks)
            
            if current_active < self.config['concurrency']:
                try:
                    free_slots = self.config['concurrency'] - current_active
                    new_indices = self.manager.clone_instances(
                        from_index=self.config['source_index'], 
                        count=1, 
                        prefix="TG_", 
                        target_group="AutoTG"
                    )
                    
                    if new_indices:
                        self.minimize_multiplayer_window()
                        new_index = new_indices[0]
                        task_thread = threading.Thread(target=self.emulator_worker, args=(new_index,))
                        with self.lock:
                            self.active_tasks[new_index] = task_thread
                        task_thread.start()
                        
                        delay = random.randint(10, 30)
                        self.logger.info(f"等待 {delay} 秒后以错开下一个并发任务启动高峰...", "系统控制")
                        for _ in range(delay * 2):
                            if self.stop_requested: break
                            time.sleep(0.5)
                    else:
                        self.logger.error("克隆模拟器失败，等待10秒后重试...", "系统控制")
                        for _ in range(20):
                            if self.stop_requested: break
                            time.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"调度任务时发生异常: {e}", "系统控制")
                    for _ in range(10):
                        if self.stop_requested: break
                        time.sleep(0.5)
            else:
                for _ in range(4):
                    if self.stop_requested: break
                    time.sleep(0.5)
                
        self.logger.info("主循环结束，等待正在运行的任务自行终止...", "系统控制")
        self.is_running = False

    def stop(self):
        self.stop_requested = True
        self.manager.stop_flag = True
        self.logger.info("已发送停止信号，正在停止所有正在执行的任务...", "系统控制")

    def _sleep(self, seconds):
        for _ in range(int(seconds * 2)):
            if self.stop_requested: return
            time.sleep(0.5)

    def arrange_window(self, index):
        try:
            instances = self.manager.get_instances()
            inst = next((x for x in instances if x['index'] == index), None)
            if not inst: return False
            
            hwnd = int(inst.get('top_win_handle', 0))
            if hwnd == 0: return False
            
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            
            if not user32.IsWindowVisible(hwnd):
                return False

            slot_idx = -1
            with self.lock:
                for i in range(8):
                    if self.window_slots[i] == index:
                        slot_idx = i
                        break
                if slot_idx == -1:
                    for i in range(8):
                        if self.window_slots[i] is None:
                            self.window_slots[i] = index
                            slot_idx = i
                            break
                            
            if slot_idx != -1:
                screen_w = user32.GetSystemMetrics(0)
                
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ('left', wintypes.LONG),
                        ('top', wintypes.LONG),
                        ('right', wintypes.LONG),
                        ('bottom', wintypes.LONG),
                    ]
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                ww = rect.right - rect.left
                wh = rect.bottom - rect.top
                
                if ww <= 0: ww = 360
                if wh <= 0: wh = 640

                row = slot_idx // 4
                col = slot_idx % 4
                
                gap_x = 60
                gap_y = 15

                x = screen_w - (col + 1) * ww - (col + 1) * gap_x
                y = row * (wh + gap_y) + gap_y

                # SWP_NOZORDER = 0x0004, SWP_SHOWWINDOW = 0x0040
                user32.SetWindowPos(hwnd, 0, x, y, ww, wh, 0x0004 | 0x0040)
                return True
        except Exception as e:
            self.logger.warning(f"[{index}] 排列窗口位置失败: {e}", "系统控制")
        return False

    def free_window_slot(self, index):
        with self.lock:
            for i in range(8):
                if self.window_slots[i] == index:
                    self.window_slots[i] = None
                    break

    def minimize_multiplayer_window(self):
        def _minimize():
            try:
                import ctypes
                from ctypes import wintypes
                import time
                user32 = ctypes.windll.user32
                
                def foreach_window(hwnd, lParam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            if "雷电多开器" in buff.value:
                                user32.ShowWindow(hwnd, 6) # SW_MINIMIZE = 6
                    return True
                
                EnumWindows = user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                for _ in range(10): # try for 5 seconds
                    EnumWindows(EnumWindowsProc(foreach_window), 0)
                    time.sleep(0.5)
            except Exception:
                pass
                
        import threading
        threading.Thread(target=_minimize, daemon=True).start()

    def emulator_worker(self, index):
        try:
            self.logger.info(f"[{index}] ---- 开始执行单机流水线 ----", "流水线")
            
            # 1. Start Emulator
            self.manager.launch_instance(index)
            self.logger.info(f"[{index}] 等待模拟器启动 (30秒)...", "流水线")
            self.minimize_multiplayer_window()
            
            arranged = False
            for _ in range(60):
                if self.stop_requested: return
                if not arranged:
                    arranged = self.arrange_window(index)
                time.sleep(0.5)
                
            if self.stop_requested: return
            
            # 2. V2ray
            v2ray = V2rayAutomation(self.manager, self.logger)
            v2ray_success = False
            
            for attempt in range(3):
                if self.stop_requested: return
                
                # 动态获取对应国家的代理
                country = self.config.get('country') or self.config.get('sms_country', 'any')
                proxy_str = self.get_proxy_by_country(country, index)
                
                if not proxy_str:
                    self.logger.error(f"[{index}] 无法获取可用代理，任务终止", "流水线")
                    break
                
                success, msg = v2ray.configure_v2ray_for_instance(index, proxy_str=proxy_str) 
                if success:
                    v2ray_success = True
                    break
                else:
                    self.logger.warning(f"[{index}] V2ray配置代理失败此时重试, 原因: {msg}", "流水线")
                    if "context deadline exceeded" in str(msg):
                        self.logger.error(f"[{index}] V2ray测试遇到本地网络异常({msg})，终止后续尝试！", "流水线")
                        break
                    try:
                        self.manager.console.adb(index, f"shell am force-stop {v2ray.pkg}")
                        self._sleep(2)
                        if self.stop_requested: return
                        self.manager.console.adb(index, f"shell pm clear {v2ray.pkg}")
                        self._sleep(2)
                    except: pass

            if not v2ray_success:
                self.logger.error(f"[{index}] V2ray配置任务失败，放弃单机流水线并且删除模拟器...", "流水线")
                self.manager.remove_instance(index)
                self.minimize_multiplayer_window()
                return

            self._sleep(5)
            
            if self.stop_requested: return
            
            # 3. Weiba
            weiba = WeibaAutomation(self.manager, self.logger)
            res = weiba.execute_weiba_flow(index)
            self._sleep(5)
            
            if self.stop_requested: return
            
            # 4. TG Register
            tg = TGRegisterAutomation(self.manager, self.logger, self.config['api_key'])
            try:
                success = tg.run(
                    index, 
                    platform=self.config['service'], 
                    country=self.config['country'], 
                    max_price=self.config['max_price']
                )
            except Exception as e:
                self.logger.error(f"[{index}] 注册中发生崩溃: {e}", "流水线")
                success = False
                
            if self.stop_requested:
                self.logger.warning(f"[{index}] 任务人工中止，保持该模拟器现状不删除以供检查", "流水线")
                return
            
            if success == "NO_NUMBERS":
                self.logger.error(f"[{index}] 接码平台获取号码失败(可能价格过低或库存不足)。已触发全局限流，不再启动新模拟器，等待现有任务完成！", "系统控制")
                self.stop_new_tasks = True
                success = False
                
            if success == "KEEP":
                self.logger.error(f"[{index}] 流水线失败，由于已获取过验证码等关键进度，只停止不删除该模拟器以供人工接管", "流水线")
            elif success:
                with self.lock:
                    self.success_count += 1
                self.logger.info(f"[{index}] 注册成功！当前总成功数：{self.success_count}/{self.config['target_count']}", "流水线")
                
                try:
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    root_dir = os.path.dirname(current_dir)
                    
                    save_path = self.config.get('account_data_path')
                    if not save_path:
                        self.logger.warning(f"[{index}] 未配置'账号资料'存放路径，请在界面设置。账号信息将保存在默认路径中。", "系统配置")
                        save_path = os.path.join(root_dir, "data", "账号资料")
                        
                    if not os.path.isabs(save_path):
                        save_path = os.path.join(root_dir, save_path)
                        
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                        
                    phone_str = getattr(tg, '_current_phone', f"Unknown_{index}")
                    clean_phone = str(phone_str).strip()
                    if clean_phone and not clean_phone.startswith('+'):
                        clean_phone = '+' + clean_phone
                        
                    phone_folder = os.path.join(save_path, clean_phone)
                    if not os.path.exists(phone_folder):
                        os.makedirs(phone_folder)
                        
                    txt_path = os.path.join(phone_folder, f"{clean_phone}.txt")
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(f"手机号：{clean_phone}\n")
                        
                    self.logger.info(f"[{index}] 已成功将初始账号资料保存至: {txt_path}", "流水线")
                except Exception as e:
                    self.logger.error(f"[{index}] 保存初始账号资料时发生异常: {e}", "流水线")
                
                # Check if password setup and email binding is enabled
                if self.config.get('enable_password_setup'):
                    delay = random.uniform(10, 30)
                    self.logger.info(f"[{index}] 已开启设置密码并绑定邮箱，随机延时 {delay:.1f} 秒后执行...", "流水线")
                    self._sleep(delay)
                    
                    if not self.stop_requested:
                        # Fetch the registered phone number
                        phone_str = getattr(tg, '_current_phone', f"Unknown_{index}")
                        
                        pw_setup_manager = PwEmailSetupManager(self.logger, self.config, self.lock)
                        pw_success = pw_setup_manager.execute_setup(index, phone_str)
                        if not pw_success:
                            self.logger.error(f"[{index}] 设置密码失败，只停止该模拟器供人工核查，不进行删除", "流水线")
                            self.minimize_multiplayer_window()
                            return

                # 获取API流程
                if self.config.get('get_api'):
                    if not self.stop_requested:
                        from core.get_API_Hash import GetAPIHash
                        api_task = GetAPIHash(self.logger, self.config, self.lock)
                        
                        api_app_name = None
                        with self.lock:
                            if hasattr(self, 'api_names') and self.api_names:
                                api_app_name = self.api_names.pop(0)
                                try:
                                    import os
                                    preset_file = self.config.get('api_app_preset')
                                    if preset_file:
                                        preset_file = self.normalize_path(preset_file)
                                        if os.path.exists(preset_file):
                                            with open(preset_file, "w", encoding="utf-8") as f:
                                                for name in self.api_names:
                                                    f.write(name + "\n")
                                except Exception as e:
                                    self.logger.warning(f"[{index}] API名称写入原文件异常: {e}", "流水线")
                        
                        api_task.pre_fetched_app_name = api_app_name
                        
                        phone_str = getattr(tg, '_current_phone', f"Unknown_{index}")
                        api_success = api_task.run(index, phone_number=phone_str)
                        if not api_success:
                            self.logger.error(f"[{index}] 获取 API 失败，保留当前模拟器以供排查", "流水线")
                            self.minimize_multiplayer_window()
                            return
                            
                # 获取Session流程 (预留接口，用户如果要求可稍后添加)
                if self.config.get('get_session'):
                    # 暂未实现
                    pass
                
                # 到这里代表所有流程运行成功，或至少基本注册成功(如果没勾选其他功能)
                self.logger.info(f"[{index}] 完整流水线成功完成，开始重命名模拟器并进行备份打包...", "流水线")
                try:
                    # 1. 关机模拟器
                    self.manager.console.quit(index)
                    for _ in range(15):
                        instances = self.manager.console.list2()
                        inst = next((x for x in instances if x['index'] == index), None)
                        if inst is None or inst.get('android_status') == 0:
                            break
                        time.sleep(1)
                        
                    # 2. 修改备注名为手机号
                    phone_str = getattr(tg, '_current_phone', f"Unknown_{index}")
                    clean_phone = str(phone_str).strip()
                    if clean_phone and not clean_phone.startswith('+'):
                        clean_phone = '+' + clean_phone
                        
                    self.manager.console.rename(index, clean_phone)
                    self.logger.info(f"[{index}] 模拟器已重命名为: {clean_phone}", "流水线")
                    
                    # 3. 备份到对应的手机号文件夹
                    save_path = self.config.get('save_data_path')
                    if not save_path:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        save_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "data", "账号资料")
                    
                    if not os.path.isabs(save_path):
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        save_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), save_path)
                    target_folder = os.path.join(save_path, clean_phone)
                    if not os.path.exists(target_folder):
                        os.makedirs(target_folder)
                        
                    # 确保有一个带有该手机号的 txt 文件，并把手机号写入
                    txt_path = os.path.join(target_folder, f"{clean_phone}.txt")
                    if not os.path.exists(txt_path):
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(f"手机号：{clean_phone}\n")
                            
                    backup_file = os.path.join(target_folder, f"{clean_phone}.ldbk")
                    
                    self.logger.info(f"[{index}] 开始备份模拟器至 {backup_file} ...", "流水线")
                    self.manager.console.backup(index, backup_file)
                    self.logger.info(f"[{index}] 备份成功完成!", "流水线")
                    
                    # 4. 备份完成后，为清理环境可以选择从雷电多开中删除它(因为我们已经备份存档)，如果不删也可以留存。通常流水线为了防满会删。
                    # self.manager.remove_instance(index) 
                    # 暂时由上层来管理，这里直接最小化返回
                    self.minimize_multiplayer_window()
                except Exception as e:
                    self.logger.error(f"[{index}] 重命名和备份发生异常: {e}", "流水线")
                    
            else:
                self.logger.error(f"[{index}] 流水线失败，准备删除当前模拟器...", "流水线")
                self.manager.remove_instance(index)
                self.minimize_multiplayer_window()

        except Exception as e:
            self.logger.error(f"[{index}] 流水线执行异常: {e}", "流水线")
        finally:
            self.free_window_slot(index)