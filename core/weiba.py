import time
import threading
import random
import uiautomator2 as u2
import os

class WeibaAutomation:
    def __init__(self, manager, logger):
        self.manager = manager
        self.logger = logger
        # 常见微霸包名
        self.possible_pkgs = ["com.soft.weiba", "com.weiba", "com.pb.weiba", "com.weiba.pro"]

    def _check_stop(self):
        return getattr(self.manager, 'stop_flag', False)

    def _sleep(self, index, seconds):
        for _ in range(int(seconds * 2)):
            if self._check_stop(): return
            time.sleep(0.5)

    def _random_delay(self, index, min_s=15, max_s=30):
        delay = random.randint(min_s, max_s)
        self.logger.info(f"[{index}] 随机延时 {delay} 秒...", status="运行中")
        self._sleep(index, delay)

    def _get_device_info(self, d):
        """解析页面中的设备信息用于对比"""
        info = {}
        try:
            xml_str = d.dump_hierarchy()
            if not xml_str:
                return info
                
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_str)
            nodes = list(root.iter('node'))
            for i, node in enumerate(nodes):
                t = node.attrib.get('text', '')
                if t in ["微霸识别码", "品牌", "机型", "IMEI", "安卓ID"]:
                    # 往后找第一个有效值
                    for j in range(i + 1, min(i + 15, len(nodes))):
                        val = nodes[j].attrib.get('text', '').strip()
                        if val and val not in ["微霸识别码", "品牌", "机型", "IMEI", "安卓ID", "查看更多...", "环境检测", "一键改机"]:
                            info[t] = val
                            break
        except Exception as e:
            self.logger.warning(f"获取设备信息失败: {e}")
        return info

    def _launch_weiba(self, console, index, d):
        self.logger.info(f"[{index}] 尝试打开微霸Pro 2026...", status="运行中")
        console.adb(index, "shell input keyevent 3")  # 回到桌面
        self._sleep(index, 1.5)
        
        # 尝试通过名字直接点击 (支持动态等待)
        if d(textContains="微霸").exists:
            d(textContains="微霸").click()
            self._sleep(index, 3)
            return True

        # 如果桌面没找到，尝试已知常用包名
        pkgs_output = console.adb(index, "shell pm list packages")
        for line in pkgs_output.splitlines():
            pkg = line.replace("package:", "").strip()
            if "weiba" in pkg.lower() or "duokai" in pkg.lower():
                console.runapp(index, pkg)
                self._sleep(index, 3)
                return True

        # 滑动桌面再次寻找
        d.swipe_ext("left", scale=0.8)
        self._sleep(index, 1.5)
        if d(textContains="微霸").exists:
            d(textContains="微霸").click()
            self._sleep(index, 3)
            return True

        self.logger.warning(f"[{index}] 未能识别到微霸App，请确认已安装。")
        return False

    def _close_weiba(self, console, index, d=None):
        self.logger.info(f"[{index}] 尝试彻底关闭微霸进程...", status="运行中")
        
        pkgs_to_kill = set(self.possible_pkgs)
        
        # 使用 u2 获取当前前台包名
        if d:
            try:
                current_pkg = d.app_current().get('package')
                if current_pkg and "launcher" not in current_pkg and "systemui" not in current_pkg:
                    pkgs_to_kill.add(current_pkg)
            except Exception:
                pass

        # 获取设备中所有带关键字的包名
        pkgs_output = console.adb(index, "shell pm list packages")
        for line in pkgs_output.splitlines():
            if "package:" in line:
                pkg = line.replace("package:", "").strip()
                if "weiba" in pkg.lower() or "duokai" in pkg.lower() or "weiqu" in pkg.lower():
                    pkgs_to_kill.add(pkg)

        # 强制停止这些App
        for pkg in pkgs_to_kill:
            if pkg:
                console.adb(index, f"shell am force-stop {pkg}")
                
        # 回到桌面
        console.adb(index, "shell input keyevent 3")

    def execute_weiba_flow(self, index):
        console = self.manager.console
        
        # 连接 uiautomator2
        port = 5555 + index * 2
        device_addr = f"127.0.0.1:{port}"
        try:
            d = u2.connect(device_addr)
            d.implicitly_wait(10.0) # 全局隐式等待10秒，提高元素查找稳定性
        except Exception as e:
            self.logger.error(f"[{index}] uiautomator2 连接失败: {e}")
            return False
        
        for attempt in range(1, 10):
            if getattr(self.manager, 'stop_flag', False):
                self.logger.warning(f"[{index}] 收到停止指令，中止微霸操作。", status="警告")
                return False
                
            self.logger.info(f"[{index}] 开始执行微霸操作, 第 {attempt} 次尝试", status="运行中")
            
            if attempt > 1:
                self._close_weiba(console, index, d)
                self._sleep(index, 2)
            
            # 第二步：打开微霸Pro 2026
            if not self._launch_weiba(console, index, d):
                self.logger.error(f"[{index}] 打开微霸失败")
                continue
                
            self.logger.info(f"[{index}] 等待微霸启动并自动跑完环境检测切换到'一键改机'页面...", status="运行中")
            
            # 动态等待：不再使用固定循环延时，直接利用 u2 的 wait 方法
            if not d(textContains="开启伪装").wait(timeout=60) and not d(textContains="抹除").wait(timeout=60):
                self.logger.error(f"[{index}] 未能自动切换到'一键改机'页面，可能卡在环境检测(60秒超时)。")
                continue
            
            self.logger.info(f"[{index}] 已成功进入'一键改机'页面。")
            self._random_delay(index, 10, 20)

            # 第三步：点击抹除APP (即使顺序变了也能精准找到)
            self.logger.info(f"[{index}] 点击抹除APP...", status="运行中")
            btn_erase = d(textContains="抹除APP")
            if not btn_erase.wait(timeout=10):
                btn_erase = d(textContains="抹除App")
                
            if btn_erase.wait(timeout=5):
                btn_erase.click()
            else:
                self.logger.warning(f"[{index}] UI树中未找到抹除APP节点(WebView可能休眠)。尝试兜底点击")
                d.click(397, 612)

            self._sleep(index, 2)
            
            # 第四步：打开抹除APP后点击Telegam (或Telegram)
            self.logger.info(f"[{index}] 寻找 Telegram...", status="运行中")
            # 通过滑动和动态查找来精准定位，无视顺序和位置
            elem_tg = d(textContains="Telegram")
            if not elem_tg.wait(timeout=10):
                elem_tg = d(textContains="Telegam")
                
            if elem_tg.wait(timeout=5):
                elem_tg.click()
            else:
                self.logger.warning(f"[{index}] 列表中未找到Telegram节点。")
                # 尝试唤醒或滚动
                d.swipe_ext("up", scale=0.5)
                self._sleep(index, 1)
                if elem_tg.wait(timeout=5):
                    elem_tg.click()
                else:
                    self.logger.warning(f"[{index}] 仍然找不到 Telegram，盲点兜底...")
                    d.click(270, 200)

            # 第五步：点击Telegam后最下面会提示“重置应用”，找到“确定”并点击
            self.logger.info(f"[{index}] 确认重置 Telegram...", status="运行中")
            if d(textContains="重置应用").wait(timeout=5):
                self.logger.info(f"[{index}] 发现重置应用提示框")
            else:
                self.logger.warning(f"[{index}] 未检测到重置应用提示框(可能已弹出但UI树未更新)")
                
            if d(textContains="确定").wait(timeout=5):
                d(textContains="确定").click()
            else:
                self.logger.warning(f"[{index}] 找不到确定按钮弹窗，兜底点击...")
                d.click(400, 580)
                
            self.logger.info(f"[{index}] 操作Telegram成功，等待提示消失...", status="运行中")
            self._sleep(index, 3)

            # 第六步：点左上角的返回
            self.logger.info(f"[{index}] 返回首页...", status="运行中")
            if d(resourceId="com.soft.weiba:id/iv_back").exists:
                d(resourceId="com.soft.weiba:id/iv_back").click()
            else:
                d.press("back")
            self._sleep(index, 2)

            # 第七步：记录首页中的当前设备信息
            self.logger.info(f"[{index}] 获取改机前设备信息...", status="运行中")
            info_before = self._get_device_info(d)
            self.logger.info(f"[{index}] 改机前信息: {info_before}")

            # 第八步：点首页界面中的“一键修改机型并开启伪装”
            self.logger.info(f"[{index}] 执行一键修改机型...", status="运行中")
            if getattr(self.manager, 'stop_flag', False): return False
            
            btn_change = d(textContains="一键修改机型")
            if btn_change.wait(timeout=10):
                btn_change.click()
            else:
                self.logger.warning(f"[{index}] 找不到'一键修改机型并开启伪装'按钮，兜底点击。")
                d.click(270, 743)
                
            if d(textContains="伪装成新设备").wait(timeout=10):
                d(textContains="伪装成新设备").click()
            else:
                self.logger.warning(f"[{index}] 找不到'伪装成新设备'按钮弹窗，兜底点击...")
                d.click(270, 850)

            # 点击后界面中间会提示“正在处理” 
            self.logger.info(f"[{index}] 正在处理改机中(最长等待30秒)...", status="运行中")
            process_success = d(textContains="成功").wait(timeout=30)

            if getattr(self.manager, 'stop_flag', False): return False
            if not process_success:
                self.logger.warning(f"[{index}] 改机处理超过30秒或未检测到成功提示，直接验证信息变化...", status="警告")

            self.logger.info(f"[{index}] 一键新机成功！对比新设备信息...", status="运行中")
            self._sleep(index, 2) 
            info_after = self._get_device_info(d)
            self.logger.info(f"[{index}] 改机后信息: {info_after}")
            
            if not info_after or (info_before and info_before.get("IMEI") == info_after.get("IMEI")):
                self.logger.warning(f"[{index}] 改机后设备信息未变化或获取失败，判定为失败", status="警告")
                continue
            
            self.logger.info(f"[{index}] 完美！设备信息已成功更新！", status="完成")
            self._random_delay(index, 15, 30)
            
            console.adb(index, "shell input keyevent 3")
            return True

        return False

    def _run_task(self, index):
        try:
            self.execute_weiba_flow(index)
        finally:
            # 确保线程信息被清理
            if hasattr(self.manager, '_running_threads') and index in self.manager._running_threads:
                self.manager._running_threads.remove(index)


    def run_weiba_on_selected(self, index_list):
        if not hasattr(self.manager, '_running_threads'):
            self.manager._running_threads = set()

        for idx in index_list:
            if idx in self.manager._running_threads:
                self.logger.warning(f"[{idx}] 任务已在运行中，请勿重复。", status="警告")
                continue
                
            self.manager._running_threads.add(idx)
            t = threading.Thread(target=self._run_task, args=(idx, ))
            t.daemon = True
            t.start()
            self._sleep(idx, 1)
