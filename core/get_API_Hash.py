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
            
        # 提取预设名称
        app_name_file = "API 程序预设名称.txt"
        
        # 寻找文件路径
        config_val = self.config.get('api_app_preset') if (self.config and getattr(self.config, 'get', None)) else None
        if config_val and config_val.strip():
            app_name_file = config_val.strip()
            # 如果是相对路径，可以基于运行目录转换为绝对路径
            if not os.path.isabs(app_name_file):
                app_name_file = os.path.abspath(app_name_file)
        else:
            # 默认同级或上一级根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(current_dir)
            app_name_file = os.path.join(root_dir, "API 程序预设名称.txt")

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
        except Exception as e:
            self._log_error(index, f"无法连接设备: {e}")
            return False

        self._log_info(index, "==== 开始执行找回的 Via 浏览器流程 ====")
        
        # 退回桌面
        self.d.press("home")
        time.sleep(2)

        # 确保后台无 via 以防页面缓存
        self.d.shell("am force-stop mark.via")
        time.sleep(1)

        self._log_info(index, "启动 Via 浏览器...")
        # 普通启动 Via
        self.d.shell("am start -n mark.via/.Shell")
        time.sleep(5)
        
        # 处理欢迎页面同意并继续
        if self.d(text="同意并继续").exists:
            self._log_info(index, "点击同意并继续...")
            self.d(text="同意并继续").click()
            time.sleep(3)
            
        # 到图2 (关于页面)，点击下面的回到首页图标
        if self.d(text="联系我们").exists or self.d(text="官方网站").exists or self.d(text="拾穗").exists:
            self._log_info(index, "当前在关于页面(图2)，点击底部回到首页图标...")
            width, height = self.d.window_size()
            self.d.click(width // 2, height - 30)
            time.sleep(2)
            
        # 严格使用老版本逻辑：直接通过意图访问指定 URL
        self._log_info(index, "在浏览器主页(图3)中访问 https://my.telegram.org/auth ...")
        self.d.shell("am start -a android.intent.action.VIEW -d 'https://my.telegram.org/auth' mark.via")
        time.sleep(8)

        self._log_info(index, "等待 my.telegram.org 页面加载完成...")
        
        # 老版本逻辑：验证是否到了手机号输入步骤
        if not self.d(textContains="Your Phone Number").wait(timeout=15.0):
            self._log_error(index, "未能显示 Telegram Auth 页面")
            return False

        # 老版本逻辑：输入手机号
        phone_input = self.d(className="android.widget.EditText")
        if phone_input.exists:
            self._log_info(index, f"填写手机号: {phone_number}")
            phone_input[0].set_text(phone_number)
            time.sleep(1)
        else:
            self._log_error(index, "找不到手机号输入框")
            return False
            
        # 向下滑动页面，确保Next按钮可见
        self.d.swipe(0.5, 0.7, 0.5, 0.3)
        time.sleep(1)
            
        next_btn = self.d(text="Next", className="android.widget.Button")
        if not next_btn.exists:
             next_btn = self.d(text="Next")
        if not next_btn.exists:
            self._log_error(index, "找不到 Next 按钮！")
            return False
            
        next_btn.click()
        time.sleep(3)
        self._log_info(index, "等待Confirmation code输入框出现...")
        
        if not self.d(textContains="Confirmation").wait(timeout=10):
            self._log_error(index, "手机号输入后未显示验证码输入框 (可能是请求过于频繁或被屏蔽)")
            return False
            
        self._log_info(index, "等待 10 秒后开始查看通知栏... (防止立刻查看时验证码还未到达)")
        time.sleep(10)
        
        self._log_info(index, "等待系统接收 Telegram 验证码通知 (最长等待5分钟)...")
        
        verify_code = None
        
        # 等待长达5分钟 (60次 * 5秒)
        for _ in range(60):
            # 展开通知栏获取即时弹出的所有消息文本
            # 兼容所有Android版本的下拉通知栏命令
            self.d.shell("cmd statusbar expand-notifications")
            time.sleep(2)
            
            texts = []
            try:
                xml = self.d.dump_hierarchy()
                import re
                matches = re.findall(r'text="([^"]*)"', xml)
                for txt in matches:
                    txt = txt.strip()
                    if txt and txt not in texts:
                        texts.append(txt)
            except Exception as e:
                self._log_error(index, f"读取UI元素出错: {e}")
                
            # 收起通知栏恢复界面
            self.d.shell("cmd statusbar collapse")
            time.sleep(1)
            # 防御性收起
            try:
                self.d.shell("input swipe 500 1500 500 200")
            except:
                pass
            time.sleep(2)

            if texts:
                full_text = "\n".join(texts)
                
                # 只要存在 Telegram 通知就进入处理
                if "Telegram" in texts or "Telegram Notifications" in texts:
                    if not hasattr(self, '_seen_notifications'):
                        self._seen_notifications = set()
                    
                    import re
                    # 首先提取消息内容
                    tmp_lines = []
                    sender = "Telegram"
                    seen_sender = False
                    
                    for txt in texts:
                        # 兼容 dump_hierarchy() 中可能存在的 &#10; 换行符
                        txt = txt.replace('&#10;', '\n')
                        for line in txt.split('\n'):
                            clean_line = line.strip()
                            if clean_line:
                                tmp_lines.append(clean_line)

                    content_lines = []
                    for clean_txt in tmp_lines:
                        if clean_txt in ["REPLY", "MARK AS READ", "管理通知", "全部清除", "开启", "关闭", "•"]:
                            continue
                            
                        if clean_txt in ["Telegram", "Telegram Notifications"] and not seen_sender:
                            sender = clean_txt
                            seen_sender = True
                            continue
                            
                        # 过滤无关时间或短占位符
                        if re.match(r'^(\d{1,2}:\d{2}|\d+%|\d+月\d+日.*|.*周.*|今天|昨天|now|现在|\d+\s*分钟.*|.*new messages.*)$', clean_txt, re.IGNORECASE):
                            continue
                            
                        # 过滤掉常见的系统通知，增加输入键盘提示
                        if clean_txt in ["Android 系统", "配置实体键盘", "点按即可选择语言和布局", "LSPosed", "LSPosed 已加载", "USB调试已连接", "点按即可关闭USB调试", "更改键盘", "雷电输入法", "物理键盘"]:
                            continue
                            
                        content_lines.append(clean_txt)

                    # 使用提取出的核心内容进行去重以防止输入法通知或其他系统通知改变造成的刷屏
                    if not content_lines:
                        continue
                        
                    content_str = "\n".join(content_lines)
                    signature = hash(content_str)
                    
                    if signature not in self._seen_notifications:
                        self._seen_notifications.add(signature)
                        
                        self._log_info(index, f"发件人：{sender}")
                        self._log_info(index, "正文：")
                        for line in content_lines:
                            self._log_info(index, line)
                                
                        verify_code = None
                        
                        # 规则1: 发件人为Telegram或者Telegram Notifications 已经匹配
                        # 规则2: 验证码上面一行肯定用冒号结尾
                        # 规则3: 验证码肯定为固定的11位，不做其他限制
                        for i in range(len(content_lines) - 1):
                            current_line = content_lines[i].strip()
                            next_line = content_lines[i+1].strip()
                            
                            if current_line.endswith(':') or current_line.endswith('：'):
                                if len(next_line) == 11:
                                    verify_code = next_line
                                    break

                        if verify_code:
                            self._log_info(index, "识别为官方验证码消息")
                            self._log_info(index, f"验证码为：{verify_code}")
                            break

            if verify_code:
                break
            time.sleep(5)
            
        if not verify_code:
            self._log_error(index, "获取验证码超时或未找到，任务终止。")
            return False
            
        self._log_info(index, "返回浏览器页面输入验证码...")
        
        edit_texts = self.d(className="android.widget.EditText")
        if edit_texts.count > 0:
            # 同样通常取最后一个
            pwd_box = edit_texts[edit_texts.count - 1]
        else:
            self._log_error(index, "页面中找不到验证码的输入框。")
            return False

        pwd_box.click()
        time.sleep(1)
        pwd_box.set_text(verify_code)
        time.sleep(2)
        
        # 向下滑动页面，确保 Sign In 按钮可见
        self.d.swipe(0.5, 0.7, 0.5, 0.3)
        time.sleep(1)
        
        sign_in_btn = self.d(text="Sign In", className="android.widget.Button")
        if not sign_in_btn.exists:
             sign_in_btn = self.d(className="android.widget.Button", textContains="Sign In")
             if not sign_in_btn.exists:
                 self._log_error(index, "未找到 Sign In 按钮！")
                 return False
                 
        self._log_info(index, "点击 Sign In...")
        sign_in_btn.click()
        time.sleep(5)
        
        api_dev_link = self.d(text="API development tools")
        if not api_dev_link.wait(timeout=15.0):
             self._log_error(index, "未能找到 API development tools 链接。可能登录失败或未进入主页。")
             return False
             
        self._log_info(index, "进入 API development tools...")
        api_dev_link.click()
        time.sleep(5)
        
        if self.d(textContains="App api_id:").exists or self.d(textContains="App api_id").exists:
             self._log_info(index, "检测到已经在该账号上分配过 API。尝试直接提取...")
             return self.extract_and_save_api(index, phone_number)
        elif self.d(text="Create new application").exists or self.d(textContains="Create new application").exists:
             self._log_info(index, "准备创建新应用...")
             
             while True:
                  app_title_text = self.get_api_app_name(index)
                  if not app_title_text:
                      self._log_error(index, "提取不到预设名称（可能文件已空或者不存在）。返回桌面，流程终止。")
                      self._save_account_data(index, phone_number, "", "", "名称不足", "未完成API申请")
                      self.d.press("home")
                      return False
                  
                  content_text = app_title_text
                  
                  self._log_info(index, f"统一使用名称填写表单: {content_text}")

                  try:
                      app_title_lbl = self.d(text="App title:")
                      if app_title_lbl.exists:
                          self._log_info(index, "填写 App title...")
                          app_title_input = app_title_lbl.down(className="android.widget.EditText")
                          app_title_input.click()
                          time.sleep(0.5)
                          app_title_input.set_text(content_text)
                          time.sleep(1)
                  except Exception as e:
                      self._log_error(index, f"填写 App title 出错: {e}")
    
                  try:
                      short_name_lbl = self.d(text="Short name:")
                      if short_name_lbl.exists:
                          self._log_info(index, "填写 Short name...")
                          short_name_input = short_name_lbl.down(className="android.widget.EditText")
                          short_name_input.click()
                          time.sleep(0.5)
                          short_name_input.set_text(content_text)
                          time.sleep(1)
                  except Exception as e:
                      self._log_error(index, f"填写 Short name 出错: {e}")
    
                  self.d.swipe(0.5, 0.7, 0.5, 0.3)
                  time.sleep(1)
                  
                  self._log_info(index, "从标题 Platform 中点击选择 Android...")
                  try:
                      platform_android = self.d(text="Android")
                      if platform_android.exists:
                          platform_android.click()
                      time.sleep(1)
                  except Exception as e:
                      self._log_error(index, f"选择 Platform 出错: {e}")
    
                  self.d.swipe(0.5, 0.7, 0.5, 0.3)
                  time.sleep(1)
    
                  try:
                      desc_lbl = self.d(text="Description:")
                      if not desc_lbl.exists:
                          self.d.swipe(0.5, 0.7, 0.5, 0.3)
                          time.sleep(1)
                          
                      if desc_lbl.exists:
                          self._log_info(index, "填写 Description...")
                          desc_input = desc_lbl.down(className="android.widget.EditText")
                          desc_input.click()
                          time.sleep(0.5)
                          desc_input.set_text(content_text)
                          time.sleep(1)
                  except Exception as e:
                      self._log_error(index, f"填写 Description 出错: {e}")
    
                  self.d.swipe(0.5, 0.7, 0.5, 0.3)
                  time.sleep(1)
    
                  create_btn = self.d(text="Create application", className="android.widget.Button")
                  if not create_btn.exists:
                      create_btn = self.d(text="Create application")
    
                  if create_btn.exists:
                      create_btn.click()
                      self._log_info(index, "点击 Create application 等待创建...")
                      time.sleep(5)
                      
                      if self.d(textContains="App api_id:").exists or self.d(textContains="App api_id").exists:
                          return self.extract_and_save_api(index, phone_number)
                      else:
                          self._log_error(index, f"名称 {content_text} 可能被占用或报错，返回顶部重新尝试提取一个新名称...")
                          self.d(scrollable=True).scroll.toBeginning()
                          time.sleep(1)
                          continue
                  else:
                      self._log_error(index, "未找到 Create application 按钮！")
                      return False
        else:
             self._log_error(index, "无法判定当前页面状态（既没有已有API信息，也没有创建表单）。")
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
            save_path = None
            if self.config and getattr(self.config, 'get', None):
                save_path = self.config.get('save_data_path')
                
            if not save_path:
                self._log_info(index, "未检测到配置存储路径，自动保存在项目默认目录。")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.dirname(os.path.dirname(current_dir))

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
            save_path = None
            if self.config and getattr(self.config, 'get', None):
                save_path = self.config.get('save_data_path')
                
            if not save_path:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.dirname(os.path.dirname(current_dir))

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
