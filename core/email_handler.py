import os
import re
import time
import random
import logging
import uiautomator2 as u2

class EmailHandler:
    def __init__(self, device_id):
        self.d = u2.connect(device_id)
        self.d.implicitly_wait(10)

    def get_account_from_file(self, file_path):
        if not os.path.exists(file_path):
            logging.error(f"账号文件不存在: {file_path}")
            return None, None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return None, None
                
            first_line = lines[0].strip()
            remaining_lines = lines[1:]
            
            # 重新写入文件（删除已读取的行）
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(remaining_lines)
            
            # 追加到已使用记录中
            used_file = file_path + ".used.txt"
            with open(used_file, 'a', encoding='utf-8') as f:
                f.write(first_line + "\n")
                
            for sep in [',', ':', '----', ' ']:
                if sep in first_line:
                    parts = first_line.split(sep, 1)
                    return parts[0].strip(), parts[1].strip()
            return first_line, ""
        except Exception as e:
            logging.error(f"读取账号文件失败: {e}")
            return None, None

    def login_via_browser(self, email, password):
        logging.info("1. 回到桌面并打开 via 浏览器...")
        self.d.press("home")
        time.sleep(2)
        self.d.app_start("mark.via", stop=True)
        time.sleep(3)

        if self.d(text="同意并继续").exists:
            logging.info("检测到许可协议，点击“同意并继续”")
            self.d(text="同意并继续").click()
            time.sleep(2)

        logging.info("2. 检查并导航至主页...")
        search_box = self.d(className="android.widget.EditText")
        
        if not search_box.exists:
            home_btn = self.d(description="主页")
            if home_btn.exists:
                home_btn.click()
            else:
                width, height = self.d.window_size()
                self.d.click(width // 2, height - 50)
            time.sleep(2)

        logging.info("3. 搜索框输入 url...")
        if search_box.wait(timeout=5):
            search_box.click()
            time.sleep(1)
            search_box.set_text("https://account.proton.me/mail")
            self.d.press("enter")
        else:
            logging.error("未找到搜索输入框！")
            return False

        logging.info("等待登录页面加载...")
        edit_texts = self.d(className="android.widget.EditText")
        if not edit_texts.wait(timeout=30):
            logging.error("网页加载太慢或没有出现账号密码输入框！")
            return False

        delay1 = random.uniform(3, 5)
        time.sleep(delay1)

        logging.info("4. 输入账号与密码...")
        if edit_texts.count >= 2:
            edit_texts[0].click()
            edit_texts[0].set_text(email)
            time.sleep(random.uniform(3, 5))
            
            edit_texts[1].click()
            edit_texts[1].set_text(password)
        else:
            e_input = self.d(textContains="邮箱").sibling(className="android.widget.EditText")
            if e_input.exists:
                e_input.set_text(email)
            time.sleep(random.uniform(3, 5))
            
            p_input = self.d(text="密码").sibling(className="android.widget.EditText")
            if p_input.exists:
                p_input.set_text(password)

        checkbox = self.d(className="android.widget.CheckBox")
        if checkbox.exists:
            checkbox.click()
        elif self.d(text="保持登录状态").exists:
            self.d(text="保持登录状态").click()

        login_btn = self.d(text="登录", className="android.widget.Button")
        if login_btn.exists:
            login_btn.click()
        else:
            self.d(textContains="登录").click()

        if self.d(text="保存密码").wait(timeout=15):
            self.d(text="保存密码").click()

        if self.d(textContains="Loading Proton").wait(timeout=10):
            self.d(textContains="Loading Proton").wait_gone(timeout=30)
            
        retry_count = 0
        while retry_count < 5:
            if self.d(textContains="收件箱").wait(timeout=15) or self.d(textContains="Inbox").wait(timeout=15) or self.d(descriptionContains="收件箱").wait(timeout=5):
                logging.info("成功登录邮箱，等待紧接收件箱加载...")
                time.sleep(5)
                return True
            else:
                retry_count += 1
                logging.info(f"等待收件箱加载中，重试第 {retry_count} 次...")
                time.sleep(5)
                
        logging.warning("登录可能失败，未找到收件箱标志。")
        return False

    def _get_webview_texts(self):
        try:
            import xml.etree.ElementTree as ET
            xml_str = self.d.dump_hierarchy()
            root = ET.fromstring(xml_str.encode('utf-8'))
            
            webview_node = None
            for elem in root.iter():
                if 'WebView' in elem.attrib.get('class', '') or 'WebView' in elem.attrib.get('className', ''):
                    webview_node = elem
                    break
            
            target_root = webview_node if webview_node is not None else root
            texts = []
            for elem in target_root.iter():
                t = elem.attrib.get('text', '').strip()
                desc = elem.attrib.get('content-desc', '').strip()
                val = t if t else desc
                if val and val not in ["网页后退", "网页前进", "主页", "菜单"]:
                    texts.append(val)
            return texts
        except Exception as e:
            return []

    def print_latest_target_email(self, platform_name="Telegram", target_email="noreply@telegram.org"):
        logging.info(f"正在获取目标邮箱的所有邮件 (平台={platform_name}, 发件人={target_email})...")
        time.sleep(3)
        texts = self._get_webview_texts()
        match_idx = -1
        p_name = platform_name.lower()
        t_email = target_email.lower()
        
        historical_count = 0
        for i, t in enumerate(texts):
            if p_name in t.lower() or t_email in t.lower():
                historical_count += 1
                if match_idx == -1:
                    match_idx = i
                    
        if match_idx == -1:
            logging.info(f"未找到包含 {platform_name} 或 {target_email} 的历史邮件。")
            print("\n==================================")
            print(f"发件人：    {target_email or platform_name}")
            print(f"历史邮件数：{historical_count}")
            print(f"最新邮件内容：\n无")
            print(f"验证码：    无")
            print("==================================\n")
            return
            
        target_text = texts[match_idx]
        el = self.d(text=target_text)
        if not el.exists:
            el = self.d(description=target_text)
            
        if el.exists:
            if getattr(el, 'count', 0) > 0:
                el[0].click()
            else:
                el.click()
            time.sleep(5)
            
            email_texts = self._get_webview_texts()
            ignore_keywords = ["收件箱", "回复", "全部回复", "转发", "标记为未读", "移动到", "删除", 
                               " Inbox ", " Reply ", " Forward ", " Archive ", " Trash ", "loading", "Loading",
                               "站点信息", "刷新网页", "通知", "Proton Mail", "在应用程序上运行更快", "私密、快速、有序", 
                               "下载", "工具栏", "更多", "搜索", "升级账户", "选择所有邮件", "会话排序", "全封闭加密存储", "显示详情", "更多选项", 
                               "未发现跟踪器,无需净化链接", "星标邮件, 关闭", "上一步", "标为未读", "移至回收站", "移至归档", "标为垃圾邮件"]
            
            clean_texts = []
            for txt in email_texts:
                if txt not in clean_texts:
                    skip = False
                    for ig in ignore_keywords:
                        if ig.lower() in txt.lower():
                            skip = True
                            break
                    if not skip and len(txt) > 0:
                        clean_texts.append(txt)
                        
            full_content = "\n".join(clean_texts)
            code_pattern = r"(?i)code.*?(\d{4,8})"
            match = re.search(code_pattern, full_content)
            code = "无"
            if match:
                code = match.group(1)
            else:
                fallback_match = re.search(r"\b(\d{5,6})\b", full_content)
                if fallback_match:
                    code = fallback_match.group(1)
                    
            print("\n==================================")
            print(f"发件人：    {target_email or platform_name}")
            print(f"历史邮件数：{historical_count}")
            print(f"最新邮件内容：\n{full_content}")
            print(f"验证码：    {code}")
            print("==================================\n")
            
            time.sleep(2)
            self.d.press("back")
            time.sleep(3)
        else:
            logging.error("未能定位到该邮件组件进行点击！")

    def extract_verification_code(self, platform_name="Telegram", target_email="noreply@telegram.org", max_wait_sec=120):
        logging.info(f"打开 Via 浏览器提取验证码 (平台={platform_name}, 发件人={target_email})...")
        self.d.app_start("mark.via")
        time.sleep(5)
        
        start_time = time.time()
        p_name = platform_name.lower()
        t_email = target_email.lower()
        processed_contents = set()
        
        while time.time() - start_time < max_wait_sec:
            # 刷新页面
            width, height = self.d.window_size()
            self.d.swipe(width // 2, height // 3, width // 2, height // 3 + 600, 0.5)
            time.sleep(8)
            
            texts = self._get_webview_texts()
            match_idx = -1
            historical_count = 0
            
            for i, t in enumerate(texts):
                if p_name in t.lower() or t_email in t.lower():
                    historical_count += 1
                    if match_idx == -1:
                        match_idx = i
                    
            if match_idx != -1:
                target_text = texts[match_idx]
                el = self.d(text=target_text)
                if not el.exists:
                    el = self.d(description=target_text)
                    
                if el.exists:
                    if getattr(el, 'count', 0) > 0:
                        el[0].click()
                    else:
                        el.click()
                        
                    time.sleep(5)
                    email_texts = self._get_webview_texts()
                    
                    ignore_keywords = ["收件箱", "回复", "全部回复", "转发", "标记为未读", "移动到", "删除", 
                                       " Inbox ", " Reply ", " Forward ", " Archive ", " Trash ", "loading", "Loading",
                                       "站点信息", "刷新网页", "通知", "Proton Mail", "在应用程序上运行更快", "私密、快速、有序", 
                                       "下载", "工具栏", "更多", "搜索", "升级账户", "选择所有邮件", "会话排序", "全封闭加密存储", "显示详情", "更多选项", 
                                       "未发现跟踪器,无需净化链接", "星标邮件, 关闭", "上一步", "标为未读", "移至回收站", "移至归档", "标为垃圾邮件"]
                    
                    clean_texts = []
                    for txt in email_texts:
                        if txt not in clean_texts:
                            skip = False
                            for ig in ignore_keywords:
                                if ig.lower() in txt.lower():
                                    skip = True
                                    break
                            if not skip and len(txt) > 0:
                                clean_texts.append(txt)
                                
                    full_content = "\n".join(clean_texts)
                    
                    code_pattern = r"(?i)code.*?(\d{4,8})"
                    match = re.search(code_pattern, full_content)
                    code = None
                    
                    if match:
                        code = match.group(1)
                    else:
                        fallback_match = re.search(r"\b(\d{5,6})\b", full_content)
                        if fallback_match:
                            code = fallback_match.group(1)
                            
                    print("\n==================================")
                    print(f"发件人：    {target_email or platform_name}")
                    print(f"历史邮件数：{historical_count}")
                    print(f"最新邮件内容：\n{full_content}")
                    print(f"验证码：    {code if code else '无'}")
                    print("==================================\n")
                            
                    if code:
                        logging.info(f"提取到验证码: {code}")
                        self.d.press("back")
                        return code
                        
                    time.sleep(2)
                    self.d.press("back")
                    time.sleep(3)
            else:
                logging.info("暂未发现目标邮件，继续等待...")
                
        logging.error("提取验证码超时。")
        return None
