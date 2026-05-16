import os
import re
import time
import logging
import random
import uiautomator2 as u2
from core.email_handler import EmailHandler

class TGPasswordSetup:
    def __init__(self, logger):
        self.logger = logger
        self.email_handler = None
        self.d = None

    def run(self, index, account_file="account.txt", email=None, password=None):
        port = 5555 + index * 2
        device_addr = f"127.0.0.1:{port}"
        
        try:
            self.d = u2.connect(device_addr)
            self.d.implicitly_wait(8.0)
            self.email_handler = EmailHandler(device_id=device_addr)
        except Exception as e:
            self.logger.error(f"[{index}] 无法连接设备: {e}")
            return False

        if email is None or password is None:
            if os.path.isabs(account_file):
                account_path = account_file
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                account_path = os.path.join(current_dir, "..", account_file)
            
            email, password = self.email_handler.get_account_from_file(account_path)
            
        if not email or not password:
            self.logger.error(f"[{index}] 获取邮箱账号失败，请检查 {account_file}。")
            return False

        self.logger.info(f"[{index}] 开始执行设置密码并绑定邮箱流程。准备使用邮箱: {email}")

        # 1. 登录邮箱
        self.logger.info(f"[{index}] 步骤一：登录邮箱")
        self.d.press("home")
        time.sleep(2)
        login_success = self.email_handler.login_via_browser(email, password)
        if not login_success:
            self.logger.error(f"[{index}] 登录邮箱失败，中止流程。")
            return False

        # 登录成功后，检测一次现有目标邮件并按格式打印出来 (用户要求)
        self.logger.info(f"[{index}] 登录成功，读取最新一封包含 Telegram 的目标邮件内容...")
        self.email_handler.print_latest_target_email(platform_name="Telegram", target_email="noreply@telegram.org")

        self.logger.info(f"[{index}] 邮件读取完成，先回到桌面。")
        self.d.press("home")
        time.sleep(2)

        wait_time = random.uniform(10, 15)
        self.logger.info(f"[{index}] 正在桌面等待 {wait_time:.1f} 秒，然后打开 Telegram...")
        time.sleep(wait_time)

        # 2. 打开 Telegram
        self.logger.info(f"[{index}] 步骤二：尝试通过多种方式打开 Telegram")
        
        # 尝试通过多种方式打开 Telegram
        if self.d(text="Telegram").exists:
            self.logger.info(f"[{index}] 桌面找到 Telegram 图标，点击启动...")
            self.d(text="Telegram").click()
            time.sleep(5)
            
        # 等待后检查是否成功进入
        current_app = self.d.app_current()
        if current_app and current_app.get("package") == "org.telegram.messenger":
            self.logger.info(f"[{index}] 图标启动方案成功，已处于 Telegram 界面")
        else:
            self.logger.info(f"[{index}] 兜底：尝试使用标准方式唤醒 Telegram 应用...")
            self.d.app_start("org.telegram.messenger")
            time.sleep(2)
            self.d.shell("monkey -p org.telegram.messenger -c android.intent.category.LAUNCHER 1")
            time.sleep(5)
            
            # 确保在前台，如果是通过 monkey 启动可能没彻底到前台
            current_app = self.d.app_current()
            if current_app and current_app.get("package") != "org.telegram.messenger":
                self.logger.warning(f"[{index}] 当前在前台的应用是 {current_app.get('package')}，再次尝试 app_start 打开 Telegram...")
                self.d.app_start("org.telegram.messenger")
                time.sleep(5)

        # 增加弹窗防御处理
        self._handle_telegram_popups(index)

        # 点击 Profile
        self.logger.info(f"[{index}] 尝试点击右下角 Profile")
        if self.d(textMatches="(?i).*profile.*").wait(timeout=10):
            self.d(textMatches="(?i).*profile.*")[-1].click()
        elif self.d(descriptionMatches="(?i).*profile.*").exists:
            self.d(descriptionMatches="(?i).*profile.*")[-1].click()
        else:
            self.logger.warning(f"[{index}] 根据文本无法找到 Profile，尝试按固定坐标点击右下角...")
            w, h = self.d.window_size()
            self.d.click(w * 0.85, h * 0.95)
        time.sleep(2)

        # 提取手机号作为密码
        phone_texts = self.d(textContains="+")
        phone_num = ""
        for pt in phone_texts:
            t = pt.get_text()
            # 简单匹配是否有多个连着的数字作为手机号
            if re.search(r'\d{4}', t):
                phone_num = re.sub(r'\D', '', t)
                break
        
        if not phone_num:
            self.logger.warning(f"[{index}] 未能从界面提取到手机号，将尝试使用备用默认密码或截取其他位置。")
            phone_num = "12345678"  # 备用密码防止卡死
        else:
            self.logger.info(f"[{index}] 提取到手机号作为密码: {phone_num}")
            
        # 点击 Settings (图2)
        self.logger.info(f"[{index}] 点击 Settings")
        time.sleep(random.uniform(3, 10))
        if self.d(textMatches="(?i).*settings.*").wait(timeout=10):
            self.d(textMatches="(?i).*settings.*")[-1].click()  # 点最后(最下)一个出现的Settings
        else:
            self.logger.error(f"[{index}] 找不到 Settings 按钮")
            return False

        # 点击 Privacy & Security (图3)
        self.logger.info(f"[{index}] 点击 Privacy and Security")
        time.sleep(random.uniform(3, 10))
        if self.d(textMatches="(?i).*privacy.*").wait(timeout=10):
            self.d(textMatches="(?i).*privacy.*")[0].click()
        else:
            self.logger.error(f"[{index}] 找不到 Privacy and Security")
            return False

        # 点击 Two-Step Verification (图4)
        self.logger.info(f"[{index}] 点击 Two-Step Verification")
        time.sleep(random.uniform(3, 10))
        if self.d(textMatches="(?i).*two-step.*").wait(timeout=10):
            self.d(textMatches="(?i).*two-step.*")[0].click()
        else:
            self.logger.error(f"[{index}] 找不到 Two-Step Verification")
            return False

        # 点击 Set Password (图5)
        self.logger.info(f"[{index}] 点击 Set Password")
        time.sleep(random.uniform(3, 10))
        if self.d(textMatches="(?i).*set password.*").wait(timeout=10):
            self.d(textMatches="(?i).*set password.*")[0].click()
        elif self.d(textMatches="(?i).*set.*").exists:
             self.d(textMatches="(?i).*set.*")[-1].click()
        else:
            # 如果是已经开启密码，这里可能是 Change Password，直接通过
            if self.d(textMatches="(?i).*change password.*").exists:
                self.logger.info(f"[{index}] 已经设置过两步验证密码，流程结束。")
                return True
            else:
                self.logger.error(f"[{index}] 找不到 Set Password 按钮")
                return False

        # 输入密码并下一步 (图6)
        self.logger.info(f"[{index}] 等待 Create a Password 页面显示")
        time.sleep(random.uniform(3, 10))
        # 强制核对页面是否加载
        if not self.d(textMatches="(?i).*password.*").wait(timeout=15):
             self.logger.error(f"[{index}] 未能确认显示 Create a Password 页面，流程终止。")
             return False
             
        self.logger.info(f"[{index}] 输入两步验证密码")
        edit_texts = self.d(className="android.widget.EditText")
        if edit_texts.exists:
            edit_texts[0].set_text(phone_num)
        else:
             self.d.send_keys(phone_num)
        time.sleep(random.uniform(2, 4))
        
        # 循环点击下一步直至界面变化
        page_reached = False
        for attempt in range(3):
            self._click_next_arrow()
            self.logger.info(f"[{index}] 点击了下一步箭头，等待 Re-enter password 页面...")
            if self.d(textMatches="(?i).*re-enter.*").wait(timeout=8):
                page_reached = True
                break
                
        if not page_reached:
            self.logger.error(f"[{index}] 无法进入 Re-enter password 页面，流程终止")
            return False
        
        # 已经进入重新输入密码界面
        self.logger.info(f"[{index}] 确认已进入重新输入密码界面，开始输入")
        time.sleep(random.uniform(1, 3))
        edit_texts = self.d(className="android.widget.EditText")
        if edit_texts.exists:
            edit_texts[0].set_text(phone_num)
        else:
            self.d.send_keys(phone_num)
        time.sleep(random.uniform(2, 4))
        
        # 循环点击下一步直至界面变化
        page_reached = False
        for attempt in range(3):
            self._click_next_arrow()
            self.logger.info(f"[{index}] 点击了下一步箭头，等待 Password Hint 页面...")
            if self.d(textMatches="(?i).*hint.*").wait(timeout=8):
                page_reached = True
                break
                
        if not page_reached:
            self.logger.error(f"[{index}] 无法进入 Password Hint 页面，流程终止")
            return False

        # Password Hint 页面，直接跳过
        self.logger.info(f"[{index}] 遇到密码提示设置，直接跳过/下一步")
        time.sleep(random.uniform(2, 5))
        skip_btn = self.d(textMatches="(?i).*skip.*")
        if skip_btn.exists:
            skip_btn.click()
            # 跳过后等待 Email 页面
            if not self.d(textMatches="(?i).*email.*").wait(timeout=10):
                self.logger.error(f"[{index}] 点击 Skip 后未能进入 Recovery Email 页面，流程终止")
                return False
        else:
            page_reached = False
            for attempt in range(3):
                self._click_next_arrow()
                self.logger.info(f"[{index}] 点击了下一步箭头，等待 Recovery Email 页面...")
                if self.d(textMatches="(?i).*email.*").wait(timeout=8):
                    page_reached = True
                    break
            
            if not page_reached:
                self.logger.error(f"[{index}] 无法进入 Recovery Email 页面，流程终止")
                return False

        # 输入邮箱并下一步 (图7)
        self.logger.info(f"[{index}] 确认已进入恢复邮箱页面: Recovery Email")
        time.sleep(random.uniform(2, 5))
             
        self.logger.info(f"[{index}] 输入恢复邮箱: {email}")
        if self.d(className="android.widget.EditText").exists:
            self.d(className="android.widget.EditText")[0].set_text(email)
        else:
            self.d.send_keys(email)
        time.sleep(random.uniform(2, 4))
        
        page_reached = False
        for attempt in range(3):
            self._click_next_arrow()
            self.logger.info(f"[{index}] 点击了下一步箭头发送验证码请求...")
            if self.d(textMatches="(?i).*code.*").wait(timeout=8) or self.d(textMatches="(?i).*check your email.*").wait(timeout=8):
                page_reached = True
                break
                
        if not page_reached:
            self.logger.error(f"[{index}] 无法进入验证码输入界面，流程终止")
            return False

        self.logger.info(f"[{index}] 已发送验证码请求，等待验证码界面")
        time.sleep(random.uniform(3, 5))

        # 等待界面来到验证码输入 (图8)
        self.logger.info(f"[{index}] 前往 Via 浏览器提取验证码")
        verify_code = self.email_handler.extract_verification_code()
        
        if not verify_code:
            self.logger.error(f"[{index}] 未能提取到验证码，流程失败")
            return False

        # 切回 Telegram
        self.logger.info(f"[{index}] 回到桌面并重新打开 Telegram")
        self.d.press("home")
        time.sleep(1.5)
        
        if self.d(text="Telegram").exists:
            self.logger.info(f"[{index}] 桌面找到 Telegram 图标，点击启动...")
            self.d(text="Telegram").click()
            time.sleep(5)
            
        # 等待后检查是否成功进入 (由于键盘可能弹出，不要用 app_current()，用元素检查)
        if self.d(packageName="org.telegram.messenger").exists:
            self.logger.info(f"[{index}] 成功返回 Telegram 界面")
        else:
            self.logger.info(f"[{index}] 兜底：尝试使用标准方式唤醒 Telegram 应用...")
            self.d.app_start("org.telegram.messenger")
            time.sleep(5)
            
            if not self.d(packageName="org.telegram.messenger").exists:
                self.logger.warning(f"[{index}] 当前未处于 Telegram，尝试使用 monkey 唤醒...")
                self.d.shell("monkey -p org.telegram.messenger -c android.intent.category.LAUNCHER 1")
                time.sleep(3)
        
        # 输入验证码界面中会出现键盘，输入验证码不要粘贴，用在键盘中点数字的方式输入验证码
        self.logger.info(f"[{index}] 输入验证码: {verify_code}")
        # 点击第一个输入框确保焦点
        input_fields = self.d(className="android.widget.EditText")
        if input_fields.exists:
            try:
                input_fields[0].click()
                time.sleep(0.5)
            except:
                pass
                
        # 逐个数字模拟键盘按键输入
        for char in str(verify_code):
            if char.isdigit():
                keycode = int(char) + 7  # Android keycode: KEYCODE_0 is 7, KEYCODE_1 is 8...
                self.d.shell(f"input keyevent {keycode}")
                time.sleep(0.3)
        
        # 等待验证成功与 Return to Settings (图9.1/9.2)
        success = False
        start_wait = time.time()
        while time.time() - start_wait < 30:
            if self.d(textContains="Return").exists:
                success = True
                break
            time.sleep(2)
            
        if success:
            self.logger.info(f"[{index}] 密码与邮箱绑定成功！")
            self.d(textContains="Return").click()
            time.sleep(2)
        else:
            self.logger.error(f"[{index}] 输入验证码后未检测到成功提示")
            return False

        # 连续三次返回，回到主界面 (图10, 11, 12, 13)
        self.logger.info(f"[{index}] 连续返回至主界面")
        for _ in range(3):
            if self.d(description="Go back").exists:
                self.d(description="Go back").click()
            elif self.d(description="Navigate up").exists:
                self.d(description="Navigate up").click()
            else:
                self.d.press("back")
            time.sleep(1.5)

        # 点击 Chats
        self.logger.info(f"[{index}] 点击 Chats 选项卡")
        if self.d(text="Chats").exists:
            self.d(text="Chats")[-1].click()
            
        self.logger.info(f"[{index}] 设置密码与绑定邮箱流程全部完成！")
        return True

    def _click_next_arrow(self):
        # 1. 优先尝试直接匹配 Content-Description (方案三核心)
        target_descs = ["Next", "Continue", "Done", "Go to next", "Submit", "下一步", "继续"]
        try:
            for desc in target_descs:
                if self.d(descriptionMatches=f"(?i).*{desc}.*").exists:
                    self.d(descriptionMatches=f"(?i).*{desc}.*")[-1].click(timeout=2)
                    time.sleep(1.5)
                    return
        except Exception:
            pass

        # 2. 备选方案：Dump XML 找到位置在右下角且带有描述的可点击元素
        try:
            w, h = self.d.window_size()
            target = None
            max_y = 0
            
            # 获取所有可点击元素
            elems = self.d(clickable=True)
            for elem in elems:
                bounds = elem.info['bounds']
                right = bounds['right']
                bottom = bounds['bottom']
                
                # 下一步按钮通常在屏幕右侧且靠近底部区域
                if right > w * 0.6 and bottom > max_y and bottom > h * 0.5:
                    max_y = bottom
                    target = elem
                    
            if target:
                target.click()
            else:
                # 兜底坐标点击，部分机器右下角蓝色按钮大概在(0.88, 0.88)或(0.9, 0.9)
                self.d.click(w * 0.88, h * 0.88)
        except Exception:
            try:
                w, h = self.d.window_size()
                self.d.click(w * 0.88, h * 0.88)
            except:
                self.d.click(0.9, 0.9)

    def _handle_telegram_popups(self, index):
        """处理进入Telegram后可能出现的全局弹窗"""
        popups = ["Not now", "Not Now", "Later", "Cancel", "Close", "UPDATE", "以后再说", "取消", "关闭"]
        for p in popups:
            btn = self.d(textContains=p)
            if btn.exists:
                self.logger.info(f"[{index}] 拦截到 Telegram 弹窗，执行点击: {p}")
                btn[0].click()
                time.sleep(1)
