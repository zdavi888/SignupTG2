import time
import threading
import random
import os
import uiautomator2 as u2

# 全局剪贴板锁，防止多开时冲突
clipboard_lock = threading.Lock()

class V2rayAutomation:
    def __init__(self, manager, logger):
        self.manager = manager
        self.logger = logger
        self.pkg = "com.v2ray.ang"

    def parse_proxy(self, proxy_str):
        # 尝试解析各种格式的代理
        proxy_str = proxy_str.strip()
        protocol = "socks"
        
        if "://" in proxy_str:
            proto, rest = proxy_str.split("://", 1)
            protocol = proto.lower()
            if protocol == "socks5": protocol = "socks"
            proxy_str = rest

        if "@" in proxy_str:
            auth, addr = proxy_str.split("@", 1)
            if ":" in auth:
                user, pwd = auth.split(":", 1)
            else:
                user, pwd = auth, ""
            if ":" in addr:
                ip, port = addr.split(":", 1)
            else:
                ip, port = addr, ""
        else:
            parts = proxy_str.split(":")
            if len(parts) == 4:
                ip, port, user, pwd = parts
            elif len(parts) == 2:
                ip, port = parts
                user, pwd = "", ""
            else:
                ip = parts[0]
                port, user, pwd = "", "", ""

        return protocol, ip, port, user, pwd

    def _sleep(self, index, seconds):
        for _ in range(int(seconds * 2)):
            if self._check_stop(): return
            time.sleep(0.5)

    def _random_delay(self, index, min_s=10, max_s=30):
        delay = random.randint(min_s, max_s)
        self.logger.info(f"[{index}] 随机延时 {delay} 秒...", "V2ray")
        self._sleep(index, delay)

    def _check_stop(self):
        return getattr(self.manager, 'stop_flag', False)

    def _wait_for_device(self, index, device_addr, timeout=60):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._check_stop(): return False
            
            try:
                ret = self.manager.console.adb(index, "shell getprop sys.boot_completed").strip()
                if ret == "1":
                    return True
            except Exception:
                pass
                
            time.sleep(2)
        return False

    def configure_v2ray_for_instance(self, index, proxy_str=None):
        if self._check_stop(): return False, "已停止操作"
        
        console = self.manager.console
        port = 5555 + index * 2
        device_addr = f"127.0.0.1:{port}"
        
        self.logger.info(f"[{index}] 正在等待设备并连接adb: {device_addr}...", "V2ray")
        if not self._wait_for_device(index, device_addr):
            self.logger.error(f"[{index}] 设备未就绪致 ADB 无法连接: {device_addr}", "V2ray")
            return False, "ADB连接超时"
            
        if self._check_stop(): return False, "已停止操作"
        
        self.logger.info(f"[{index}] ADB连接成功，等待15秒让系统启动完全...", "V2ray")
        self._sleep(index, 15)
        if self._check_stop(): return False, "已停止操作"
        
        try:
            d = u2.connect(device_addr)
            d.implicitly_wait(10.0) 
        except Exception as e:
            self.logger.error(f"[{index}] uiautomator2 连接失败: {e}", "V2ray")
            return False, str(e)
            
        try:
            self.logger.info(f"[{index}] 开始配置 V2ray...", "V2ray")
            
            # 1. 启动 V2ray
            console.adb(index, f"shell am force-stop {self.pkg}")
            self._sleep(index, 2)
            console.runapp(index, self.pkg)
            self.logger.info(f"[{index}] 已启动 V2ray", "V2ray")
            
            # 等待进入主页
            if not d(textContains="未连接").wait(timeout=10) and not d(textContains="已连接").wait(timeout=5):
                self.logger.warning(f"[{index}] V2ray主页加载超时或未识别", "V2ray")
                
            if self._check_stop(): return False, "已停止操作"
            self._random_delay(index)
            
            self.logger.info(f"[{index}] 尝试展开添加菜单...", "V2ray")
            # 点击添加按钮 
            add_btn = d(description="添加配置")
            if not add_btn.wait(timeout=2):
                add_btn = d(description="Add")
            if not add_btn.exists:
                add_btn = d(resourceId="com.v2ray.ang:id/fab")
                
            if add_btn.exists:
                add_btn.click()
            else:
                self.logger.warning(f"[{index}] 未找到添加按钮，尝试坐标定位右上角...", "V2ray")
                d.click(0.9, 0.08)
                
            self._sleep(index, 2)
            if self._check_stop(): return False, "已停止操作"

            menu_opened = d(textContains="剪贴板").exists or d(textContains="SOCKS").exists or d(textContains="HTTP").exists
            
            if proxy_str and not menu_opened:
                self.logger.warning(f"[{index}] 没能展开添加菜单，放弃配置代理！", "V2ray")
                return False, "未能打开添加菜单"
                
            if proxy_str and menu_opened:
                if proxy_str.startswith("vmess://") or proxy_str.startswith("vless://") or proxy_str.startswith("ss://") or proxy_str.startswith("trojan://"):
                    self.logger.info(f"[{index}] 检测到URI格式代理，尝试从剪贴板导入...", "V2ray")
                    with clipboard_lock:
                        import tkinter as tk
                        r = tk.Tk()
                        r.withdraw()
                        r.clipboard_clear()
                        r.clipboard_append(proxy_str)
                        r.update()
                        r.destroy()
                        if d(textContains="从剪贴板导入").exists:
                            d(textContains="从剪贴板导入").click()
                        elif d(textContains="Import from Clipboard").exists:
                            d(textContains="Import from Clipboard").click()
                        self._sleep(index, 2)
                else:
                    protocol, ip, r_port, user, pwd = self.parse_proxy(proxy_str)
                    target_text = "SOCKS" if protocol == "socks" else "HTTP"
                    target_btn = d(textContains=f"添加 [{target_text}]")
                    if not target_btn.exists:
                        target_btn = d(textContains=f"Add [{target_text}]")
                        
                    if target_btn.exists:
                        target_btn.click()
                        self.logger.info(f"[{index}] 正在输入代理 {ip}:{r_port}...", "V2ray")
                        
                        if not d(textContains=target_text).wait(timeout=5) and not d(textContains="配置").exists:
                            self.logger.warning(f"[{index}] 未能进入代理配置页面，放弃添加！", "V2ray")
                        else:
                            self._sleep(index, 1.5)
                            if self._check_stop(): return False, "已停止操作"
                            
                            import string
                            alias = "proxy_" + "".join(random.choices(string.ascii_letters + string.digits, k=5))
                            
                            import xml.etree.ElementTree as ET
                            xml_str = d.dump_hierarchy()
                            root = ET.fromstring(xml_str)
                            nodes = list(root.iter('node'))
                            
                            def get_centerpos(bounds_str):
                                # "[0,126][1080,242]" -> centerx, centery
                                import re
                                match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                                if match:
                                    x1, y1, x2, y2 = map(int, match.groups())
                                    return (x1+x2)//2, (y1+y2)//2
                                return 0, 0
                                
                            label_centers = {}
                            edit_centers = []
                            for node in nodes:
                                cls = node.attrib.get('class', '')
                                bounds = node.attrib.get('bounds', '')
                                text = node.attrib.get('text', '').lower()
                                if cls == 'android.widget.TextView' and bounds:
                                    cx, cy = get_centerpos(bounds)
                                    label_centers[text] = (cx, cy)
                                elif cls == 'android.widget.EditText' and bounds:
                                    cx, cy = get_centerpos(bounds)
                                    edit_centers.append({'cx': cx, 'cy': cy, 'bounds': bounds})
                                    
                            def find_nearest_edit(label_keys):
                                best_y = -1
                                for k in label_keys:
                                    for t, (cx, cy) in label_centers.items():
                                        if k in t:
                                            if cy > best_y: best_y = cy
                                if best_y == -1: return None
                                # Find edit control with cy roughly similar or slightly below best_y
                                best_edit = None
                                best_dist = 9999
                                for edit in edit_centers:
                                    dist = edit['cy'] - best_y
                                    # It might be to the right (same cy) or below (cy > best_y)
                                    if -50 <= dist <= 300: 
                                        if abs(dist) < best_dist:
                                            best_dist = abs(dist)
                                            best_edit = edit
                                return best_edit
                                
                            targets = [
                                (["别名", "remarks"], alias),
                                (["地址", "address"], ip),
                                (["端口", "port"], str(r_port)),
                                (["用户", "user"], user),
                                (["密码", "pass"], pwd)
                            ]
                            
                            for keys, val in targets:
                                if val:
                                    edit = find_nearest_edit(keys)
                                    if not edit and ('密码' in keys or '用户' in keys):
                                        d.swipe_ext("up", scale=0.6)
                                        self._sleep(index, 1)
                                        xml_str = d.dump_hierarchy()
                                        root = ET.fromstring(xml_str)
                                        nodes = list(root.iter('node'))
                                        label_centers.clear()
                                        edit_centers.clear()
                                        for node in nodes:
                                            cls = node.attrib.get('class', '')
                                            bounds = node.attrib.get('bounds', '')
                                            text = node.attrib.get('text', '').lower()
                                            if cls == 'android.widget.TextView' and bounds:
                                                cx, cy = get_centerpos(bounds)
                                                label_centers[text] = (cx, cy)
                                            elif cls == 'android.widget.EditText' and bounds:
                                                cx, cy = get_centerpos(bounds)
                                                edit_centers.append({'cx': cx, 'cy': cy, 'bounds': bounds})
                                        edit = find_nearest_edit(keys)
                                        
                                    if edit:
                                        d.click(edit['cx'], edit['cy'])
                                        self._sleep(index, 0.5)
                                        # Use ADB text input to avoid IME issues
                                        d.send_keys(val, clear=True)
                                        self._sleep(index, 0.5)
                                        if self._check_stop(): return False, "已停止操作"
                                    else:
                                        self.logger.warning(f"[{index}] 找不到 {keys[0]} 对应的输入框", "V2ray")

                            self._sleep(index, 1)
                            if self._check_stop(): return False, "已停止操作"
                            
                            # 保存
                            self.logger.info(f"[{index}] 保存代理配置...", "V2ray")
                            save_btn = d(resourceId="com.v2ray.ang:id/custom_save")
                            if not save_btn.exists:
                                save_btn = d(description="保存")
                            if not save_btn.exists:
                                save_btn = d(description="Save")
                                
                            if save_btn.exists:
                                save_btn.click()
                            else:
                                d.click(0.9, 0.08) 
                                
                            self._sleep(index, 2)
                    else:
                        self.logger.warning(f"[{index}] 没找到 {target_text} 添加按钮！", "V2ray")

            if self._check_stop(): return False, "已停止操作"
            
            # 等待回到主页
            d(textContains="连接").wait(timeout=5)
            self._random_delay(index, 2, 5)
            
            # 选择最新添加的代理
            self.logger.info(f"[{index}] 尝试选中最新的代理...", "V2ray")
            if 'alias' in locals() and alias:
                alias_node = d(textContains=alias)
                if alias_node.exists:
                    alias_node.click()
                    self._sleep(index, 1)
            else:
                d.click(0.4, 0.18)
                self._sleep(index, 1)
                
            if self._check_stop(): return False, "已停止操作"
            
            # 4. 点击启动连接
            self._random_delay(index, 2, 5)
            fab_btn = d(resourceId="com.v2ray.ang:id/fab")
            if fab_btn.exists:
                if not (d(textContains="点击测试连接").exists or d(textContains="Tap to test connection").exists):
                    self.logger.info(f"[{index}] 准备启动服务...", "V2ray")
                    try:
                        fab_btn.click()
                        if d(textContains="确定").wait(timeout=3):
                            d(textContains="确定").click()
                    except Exception as e:
                        # 开启VPN极易导致ADB底层网络变化从而断开连接
                        self.logger.warning(f"[{index}] 启动服务时网络瞬断: {e}", "V2ray")
                        self._sleep(index, 3)
                        # 尝试重连uiautomator2客户端
                        try:
                            d = u2.connect(device_addr)
                            d.implicitly_wait(10.0)
                        except Exception:
                            pass
                else:
                    self.logger.info(f"[{index}] 服务已经是连接状态", "V2ray")
                        
            # 等待已连接
            if not d(textContains="点击测试连接").wait(timeout=10) and not d(textContains="Tap to test connection").exists:
                self.logger.warning(f"[{index}] 服务似乎未能成功启动，未检测到已连接状态", "V2ray")
            else:
                self.logger.info(f"[{index}] 启动服务成功", "V2ray")
                
            if self._check_stop(): return False, "已停止操作"
            
            # 5. 测试真实IP
            self._random_delay(index, 2, 5)
            self.logger.info(f"[{index}] 正在测试连接...", "V2ray")
            
            success = False
            success_msg = "真实IP测试超时或失败"
            
            try:
                test_target = d(textContains="点击测试连接")
                if not test_target.exists:
                    test_target = d(textContains="测试连接")
                if not test_target.exists:
                    test_target = d(textContains="Tap to test connection")
                    
                if test_target.exists:
                    test_target.click()
                    self.logger.info(f"[{index}] 已点击测试，等待结果 (最长60秒)...", "V2ray")
                    testing_count = 0
                    for _ in range(60):
                        if self._check_stop(): return False, "已停止操作"
                        self._sleep(index, 1)
                        try:
                            xml_str = d.dump_hierarchy()
                        except Exception as e:
                            self.logger.warning(f"[{index}] 检查结果时网络瞬断: {e}", "V2ray")
                            self._sleep(index, 2)
                            try:
                                d = u2.connect(device_addr)
                                d.implicitly_wait(10.0)
                            except Exception:
                                pass
                            continue
                        
                        if "测试中" in xml_str or "Testing" in xml_str:
                            testing_count += 1
                            if testing_count >= 60:
                                success_msg = "真实IP测试一直处于测试中(超时放弃)"
                                self.logger.warning(f"[{index}] 真实IP测试一直处于测试中，超过60秒放弃", "V2ray")
                                break
                            continue
                        else:
                            testing_count = 0
                            
                        if "延时" in xml_str or "delay" in xml_str.lower() or "ms" in xml_str.lower() or "连接成功" in xml_str:
                            success = True
                            success_msg = "真实IP测试成功 (显示延迟)"
                            break
                            
                        if "context deadline exceeded" in xml_str:
                            success = False
                            success_msg = "网络异常：context deadline exceeded"
                            break
                            
                        if "失败" in xml_str or "Timeout" in xml_str or "超时" in xml_str or "timeout" in xml_str.lower() or "failed" in xml_str.lower():
                            success = False
                            success_msg = "真实IP测试失败或超时"
                            break
                else:
                    success_msg = "未找到[测试连接]按钮"
                    success = False
            except Exception as e:
                self.logger.error(f"[{index}] 测试IP时发生异常: {e}", "V2ray")
                success_msg = f"测试时异常: {e}"
                success = False

            self.logger.info(f"[{index}] V2ray配置完成: {success_msg}", "V2ray" if success else "V2ray报错")
            
            # 稍作停留，让用户能看清结果
            self._random_delay(index, 10, 15)
            
            # 返回桌面
            console.adb(index, "shell input keyevent 3")
            return success, success_msg
            
        except Exception as e:
            self.logger.error(f"[{index}] 配置V2ray发生异常: {str(e)}", "V2ray")
            return False, str(e)
