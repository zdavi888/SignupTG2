import uiautomator2 as u2
import time
import re
import logging
import os
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EmailExtractor:
    def __init__(self, device_id=None):
        if device_id:
            self.d = u2.connect(device_id)
        else:
            self.d = u2.connect()
        self.d.implicitly_wait(10)

    def read_account(self, file_path):
        if not os.path.exists(file_path):
            logging.error(f"账号文件不存在: {file_path}")
            return None, None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return None, None
                for sep in [',', ':', '----', ' ']:
                    if sep in content:
                        parts = content.split(sep, 1)
                        return parts[0].strip(), parts[1].strip()
                return None, None
        except Exception as e:
            logging.error(f"读取账号文件失败: {e}")
            return None, None

    def execute(self, account_file, platform_name, target_email=""):
        email, password = self.read_account(account_file)
        if not email or not password:
            logging.error("无法获取邮箱账号或密码！")
            return None

        logging.info("1. 打开 via 浏览器...")
        self.d.app_start("mark.via", stop=True) # stop=True 确保冷启动，流程更稳定
        time.sleep(3)

        # 捕获 图1 的 同意并继续
        if self.d(text="同意并继续").exists:
            logging.info("检测到许可协议，点击“同意并继续”")
            self.d(text="同意并继续").click()
            time.sleep(2)

        logging.info("2. 检查并导航至主页...")
        search_box = self.d(className="android.widget.EditText")
        
        # 如果当前不存在搜索框，说明不在图3（主页），则需要点击底部 home 图标
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
            return None

        logging.info("等待登录页面加载...")
        edit_texts = self.d(className="android.widget.EditText")
        if not edit_texts.wait(timeout=30):
            logging.error("网页加载太慢或没有出现账号密码输入框！")
            return None

        delay1 = random.uniform(3, 5)
        logging.info(f"页面出来后，随机延时 {delay1:.2f} 秒...")
        time.sleep(delay1)

        logging.info("4. 输入账号与密码...")
        if edit_texts.count >= 2:
            edit_texts[0].click()
            edit_texts[0].set_text(email)
            
            delay2 = random.uniform(3, 5)
            logging.info(f"输入账号后，随机延时 {delay2:.2f} 秒...")
            time.sleep(delay2)
            
            edit_texts[1].click()
            edit_texts[1].set_text(password)
        else:
            logging.warning("未检测到预期的两个输入框布局，尝试依据文本旁边的 EditText 查找输入框...")
            e_input = self.d(textContains="邮箱").sibling(className="android.widget.EditText")
            if e_input.exists:
                e_input.set_text(email)
                
            delay2 = random.uniform(3, 5)
            logging.info(f"输入账号后，随机延时 {delay2:.2f} 秒...")
            time.sleep(delay2)
            
            p_input = self.d(text="密码").sibling(className="android.widget.EditText")
            if p_input.exists:
                p_input.set_text(password)

        logging.info("勾选保持登录状态...")
        checkbox = self.d(className="android.widget.CheckBox")
        if checkbox.exists:
            checkbox.click()
        elif self.d(text="保持登录状态").exists:
            self.d(text="保持登录状态").click()

        logging.info("点击登录...")
        login_btn = self.d(text="登录", className="android.widget.Button")
        if login_btn.exists:
            login_btn.click()
        else:
            self.d(textContains="登录").click()

        logging.info("5. 等待页面跳转并处理保存密码弹窗...")
        if self.d(text="保存密码").wait(timeout=15):
            logging.info("已点击保存密码")
            self.d(text="保存密码").click()

        logging.info("6. 等待进入收件箱...")
        # Proton 登录时会出现Loading... 等待它消失
        if self.d(textContains="Loading Proton").wait(timeout=10):
            self.d(textContains="Loading Proton").wait_gone(timeout=30)
            
        if self.d(textContains="收件箱").wait(timeout=30) or self.d(textContains="Inbox").wait(timeout=30):
            logging.info("成功检测到收件箱标志！等待 10 秒确保加载完成...")
            time.sleep(10)
        else:
            logging.warning("未能通过特定文本确认页面加载，继续往下尝试查找邮件...")

        logging.info(f"7. 开始持续提取目标邮件 (条件: 平台={platform_name}, 发件人={target_email})...")
        processed_contents = set()
        last_clicked_signature = None
        
        def get_webview_texts():
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
                    if val and val not in ["网页后退", "网页前进", "主页", "菜单", "Android 系统通知：配置实体键盘", "WLAN 信号满格。", "手机信号满格。", "正在充电，已完成 100%。"]:
                        texts.append(val)
                return texts
            except Exception as e:
                logging.error(f"解析 XML 失败: {e}")
                return []

        is_first_check = True

        while True:
            if not is_first_check:
                logging.info("等待 15 秒后重新检测是否有新邮件...")
                time.sleep(15)
                # 简单下拉刷新
                width, height = self.d.window_size()
                self.d.swipe(width // 2, height // 3, width // 2, height // 3 + 600, 0.5)
                time.sleep(8)
            
            texts = get_webview_texts()
            
            historical_count = 0
            match_idx = -1
            match_sig = ""
            
            p_name = platform_name.lower() if platform_name else ""
            t_email = target_email.lower() if target_email else ""
            
            # 从列表中寻找符合目标的邮件特征
            for i, t in enumerate(texts):
                is_match = False
                if p_name and p_name in t.lower():
                    is_match = True
                elif t_email and t_email in t.lower():
                    is_match = True
                    
                if is_match:
                    historical_count += 1
                    if match_idx == -1:
                        match_idx = i
                        # 用目标文本和之后的一段文本作为简单的列表层级签名
                        sub_sig = t
                        if i + 1 < len(texts):
                            sub_sig += "_" + texts[i+1]
                        match_sig = sub_sig
            
            # 如果没找到，或者是第一轮没找到，直接跳过
            if match_idx == -1:
                if is_first_check:
                    logging.info(f"未找到包含 {platform_name or target_email} 的历史邮件。")
                is_first_check = False
                continue

            # 如果找到了且这个签名和上一次点击的不同，说明可能有新邮件（或者初次启动）
            if match_sig != last_clicked_signature or is_first_check:
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
                    
                    # 进去之后提取邮件详情
                    email_texts = get_webview_texts()
                    
                    # 过滤无用信息
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
                    
                    import hashlib
                    content_hash = hashlib.md5(full_content.encode('utf-8')).hexdigest()
                    
                    # 如果内容是新的，则打印
                    if content_hash not in processed_contents:
                        processed_contents.add(content_hash)
                        
                        code_pattern = r"(?i)code.*?(\d{4,8})"
                        match = re.search(code_pattern, full_content)
                        code = "无"
                        
                        if match:
                            code = match.group(1)
                        else:
                            fallback_match = re.search(r"\b(\d{5,6})\b", full_content)
                            if fallback_match:
                                code = fallback_match.group(1)
                                
                        sender_display = target_email if target_email else platform_name
                        print("\n==================================")
                        print(f"发件人：    {sender_display}")
                        print(f"历史邮件数：{historical_count}")
                        print(f"最新邮件内容：\n{full_content}")
                        print(f"验证码：    {code}")
                        print("==================================\n")
                        
                        last_clicked_signature = match_sig
                    else:
                        logging.info("打开的邮件已被处理过，忽略。")
                        # 即使内容重复，也更新签名防止反复点击
                        last_clicked_signature = match_sig
                    
                    time.sleep(2)
                    self.d.press("back")
                    time.sleep(3)
                else:
                    logging.error("未能定位到该邮件组件进行点击！")
                    
            is_first_check = False

if __name__ == "__main__":
    extractor = EmailExtractor()
    pass
