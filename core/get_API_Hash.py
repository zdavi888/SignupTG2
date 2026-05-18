import os
import sys
import logging
import random
import time
import re
import uiautomator2 as u2
import threading

class GetAPIHash:
    def __init__(self, logger, config=None, lock=None):
        self.logger = logger
        self.config = config
        self.lock = lock
        self.d = None

    def _log_info(self, index, msg):
        if self.logger:
            self.logger.info(f"[{index}] {msg}", "获取API")
        else:
            print(f"[{index}] INFO: {msg}")

    def _log_error(self, index, msg):
        if self.logger:
            self.logger.error(f"[{index}] {msg}", "获取API")
        else:
            print(f"[{index}] ERROR: {msg}")

    def get_api_app_name(self, index):
        # 使用类似于代理的全局分配提取模式，如果主调度分配了名称，则直接使用
        if hasattr(self, 'pre_fetched_app_name') and self.pre_fetched_app_name:
            return self.pre_fetched_app_name
            
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        
        # 优先从配置获取，否则使用固定默认值
        app_name_file = None
        if self.config and getattr(self.config, 'get', None):
            app_name_file = self.config.get('api_app_preset')
            
        if not app_name_file:
            app_name_file = os.path.join("data", "API预设名称.txt")
            
        # 统一转为绝对路径
        if not os.path.isabs(app_name_file):
            app_name_file = os.path.join(root_dir, app_name_file)

        if not os.path.exists(app_name_file):
            self._log_error(index, f"预设名称文件不存在，查找路径为: {app_name_file}")
            return None

        app_name = None
        # 线程安全读取并删除第一行
        if self.lock:
            self.lock.acquire()
        try:
            # 加入多重编码尝试，防止GBK等编码错误导致无法读取
            lines = []
            for enc in ['utf-8', 'gbk', 'utf-8-sig']:
                try:
                    with open(app_name_file, 'r', encoding=enc) as f:
                        lines = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            
            valid_lines = [line for line in lines if line.strip()]
            if valid_lines:
                app_name = valid_lines[0].strip()
                # 重新写入剩余内容
                with open(app_name_file, 'w', encoding='utf-8') as f:
                    f.writelines(valid_lines[1:])
        except Exception as e:
            self._log_error(index, f"读取API预设名称出错: {e}")
        finally:
            if self.lock:
                self.lock.release()
                
        return app_name

    def run(self, index, phone_number=None):
        if not phone_number:
            self._log_error(index, "没有提供手机号参数，无法获取API")
            return False

        port = 5555 + index * 2
        device_addr = f"127.0.0.1:{port}"
        
        try:
            self.d = u2.connect(device_addr)
            self.d.implicitly_wait(10.0)
            self._log_info(index, f"成功连接设备: {self.d.serial}")
        except Exception as e:
            self._log_error(index, f"无法连接设备: {e}")
            return False

        self._log_info(index, "==== 开始执行完整 API 提取流程 ====")
        
        # 1. 准备浏览器环境
        self.d.press("home")
        time.sleep(1)
        self.d.shell("am force-stop mark.via")
        time.sleep(1)
        self.d.shell("am start -n mark.via/.Shell")
        time.sleep(3)
        
        if self.d(text="同意并继续").exists:
            self.d(text="同意并继续").click()
            time.sleep(2)
            
        # 2. 访问官网
        self._log_info(index, "正在访问 my.telegram.org/auth ...")
        self.d.shell("am start -a android.intent.action.VIEW -d 'https://my.telegram.org/auth' mark.via")
        time.sleep(8)
        
        if not self.d(textContains="Your Phone Number").wait(timeout=15.0):
            self._log_error(index, "页面加载缓慢或无法显示 TG 登录页")
            return False
            
        # 3. 输入手机号
        phone_field = self.d(className="android.widget.EditText")
        if phone_field.exists:
            self._log_info(index, f"输入手机号: {phone_number}")
            phone_field.set_text(phone_number)
            time.sleep(1)
            self.d.swipe(0.5, 0.7, 0.5, 0.4)
            next_btn = self.d(text="Next")
            if next_btn.exists:
                next_btn.click()
                time.sleep(3)
            else:
                self._log_error(index, "找不到 Next 按钮")
                # return False
        else:
            self._log_error(index, "找不到手机号输入框")
            # return False
            
        # 4. 获取验证码
        if not self.d(textContains="Confirmation").wait(timeout=10):
            # 兼容有些时候到了这步但是没显示标题的情况
            pass
            
        self._log_info(index, "需等待 10 秒后开始提取验证码通知...")
        time.sleep(10)
        
        verify_code = None
        for attempt in range(12): # 等待约 1 分钟
            self.d.shell("cmd statusbar expand-notifications")
            time.sleep(2)
            
            try:
                xml = self.d.dump_hierarchy()
                # 提取所有 text 属性内容
                all_raw_texts = re.findall(r'text="([^"]*)"', xml)
                
                # 合并并按行拆分，过滤掉明显非验证码的系统词汇
                filtered_lines = []
                for t in all_raw_texts:
                    t = t.strip()
                    if not t or t.lower() in ["telegram", "mark as read", "via", "reply"]: continue
                    filtered_lines.append(t)
                
                # 调试打印，方便用户看到抓取到了什么
                self._log_info(index, f"[通知探测] 抓取到的文本行: {filtered_lines}")

                # 核心逻辑 1: 寻找包含冒号且后面跟着11位码的行
                for line in filtered_lines:
                    if ":" in line or "：" in line:
                        # 看看冒号后面是不是就是那个码
                        parts = re.split(r'[:：]', line)
                        for p in parts:
                            p_clean = p.strip()
                            if len(p_clean) == 11 and any(c.isdigit() for c in p_clean) and any(c.isalpha() for c in p_clean):
                                verify_code = p_clean
                                break
                    if verify_code: break

                # 核心逻辑 2: 寻找上一行以冒号结尾，下一行是11位码的情况
                if not verify_code:
                    for i in range(len(filtered_lines) - 1):
                        curr = filtered_lines[i]
                        nxt = filtered_lines[i+1]
                        if curr.endswith(':') or curr.endswith('：'):
                            if len(nxt) == 11 and any(c.isdigit() for c in nxt) and any(c.isalpha() for c in nxt):
                                verify_code = nxt
                                break
                
                # 备用逻辑：直接正则搜 11 位码
                if not verify_code:
                    for line in filtered_lines:
                        m = re.findall(r'[a-zA-Z0-9]{11}', line)
                        for code in m:
                            if any(c.isdigit() for c in code) and any(c.isalpha() for c in code):
                                # 排除掉一些可能的 UI 词
                                if code.lower() not in ["framelayout", "progressbar", "linearlayout"]:
                                    verify_code = code
                                    break
                        if verify_code: break
            except Exception as e:
                self._log_error(index, f"解析通知 XML 出错: {e}")
            
            self.d.shell("cmd statusbar collapse")
            if verify_code: break
            
            self._log_info(index, f"未检测到验证码，等待 5 秒后重试 (第 {attempt+1}/12 次)...")
            time.sleep(5)
            
        if not verify_code:
            self._log_error(index, "未能从通知栏提取到 11 位有效验证码")
            return False
            
        self._log_info(index, f"🎉 成功提取验证码: {verify_code}，正在填入...")
        
        code_inputs = self.d(className="android.widget.EditText")
        if code_inputs.exists:
            # 最后一个通常是验证码框
            code_box = code_inputs[code_inputs.count - 1]
            code_box.click()
            time.sleep(0.5)
            code_box.set_text(verify_code)
            time.sleep(2)
            self.d.swipe(0.5, 0.7, 0.5, 0.4)
            signin_btn = self.d(text="Sign In")
            if signin_btn.exists:
                signin_btn.click()
                time.sleep(5)
            else:
                self._log_error(index, "找不到 Sign In 按钮")
                return False
        else:
            self._log_error(index, "找不到验证码输入框")
            return False
            
        # 5. 进入管理页面
        api_link = self.d(text="API development tools")
        if api_link.wait(timeout=10):
            api_link.click()
            time.sleep(5)
        
        # 6. 处理 API 申请
        if self.d(textContains="App api_id:").exists:
             self._log_info(index, "账号已分配过 API，直接提取。")
             return self.extract_and_save_api(index, phone_number)
        
        self._log_info(index, "准备申请新 API...")
        while True:
            # 回到顶部
            self._log_info(index, "回到顶部并清理旧数据...")
            try:
                for _ in range(3):
                    self.d.swipe(0.5, 0.3, 0.5, 0.8) 
                    time.sleep(0.5)
            except: pass
            
            # 提取新名称
            app_title_text = self.get_api_app_name(index)
            if not app_title_text:
                self._log_error(index, "无预设名称可用")
                return False
            
            content_text = app_title_text
            self._log_info(index, f"尝试使用名称: {content_text}")

            try:
                # App title
                lbl_title = self.d(text="App title:")
                if lbl_title.exists:
                    inp_title = lbl_title.down(className="android.widget.EditText")
                    if inp_title.exists:
                        inp_title.click()
                        time.sleep(0.5)
                        inp_title.set_text("")
                        time.sleep(0.5)
                        inp_title.set_text(content_text)
                    
                # Short name
                lbl_short = self.d(text="Short name:")
                if lbl_short.exists:
                    inp_short = lbl_short.down(className="android.widget.EditText")
                    if inp_short.exists:
                        inp_short.click()
                        time.sleep(0.5)
                        inp_short.set_text("")
                        time.sleep(0.5)
                        inp_short.set_text(content_text)
                
                # URL
                lbl_url = self.d(text="URL:")
                if lbl_url.exists:
                     inp_url = lbl_url.down(className="android.widget.EditText")
                     if inp_url.exists: inp_url.set_text("")
                
                self.d.swipe(0.5, 0.8, 0.5, 0.4)
                time.sleep(1)
                
                # Platform
                plt_android = self.d(text="Android")
                if plt_android.exists: plt_android.click()
                
                # Description
                lbl_desc = self.d(text="Description:")
                if not lbl_desc.exists:
                    self.d.swipe(0.5, 0.8, 0.5, 0.4)
                    time.sleep(1)
                
                if lbl_desc.exists:
                    inp_desc = lbl_desc.down(className="android.widget.EditText")
                    if inp_desc.exists:
                        inp_desc.click()
                        time.sleep(0.5)
                        inp_desc.set_text("")
                        time.sleep(0.5)
                        inp_desc.set_text(content_text)

                self.d.swipe(0.5, 0.8, 0.5, 0.4)
                time.sleep(1)
                
                # Create
                self._log_info(index, "正在向下滚动寻找 Create application 按钮...")
                # 强化滚动寻找逻辑
                for _ in range(5):
                    # 检查按钮是否在当前视口
                    create_btn = self.d(text="Create application", className="android.widget.Button")
                    if not create_btn.exists: 
                        create_btn = self.d(text="Create application")
                    
                    if create_btn.exists:
                        # 确保按钮在视口内且可点击
                        self._log_info(index, "已找到创建按钮，点击中...")
                        create_btn.click()
                        time.sleep(10)
                        break
                    
                    # 如果没找到，继续向上滑（页面向下滚）
                    self.d.swipe(0.5, 0.8, 0.5, 0.2)
                    time.sleep(1.5)
                else:
                    self._log_error(index, "滚动寻找 5 次后仍未找到 Create application 按钮")
                    break
                    
                # 判定结果
                if self.d(textContains="App api_id:").exists:
                        self._log_info(index, "🎉 创建成功！正在提取数据...")
                        return self.extract_and_save_api(index, phone_number)
                    else:
                        error_dismissed = False
                        # 尝试捕获报错弹窗并点击确认
                        for btn_text in ["确定", "OK", "确 定", "Confirm"]:
                            btn = self.d(text=btn_text)
                            if btn.exists:
                                self._log_error(index, f"创建提示报错 (发现 {btn_text} 弹窗)，正在尝试清理并换名重试...")
                                btn.click()
                                error_dismissed = True
                                break
                        
                        if error_dismissed:
                            time.sleep(2)
                            continue 
                        else:
                            # 如果没弹窗也没成功，可能还在加载或者静默错误
                            self._log_error(index, "未能检测到成功跳转或报错弹窗，尝试再次提取验证...")
                            if self.d(textContains="App api_id:").exists:
                                return self.extract_and_save_api(index, phone_number)
                            break
                else:
                    self._log_error(index, "滚动 3 次后仍未找到 Create application 按钮")
                    break
            except Exception as e:
                self._log_error(index, f"表单异常: {e}")
                break
        
        return False

    def extract_and_save_api(self, index, phone_number):
        self._log_info(index, "正在提取分配给该账号的 api_id 与 api_hash...")
        
        # 找出所有文本节点
        all_texts = []
        for x in self.d(className="android.widget.TextView"):
             try:
                 all_texts.append(x.get_text())
             except:
                 pass
                 
        api_id, api_hash, app_title, short_name = "","","",""
        for i, t in enumerate(all_texts):
             if t.strip() == "App api_id:":
                  api_id = all_texts[i+1].strip()
             elif t.strip() == "App api_hash:":
                  api_hash = all_texts[i+1].strip()
             elif t.strip() == "App title:":
                  app_title = all_texts[i+1].strip()
             elif t.strip() == "Short name:":
                  short_name = all_texts[i+1].strip()
                  
        if not api_id or not api_hash:
             self._log_error(index, "提取 api_id/hash 失败，页面元素结构发生变动。")
             return False
             
        self._log_info(index, f"获取明细明文 => api_id: {api_id}, hash: {api_hash}")

        # 调用保存
        save_res = self._save_account_data(index, phone_number, api_id, api_hash, app_title, short_name)

        # 向上滑动找 "Save changes" 以便修改生效
        self.d(scrollable=True).scroll.to(text="Save changes")
        time.sleep(1)
        save_btn = self.d(text="Save changes")
        if save_btn.exists:
             self._log_info(index, "点击 Save changes 进行同步保存...")
             save_btn.click()
             # 按钮变为 Saving... 继续走
             time.sleep(2)
        
        # 全部完成后随机延时15-30秒
        delay = random.uniform(15, 30)
        self._log_info(index, f"获取API全部流程已完成，延时 {delay:.1f} 秒...")
        time.sleep(delay)
        
        # 退回桌面
        self.d.press("home")
        return True

    def _save_account_data(self, index, phone_number, api_id, api_hash, app_title, short_name):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(current_dir)
            
            save_path = None
            if self.config and getattr(self.config, 'get', None):
                # 统一使用 account_data_path
                save_path = self.config.get('account_data_path')
                
            if not save_path:
                save_path = os.path.join(root_dir, "data", "账号资料")
            elif not os.path.isabs(save_path):
                save_path = os.path.join(root_dir, save_path)

            if not os.path.exists(save_path):
                os.makedirs(save_path)
            
            clean_phone = str(phone_number).strip()
            if clean_phone and not clean_phone.startswith('+'):
                clean_phone = '+' + clean_phone
                
            phone_folder = os.path.join(save_path, clean_phone)
            if not os.path.exists(phone_folder):
                os.makedirs(phone_folder)
                
            txt_path = os.path.join(phone_folder, f"{clean_phone}.txt")
            
            if not os.path.exists(txt_path):
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"手机号：{clean_phone}\n")
            
            data_to_write = f"\nApp api_id：{api_id}\nApp api_hash：{api_hash}\nApp title：{app_title}\nShort name：{short_name}\n"
            with open(txt_path, 'a', encoding='utf-8') as f:
                f.write(data_to_write)
                
            self._log_info(index, f"账号API资料追加保存完成: {txt_path}")
            return True
        except Exception as e:
            self._log_error(index, f"往本地资料文件写入时发生异常: {e}")
            return False

    def _record_failure(self, index, phone_number, reason):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(current_dir)
            
            save_path = None
            if self.config and getattr(self.config, 'get', None):
                save_path = self.config.get('account_data_path')
                
            if not save_path:
                save_path = os.path.join(root_dir, "data", "账号资料")
            elif not os.path.isabs(save_path):
                save_path = os.path.join(root_dir, save_path)

            if not os.path.exists(save_path):
                os.makedirs(save_path)
            
            clean_phone = str(phone_number).strip()
            if clean_phone and not clean_phone.startswith('+'):
                clean_phone = '+' + clean_phone
                
            phone_folder = os.path.join(save_path, clean_phone)
            if not os.path.exists(phone_folder):
                os.makedirs(phone_folder)
                
            txt_path = os.path.join(phone_folder, f"{clean_phone}.txt")
            
            if not os.path.exists(txt_path):
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(f"手机号：{clean_phone}\n")
            
            with open(txt_path, 'a', encoding='utf-8') as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {reason}\n")
                
        except Exception as e:
            self._log_error(index, f"记录获取API失败日志时发生错误: {e}")

