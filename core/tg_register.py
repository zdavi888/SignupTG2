import uiautomator2 as u2
import time
import random
import os
import threading
from api.hero_sms import HeroSMS

# 全局录制锁，保证所有并发模拟器有且只有1个能录制
GLOBAL_RECORD_LOCK = threading.Lock()
LAST_RECORD_END_TIME = 0.0

class TGRegisterAutomation:
    def __init__(self, manager, logger, api_key):
        self.manager = manager
        self.logger = logger
        self.sms = HeroSMS(api_key)

    def _check_stop(self):
        return getattr(self.manager, 'stop_flag', False)

    def _sleep(self, seconds):
        for _ in range(int(seconds * 2)):
            if self._check_stop(): return
            time.sleep(0.5)

    def _delay(self, min_s=2, max_s=4):
        delay = random.uniform(min_s, max_s)
        self._sleep(delay)
        
    def _random_name(self):
        first_names = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Oliver", "Isabella", "William", "Sophia", "Elijah"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez"]
        return random.choice(first_names), random.choice(last_names)

    def _async_cancel_order(self, order_id, purchase_time, index):
        def cancel_job():
            elapsed = time.time() - purchase_time
            if elapsed < 125:  # 等待稍微超过 2 分钟以确保平台允许取消
                wait_time = 125 - elapsed
                self.logger.info(f"[{index}] 号码尚未达到平台取消的2分钟限制，将在后台等待 {wait_time:.1f} 秒后抛弃号码", "TG注册")
                time.sleep(wait_time)
            for _ in range(3):
                try:
                    self.sms.set_status(order_id, 8)
                    self.logger.info(f"[{index}] 成功向接码平台发送取消号码请求 (订单ID: {order_id})", "TG注册")
                    break
                except Exception as e:
                    time.sleep(2)
        threading.Thread(target=cancel_job, daemon=True).start()

    def run(self, index, platform, country, max_price):
        self._current_phone = None
        self._received_code = False
        self._recording_process = None
        self._owns_record_lock = False
        self._final_res = False
        self._recording_file = f"/sdcard/tg_record_{index}.mp4"
        self._current_device_addr = f"127.0.0.1:{5555 + index * 2}"
        
        try:
            self._final_res = self._run_attempt(index, platform, country, max_price, 0)
        finally:
            self._handle_video(index)
        return self._final_res

    def _get_adb_path(self):
        import os
        adb_path = "adb"
        if hasattr(self.manager, 'console') and hasattr(self.manager.console, 'console_path'):
            base_dir = os.path.dirname(self.manager.console.console_path)
            candidate = os.path.join(base_dir, 'adb.exe')
            if os.path.exists(candidate):
                adb_path = candidate
        return adb_path

    def _get_ld_video_dir(self):
        import os
        from core.config import ConfigManager
        config = ConfigManager()
        ld_path = config.get_ld_path()
        if not ld_path:
            return ""
        ld_dir = os.path.dirname(ld_path)
        video_dir = os.path.join(ld_dir, "vms", "video")
        if not os.path.exists(video_dir):
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                documents = winreg.QueryValueEx(key, "Personal")[0]
                video_dir = os.path.join(documents, "XuanZhi", "Video")
                if not os.path.exists(video_dir):
                    os.makedirs(video_dir, exist_ok=True)
            except:
                os.makedirs(video_dir, exist_ok=True)
        return video_dir

    def _handle_video(self, index):
        res = self._final_res
        from record_video import bring_window_to_front_and_press_f8, close_ld_popups_by_pid
        
        if not getattr(self, '_owns_record_lock', False) or not getattr(self, '_instance_name', None):
            return

        self.logger.info(f"[{index}] 正在停止原生视频录制...", "TG注册")
        hwnd_used = bring_window_to_front_and_press_f8(self._instance_name, is_stop=True)
        
        if hwnd_used:
            close_ld_popups_by_pid(hwnd_used)
            
        global GLOBAL_RECORD_LOCK, LAST_RECORD_END_TIME
        LAST_RECORD_END_TIME = time.time()
        self._owns_record_lock = False
        GLOBAL_RECORD_LOCK.release()
            
        os.makedirs("data/videos/success", exist_ok=True)
        os.makedirs("data/videos/needs_pwd", exist_ok=True)
        
        # 寻找新增的视频文件，等待最多10秒以便雷电把 tmp 结尾的文件转换完成
        target_video_file = None
        for wait_idx in range(10):
            after_files = set()
            if os.path.exists(self._video_dir):
                after_files = set(f for f in os.listdir(self._video_dir) if f.endswith(".mp4"))
                
            new_files_set = after_files - getattr(self, '_before_all_files', set())
            
            non_tmp_new = [f for f in new_files_set if not f.endswith("_tmp.mp4")]
            if non_tmp_new:
                target_video_file = sorted(non_tmp_new, key=lambda x: os.path.getmtime(os.path.join(self._video_dir, x)))[-1]
                break
            elif new_files_set:
                target_video_file = sorted(list(new_files_set), key=lambda x: os.path.getmtime(os.path.join(self._video_dir, x)))[-1]
                
            time.sleep(1)
            
        if not target_video_file:
            self.logger.warning(f"[{index}] 未能定位到产生的视频文件，跳过重命名保存。", "TG注册")
            if self._received_code or self._final_res is True:
                self.logger.warning(f"[{index}] 因出现特殊情况（且已接收到验证码）未能保存录像，为防数据丢失，强烈保留该模拟器窗口供人工核查！", "TG注册")
                self._final_res = "KEEP"
            return
            
        source_path = os.path.join(self._video_dir, target_video_file)

        if not getattr(self, '_current_phone', None):
            try:
                os.remove(source_path)
            except Exception as e:
                self.logger.warning(f"[{index}] 无法删除废弃的视频文件: {e}", "TG注册")
            return

        phone_str = str(self._current_phone).replace("+", "").strip()
        dest_path = None

        if res is True:
            dest_path = f"data/videos/success/{phone_str}.mp4"
            self.logger.info(f"[{index}] 完整的注册流程结束，保存视频到 {dest_path}", "TG注册")
        elif self._received_code:
            dest_path = f"data/videos/needs_pwd/{phone_str}.mp4"
            self.logger.info(f"[{index}] 该号码已接受到验证码，但未完全成功，已保存录制的视频，名称为：{phone_str}.mp4", "TG注册")
        else:
            self.logger.info(f"[{index}] 未获取验证码或前期失败，删除本地截取的录制视频", "TG注册")
            try:
                os.remove(source_path)
            except: pass
            return
            
        if dest_path:
            import shutil
            # 使用循环重试机制移动文件，以防文件句柄未立刻释放
            saved_success = False
            for _ in range(5):
                try:
                    shutil.move(source_path, dest_path)
                    saved_success = True
                    break
                except Exception as e:
                    time.sleep(1.5)
            if not saved_success:
                self.logger.error(f"[{index}] 保存录制视频文件到目录失败!", "TG注册")
                if self._received_code or self._final_res is True:
                    self.logger.warning(f"[{index}] 视频保存失败，强制保留该模拟器窗口供人工核查！", "TG注册")
                    self._final_res = "KEEP"

    def _run_attempt(self, index, platform, country, max_price, attempt_num):
        self.logger.info(f"[{index}] 开始 Telegram 自动注册流程...", "TG注册")
        port = 5555 + index * 2
        device_addr = f"127.0.0.1:{port}"
        
        try:
            d = u2.connect(device_addr)
            d.implicitly_wait(8.0)
        except Exception as e:
            self.logger.error(f"[{index}] 无法连接U2: {e}", "TG注册")
            return False

        if self._check_stop(): return False

        # Launch App
        self.logger.info(f"[{index}] 尝试从桌面或系统启动 Telegram...", "TG注册")
        try:
            d.press("home")
            self._sleep(2)
            if d(text="Telegram").exists:
                d(text="Telegram").click()
                self._sleep(5)
            else:
                try:
                    self.manager.console.runapp(index, "org.telegram.messenger")
                except:
                    d.app_start("org.telegram.messenger")
                self._sleep(5)
        except Exception as e:
            self.logger.warning(f"[{index}] 启动TG遇到异常: {e}", "TG注册")
            
        self._sleep(5)

        if self._check_stop(): return False
        self.logger.info(f"[{index}] 正在导航至手机号输入界面...", "TG注册")
        
        # 循环点击直到出现输入框
        reached_input = False
        for _ in range(25):
            if self._check_stop(): return False
            
            try:
                if len(d(className="android.widget.EditText")) >= 1:
                    reached_input = True
                    break
                    
                if d(textContains="Start Messaging").exists:
                    d(textContains="Start Messaging")[-1].click()
                elif d(textContains="开始").exists:
                    d(textContains="开始")[-1].click()
                elif d(textContains="使用").exists:
                    d(textContains="使用")[-1].click()
                elif d(textContains="Continue").exists:
                    d(textContains="Continue")[-1].click()
                elif d(textContains="继续").exists:
                    d(textContains="继续")[-1].click()
                elif d(textContains="Allow").exists:
                    d(textContains="Allow")[-1].click()
                elif d(textContains="允许").exists:
                    d(textContains="允许")[-1].click()
                elif d(textContains="OK").exists:
                    d(textContains="OK")[-1].click()
                elif d(textContains="确定").exists:
                    d(textContains="确定")[-1].click()
                elif d(textContains="同意").exists:
                    d(textContains="同意")[-1].click()
                elif d(textContains="Agree").exists:
                    d(textContains="Agree")[-1].click()
            except Exception as e:
                self.logger.warning(f"[{index}] 导航时界面刷新或断开: {e}", "TG注册")
                
            self._sleep(2)
            
        if not reached_input:
            self.logger.error(f"[{index}] 无法到达手机号输入界面", "TG注册")
            return False

        if self._check_stop(): return False
        
        # 获取模拟器名称用于置顶窗口
        instance_name = None
        try:
            instances = self.manager.console.list2()
            instance = next((inst for inst in instances if inst['index'] == index), None)
            if instance:
                instance_name = instance['name']
        except: pass
        if not instance_name:
            instance_name = f"TG_{index}" # 默认备用名称
            
        self._instance_name = instance_name
        
        self.logger.info(f"[{index}] 正在等待全局录制锁（同时只能有一个窗口录制）...", "TG注册")
        global GLOBAL_RECORD_LOCK, LAST_RECORD_END_TIME
        GLOBAL_RECORD_LOCK.acquire()
        self._owns_record_lock = True
        
        # 检查是否需要等待 10-30 秒
        now = time.time()
        if LAST_RECORD_END_TIME > 0:
            elapsed = now - LAST_RECORD_END_TIME
            wait_time = random.uniform(10, 30)
            if elapsed < wait_time:
                sleep_s = wait_time - elapsed
                self.logger.info(f"[{index}] 上次录制刚结束，排队等待 {sleep_s:.1f} 秒...", "TG注册")
                self._sleep(sleep_s)
                
        if self._check_stop(): return False
        
        # 启动原生的录制视频
        self.logger.info(f"[{index}] 准备在模拟器中开启视频录制...", "TG注册")
        
        # 记录现存视频列表，用于结束时定位最新的录像文件
        self._video_dir = self._get_ld_video_dir()
        self._before_files = set()
        self._before_all_files = set()
        if os.path.exists(self._video_dir):
            self._before_files = set(f for f in os.listdir(self._video_dir) if f.endswith(".mp4") and not f.endswith("_tmp.mp4"))
            self._before_all_files = set(os.listdir(self._video_dir))
            
        from record_video import bring_window_to_front_and_press_f8
        hwnd_used = bring_window_to_front_and_press_f8(self._instance_name, is_stop=False)
        if hwnd_used:
            self.logger.info(f"[{index}] 视频录制已通过F8快捷键启动！", "TG注册")
        else:
            self.logger.warning(f"[{index}] 开启录制告警：未捕捉到有效窗口句柄，可能启动失败！", "TG注册")
            
        # 轮询探测真实的录制状态（临时文件产生，或者出现“录制已经启动”的警告提示框）
        self.logger.info(f"[{index}] 正在验证真实的录制状态，必须确保录制开启后才获取号码...", "TG注册")
        started_recording = False
        
        import ctypes
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        GetWindowText = user32.GetWindowTextW
        GetWindowTextLength = user32.GetWindowTextLengthW
        
        main_pid = ctypes.wintypes.DWORD()
        if hwnd_used:
            user32.GetWindowThreadProcessId(hwnd_used, ctypes.byref(main_pid))
            
        for i in range(60): # 最长等待 60 秒
            self._delay(1.0, 1.0)
            
            # 1. 检测是否产生了新的文件
            if os.path.exists(self._video_dir):
                current_all_files = set(os.listdir(self._video_dir))
                new_files = current_all_files - self._before_all_files
                if new_files:
                    started_recording = True
                    self.logger.info(f"[{index}] 检测到录制临时文件生成 {list(new_files)}，确认录制已启动！", "TG注册")
                    break
                    
            # 2. 检测由于已经录制中而弹出的“提示”窗口
            found_popup = False
            if hwnd_used:
                def foreach_window(hwnd, lParam):
                    nonlocal found_popup
                    if user32.IsWindowVisible(hwnd) and hwnd != hwnd_used:
                        win_pid = ctypes.wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                        if win_pid.value == main_pid.value:
                            length = GetWindowTextLength(hwnd)
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                GetWindowText(hwnd, buff, length + 1)
                                if "提示" in buff.value:
                                    found_popup = hwnd
                                    return False
                    return True
                EnumWindows(EnumWindowsProc(foreach_window), 0)
                
                if found_popup:
                    self.logger.info(f"[{index}] 探测到雷电提示框(可能是[录制中])，录制已实质在进行中！", "TG注册")
                    # 关闭该提示窗
                    user32.PostMessageW(found_popup, 0x0010, 0, 0)
                    started_recording = True
                    break
                    
            if i % 5 == 0 and i > 0:
                self.logger.info(f"[{index}] 等待录制生效中({i}s)...", "TG注册")
                
        if not started_recording:
            # 经过长达 60 秒的等待，既没有新文件生成，也没有弹窗提示。
            # 这意味着 F8 非常有可能被漏掉，或者录制功能异常！
            self.logger.error(f"[{index}] 严重错误：长达60秒未检测到真实的录制状态(文件或提示框)，为防数据逃逸，严禁获取手机号！中止本轮注冊！", "TG注册")
            return False
        
        # 即使检测到了，为了防止雷电偶尔初始化卡顿导致前端画面未跟上，再额外稳妥等待 2 秒
        self._delay(2.0, 3.0)
        
        # 4. Request Phone Number
        self.logger.info(f"[{index}] 已到达输入界面，正在向接码平台请求手机号...", "TG注册")
        country_code = "0" if str(country).lower() == "any" else str(country)
        order_time = time.time()
        order_id, phone = self.sms.get_number(service=platform, country=country_code, max_price=max_price)
        
        if not order_id:
            self.logger.error(f"[{index}] 获取号码失败: {phone}", "TG注册")
            if "NO_NUMBERS" in str(phone).upper():
                return "NO_NUMBERS"
            return False
            
        self._current_phone = phone
        self.logger.info(f"[{index}] 成功获取号码: {phone}, 订单ID: {order_id}", "TG注册")
        
        # Input phone number. TG has country code and phone fields.
        # It's usually easier to tap the field, clear it, and type the whole thing (including + if necessary)
        # or type it using adb shell input text.
        # But U2 clearing is safer.
        editors = d(className="android.widget.EditText")
        if len(editors) >= 2:
            editors[1].click()
            self._sleep(1)
            d.send_keys(phone, clear=True)
        elif len(editors) == 1:
            editors[0].click()
            self._sleep(1)
            d.send_keys(phone, clear=True)
        else:
            d.send_keys(phone)
            
        for verify_attempt in range(2):
            if verify_attempt > 0:
                self.logger.info(f'[{index}] 出现不确定因素，尝试用原号码并使用重发验证码重试...', 'TG注册')
            self._delay()
            d.press("enter")

            # 尝试点击右下角下一步按钮
            try:
                d(className="android.widget.FrameLayout", clickable=True)[-1].click()
            except:
                d.click(0.9, 0.9) 

            self._delay()

            self.logger.info(f"[{index}] 正在确认手机号并等待验证码...", "TG注册")

            state = "unknown"
            wait_start = time.time()
            while time.time() - wait_start < 120:
                if self._check_stop(): return False

                try:
                    xml = d.dump_hierarchy()
                except Exception:
                    self._sleep(2)
                    continue

                if "This phone number is banned." in xml or ("Invalid phone number" in xml and "Please check the number and try again" in xml):
                    state = "banned"
                    break
                if "Check your Telegram messages" in xml and "on your other device" in xml:
                    state = "other_device"
                    break
                if ("Add Email" in xml and "valid email address" in xml) or ("Check Your Email" in xml and "sent to your email" in xml):
                    state = "email_lock"
                    break
                if ("Enter code" in xml and "sent an SMS with an activation code" in xml) or (d(textContains="Enter code").exists and d(textContains="sent an SMS with an activation code").exists):
                    state = "sms_sent"
                    break
                if "Please try again later" in xml or "Please enter your number" in xml:
                    state = "invalid_number"
                    break

                import re
                match = re.search(r'You can request an SMS in (\d+:\d+)', xml)
                if match:
                    time_str = match.group(1)
                    mins = int(time_str.split(':')[0])
                    if mins >= 57:
                        self.logger.info(f"[{index}] 检测到验证码倒计时过长({match.group(0)})，等待倒计时10-30秒后执行返回并重提交...", "TG注册")
                        self._delay(10, 30)

                        # 1. 点击左上角返回
                        if d(description="Go back").exists:
                            d(description="Go back").click()
                        elif d(description="Navigate up").exists:
                            d(description="Navigate up").click()
                        else:
                            d.press("back")
                        self._sleep(3)

                        # 2. 弹窗 Edit number 点击 Edit
                        if d(textContains="Edit").exists:
                            d(textContains="Edit")[-1].click()
                        self._sleep(3)

                        # 3. 点击重新提交的小蓝箭头
                        try:
                            d(className="android.widget.FrameLayout", clickable=True)[-1].click()
                        except:
                            d.click(0.9, 0.9)
                        self._sleep(3)

                        # 4. 点击弹窗 Yes
                        if d(textContains="Yes").exists:
                            d(textContains="Yes")[-1].click()
                        elif d(textContains="YES").exists:
                            d(textContains="YES")[-1].click()
                        self._sleep(4)

                        # 重置整体超时时间，以确保后续有足够时间接收短信
                        wait_start = time.time()
                        continue
                    else:
                        if getattr(self, 'last_logged_sms', '') != time_str:
                            self.logger.info(f"[{index}] 识别到倒计时提示: {match.group(0)}, 继续等待...", "TG注册")
                            self.last_logged_sms = time_str

                if d(text="Get the code via SMS").exists:
                    self.logger.info(f"[{index}] 出现 'Get the code via SMS'，点击以获取短信...", "TG注册")
                    d(text="Get the code via SMS")[-1].click()
                    self._sleep(2)
                    wait_start = time.time()
                    continue

                if "Didn't get the code" in xml:
                    self.logger.info(f"[{index}] 检测到 'Didn't get the code?'，执行返回并重新提交...", "TG注册")

                    # 1. 点击左上角返回
                    if d(description="Go back").exists:
                        d(description="Go back").click()
                    elif d(description="Navigate up").exists:
                        d(description="Navigate up").click()
                    else:
                        d.press("back")
                    self._sleep(3)

                    # 2. 弹窗 Edit number 点击 Edit
                    if d(textContains="Edit").exists:
                        d(textContains="Edit")[-1].click()
                    self._sleep(3)

                    # 3. 点击重新提交的小蓝箭头
                    try:
                        d(className="android.widget.FrameLayout", clickable=True)[-1].click()
                    except:
                        d.click(0.9, 0.9)
                    self._sleep(3)

                    # 4. 点击弹窗 Yes
                    if d(textContains="Yes").exists:
                        d(textContains="Yes")[-1].click()
                    elif d(textContains="YES").exists:
                        d(textContains="YES")[-1].click()
                    self._sleep(4)

                    wait_start = time.time()
                    continue

                # 处理各种弹窗
                handled = False
                # 恢复textContains，但取[-1]即界面的最下方按钮，以防点到包含同词的标题
                for text in ["Yes", "YES", "是的", "Continue", "CONTINUE", "继续", "Allow", "ALLOW", "允许"]:
                    elems = d(textContains=text)
                    if len(elems) > 0:
                        try:
                            elems[-1].click()
                            handled = True
                            break
                        except: pass

                if not handled:
                    self._sleep(2)
                else:
                    self._sleep(1)

            if state in ["banned", "email_lock", "invalid_number", "other_device"]:
                self.logger.error(f"[{index}] 号码不可用 ({state})，请联系客服发送视频保存证据申请退款，准备放弃并交由流水线彻底删除该模拟器", "TG注册")
                if state in ["banned", "email_lock", "other_device"]:
                    self._delay(10, 20)
                # Cancel order
                self._async_cancel_order(order_id, order_time, index)
                return False

            if state == "unknown":
                self.logger.warning(f"[{index}] 未知界面状态，放弃当前模拟器...", "TG注册")
                self._async_cancel_order(order_id, order_time, index)
                return False

            # Check if we got "Wait 60 minutes" (Step 9.1 etc.)
            # If it says "Call in 3:00" or similar, we just wait for SMS from platform anyway.

            code = None
            for i in range(60): # wait up to 2 minutes (60 * 2s) for SMS
                if self._check_stop(): return False
                status_res = self.sms.get_status(order_id)
                if isinstance(status_res, str) and status_res.startswith("STATUS_OK"):
                    code = status_res.split(":")[1]
                    break

                if i % 3 == 0:
                    xml = d.dump_hierarchy()
                    if "Return to entering the code" in xml or "Phone verification" in xml and "Return" in xml:
                        self.logger.warning(f"[{index}] 页面变为Phone verification，未收到验证码，取消订单并放弃当前模拟器...", "TG注册")
                        self._async_cancel_order(order_id, order_time, index)
                        return False

                # To handle step 9.6 "Get the code via SMS", we check UI periodically
                if i % 5 == 0:
                    if d(textContains="Get the code via SMS").exists:
                        self._delay(5, 20)
                        d(textContains="Get the code via SMS").click()
                self._sleep(2)

            if not code:
                self.logger.error(f"[{index}] 接码超时，取消订单并放弃当前模拟器", "TG注册")
                self._async_cancel_order(order_id, order_time, index)
                return False

            self._received_code = True
            self.logger.info(f"[{index}] 成功接收到验证码: {code}", "TG注册")


            # 9.8 Input code
            d.send_keys(code)
            self.logger.info(f"[{index}] 输入验证码，等待验证通过...", "TG注册")
            self._sleep(3) # Wait for initial typing to process
            last_type_time = time.time()

            verify_start = time.time()
            verified = False
            while time.time() - verify_start < 120:
                if self._check_stop(): return "KEEP"
                xml = d.dump_hierarchy()

                if "Profile info" in xml or "First name" in xml or d(textContains="First name").exists:
                    verified = True
                    break
                if "Terms of Service" in xml:
                    verified = True
                    break
                if "Your password" in xml and "Two-Step Verification enabled. Your account is protected with an additional password." in xml:
                    verified = True
                    break
                if d(textContains="Continue").exists and d(textContains="Not now").exists:
                    verified = True
                    break
                if "允许" in xml or "拒绝" in xml or "Allow" in xml or "Deny" in xml:
                    verified = True
                    break
                if (d(textMatches="(?i)chats").exists and d(textMatches="(?i)settings").exists) or "Welcome to Telegram" in xml:
                    verified = True
                    break

                if "Invalid code" in xml or "code is invalid" in xml:
                    self.logger.info(f"[{index}] 提示验证码无效，尝试重新输入验证码: {code}", "TG注册")
                    try:
                        if d(className="android.widget.EditText").exists:
                            ed = d(className="android.widget.EditText")[0]
                            ed.click()
                            self._sleep(1)
                            ed.set_text(code)
                    except: 
                        d.send_keys(code)
                    last_type_time = time.time()
                    self._sleep(3)
                    continue

                # Check if verification code might be cleared or returned to the input field
                if time.time() - last_type_time > 5:
                    try:
                        if d(className="android.widget.EditText").exists and d(textContains="Enter code").exists:
                            ed_text = d(className="android.widget.EditText").get_text()
                            if not ed_text or len(str(ed_text).strip()) == 0 or "_" in str(ed_text):
                                self.logger.info(f"[{index}] 发现验证码被清空或处于输入状态，先清空再重新输入验证码: {code}", "TG注册")
                                try:
                                    ed = d(className="android.widget.EditText")[0]
                                    ed.click()
                                    self._sleep(1)
                                    ed.set_text(code)
                                except Exception as e:
                                    d.send_keys(code)
                                last_type_time = time.time()
                                self._sleep(3)
                                continue
                    except:
                        pass

                self._sleep(2)

            if not verified:
                self.logger.warning(f"[{index}] 验证码输入后2分钟未验证通过，可能出现不确定因素，尝试返回并用现有号码重新提交!", "TG注册")
                for _ in range(5):
                    xml = d.dump_hierarchy()
                    if "Your phone number" in xml or "Country" in xml:
                        break
                    if d(description="Go back").exists: d(description="Go back").click()
                    elif d(description="Navigate up").exists: d(description="Navigate up").click()
                    else: d.press("back")
                    self._sleep(2)
                    if d(textContains="Yes").exists:
                        d(textContains="Yes").click()
                    elif d(textContains="YES").exists:
                        d(textContains="YES").click()
                    self._sleep(2)
                if verify_attempt == 0:
                    self.sms.set_status(order_id, 3)
                    continue
                else:
                    self.logger.error(f"[{index}] 连续两次注册未能成功，请人工联系客服处理，将保留当前模拟器不删除", "TG注册")
                    return "KEEP"

            # Subsequent steps
            success = False
            for step in range(30):
                if self._check_stop(): return "KEEP"
                xml = d.dump_hierarchy()

                if "Your password" in xml and "Two-Step Verification enabled. Your account is protected with an additional password." in xml:
                    self.logger.error(f"[{index}] 出现两步验证密码锁，停止后续步骤，将放弃并彻底删除该模拟器", "TG注册")
                    return False

                if "Terms of Service" in xml:
                    if d(textContains="Accept").exists: d(textContains="Accept")[-1].click()
                    elif d(textContains="Agree").exists: d(textContains="Agree")[-1].click()
                    self._sleep(2)
                    continue

                if "Profile info" in xml or "First name" in xml or d(textContains="First name").exists:
                    fn, ln = self._random_name()
                    if d(className="android.widget.EditText").exists:
                        eds = d(className="android.widget.EditText")
                        if len(eds) >= 1: eds[0].set_text(fn)
                        if len(eds) >= 2: eds[1].set_text(ln)
                        d.press("enter")
                        self._delay()
                        try: d(className="android.widget.FrameLayout", clickable=True)[-1].click()
                        except: d.click(0.9, 0.9)
                        self._sleep(3)
                    continue

                if d(textContains="needs access to your contacts").exists and d(textContains="Continue").exists:
                    d(textContains="Continue")[-1].click()
                    self._sleep(2)
                    continue

                if ("contacts" in xml.lower() or "通讯录" in xml or "联系人" in xml) and (d(textContains="拒绝").exists or d(textContains="Deny").exists):
                    if d(textContains="拒绝").exists: d(textContains="拒绝")[-1].click()
                    elif d(textContains="Deny").exists: d(textContains="Deny")[-1].click()
                    self._sleep(2)
                    continue

                if ("photos" in xml.lower() or "media" in xml.lower() or "文件" in xml or "照片" in xml) and (d(textContains="拒绝").exists or d(textContains="Deny").exists):
                    if d(textContains="拒绝").exists: d(textContains="拒绝")[-1].click()
                    elif d(textContains="Deny").exists: d(textContains="Deny")[-1].click()
                    self._sleep(2)
                    continue

                if d(textContains="拒绝").exists:
                    d(textContains="拒绝")[-1].click()
                    self._sleep(2)
                    continue
                if d(textExact="Deny").exists:
                    d(textExact="Deny")[-1].click()
                    self._sleep(2)
                    continue

                if "Choose your language" in xml or "Elige tu idioma" in xml:
                    if d(textContains="Otro").exists: d(textContains="Otro")[-1].click()
                    elif d(textContains="Other").exists: d(textContains="Other")[-1].click()
                    self._sleep(1)
                    if d(textContains="OK").exists: d(textContains="OK")[-1].click()
                    elif d(textContains="确定").exists: d(textContains="确定")[-1].click()
                    self._sleep(2)
                    continue

                if "Translate Messages" in xml or d(text="Language").exists:
                    if d(description="Go back").exists: d(description="Go back").click()
                    elif d(description="Navigate up").exists: d(description="Navigate up").click()
                    else: d.press("back")
                    self._sleep(2)
                    continue

                if "Welcome to Telegram" in xml or (d(textMatches="(?i)chats").exists and d(textMatches="(?i)settings").exists):
                    self.logger.info(f"[{index}] 🎉 成功抵达Telegram首页！注册流程圆满完成！", "TG注册")
                    success = True
                    break

                self._sleep(2)

            if success:
                return True

            self.logger.warning(f"[{index}] 似乎处于未知界面停滞，未识别到首页，标记为失败。", "TG注册")
            return "KEEP"