# ----------------- 测试功能模块（可独立执行） -----------------
def run_test_standalone():
    print("=" * 50)
    print("      Telegram 独立测试: 获取 API_ID / API_HASH")
    print("=" * 50)
    
    # 因为此文件在 core/ 中，为确保可以引入关联类，需设置环境变量
    if __name__ == '__main__':
        current_path = os.path.dirname(os.path.abspath(__file__))
        parent_path = os.path.dirname(current_path)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
            
    from core.config import ConfigManager
    from core.ldconsole import LDConsole
    from core.logger import AppLogger
    
    config = ConfigManager()
    ld_path = config.get_ld_path()
    if not ld_path:
        print("【错误】 请先在系统配置中设置雷电模拟器根目录 (ld_path)。")
        return

    console = LDConsole(ld_path)
    instances = console.list2()
    
    running_instances = [inst for inst in instances if inst["android_status"] == 1]
    
    if not running_instances:
        print("当前没有任何处于开启状态的模拟器，请先启动您要测试的模拟器！！")
        return
        
    print("当前运行状态的模拟器列表:")
    for idx, inst in enumerate(running_instances):
        print(f" [{idx}] 号选项 -> 面板索引: {inst['index']}, 名称: {inst['name']}")
        
    print("-" * 50)
    selection = input("请输入要运行测试的模拟器选项 (例如输入 0 选第一个): ").strip()
    
    try:
        selection_idx = int(selection)
        if selection_idx < 0 or selection_idx >= len(running_instances):
            raise ValueError()
    except ValueError:
        print("输入无效。")
        return
        
    target_inst = running_instances[selection_idx]
    target_index = target_inst["index"]
    print(f"\n✅ 模拟器选定: {target_inst['name']} (多开索引: {target_index})")
    
    phone_number = input("\n👇请输入该模拟器内已绑定的 Telegram 手机号码 (带+与区号如 +63123456789): ").strip()
    if not phone_number:
        print("手机号码不能为空！")
        return
    if not phone_number.startswith('+'):
         phone_number = "+" + phone_number
         
    print(f"✅ 将请求发送给手机号: {phone_number}")
    print(f"\n🚀 即将开始执行自动获取获取API任务...")
    
    app_logger = AppLogger()
    import threading
    lock = threading.Lock()
    api_runner = GetAPIHash(logger=app_logger, config=config, lock=lock)
    
    try:
        success = api_runner.run(target_index, phone_number)
        if success:
            print("\n🎉 测试成功：顺利拿到验证码，注册APP，提取各项凭证！")
        else:
            print("\n❌ 测试失败：未能跑出全部流程，具体看上面日志中的 ERROR 错误打印。")
    except Exception as e:
        print(f"\n💔 严重错误: {str(e)}")

if __name__ == "__main__":
    run_test_standalone()
