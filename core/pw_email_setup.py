import os
import sys

# 允许直接运行该脚本时能找到 core 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.tg_password_setup import TGPasswordSetup

class PwEmailSetupManager:
    def __init__(self, logger, config, lock):
        self.logger = logger
        self.config = config
        self.lock = lock

    def get_account_from_file_thread_safe(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return None, None
            
        with self.lock:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                if not lines:
                    return None, None
                    
                first_line = lines[0].strip()
                remaining_lines = lines[1:]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(remaining_lines)
                
                used_file = file_path + ".used.txt"
                with open(used_file, 'a', encoding='utf-8') as f:
                    f.write(first_line + "\n")
                    
                for sep in [',', ':', '----', ' ']:
                    if sep in first_line:
                        parts = first_line.split(sep, 1)
                        return parts[0].strip(), parts[1].strip()
                return first_line.strip(), None
            except Exception as e:
                self.logger.error(f"安全读取邮箱列表文件失败: {str(e)}", "设置密码")
                return None, None

    def execute_setup(self, index, phone_number):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        
        email_file = self.config.get('email_file_path')
        if not os.path.isabs(email_file):
            email_file = os.path.join(root_dir, email_file)
            
        if not email_file:
            self.logger.error(f"[{index}] 未配置邮箱列表文件，无法进行密码与邮箱绑定。", "设置密码")
            return False

        email, password = self.get_account_from_file_thread_safe(email_file)
        if not email or not password:
            self.logger.error(f"[{index}] 无法从文件 {email_file} 获取有效邮箱及密码，可能数量不足。", "设置密码")
            return False
            
        self.logger.info(f"[{index}] 已成功获取分配的邮箱: {email}", "流水线")
        
        setup_flow = TGPasswordSetup(logger=self.logger)
        try:
            success = setup_flow.run(index, account_file=email_file, email=email, password=password)
            if success:
                self.logger.info(f"[{index}] 账号密码与邮箱绑定流程全部完成！", "流水线")
                self._save_account_data(index, phone_number, email, password)
                return True
            else:
                self.logger.error(f"[{index}] 设置密码与绑定邮箱流程失败。", "设置密码")
                return False
        except Exception as e:
            self.logger.error(f"[{index}] 设置密码模块执行发生异常: {str(e)}", "设置密码")
            return False

    def _save_account_data(self, index, phone_number, email, password):
        try:
            save_path = self.config.get('account_data_path')
            if not save_path:
                self.logger.warning(f"[{index}] 未配置'账号资料'存放路径，请在界面设置。账号密码信息将保存在默认路径中。", "系统配置")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "data", "账号资料")
                
            if not os.path.isabs(save_path):
                current_dir = os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), save_path)

            if not os.path.exists(save_path):
                os.makedirs(save_path)
            
            clean_phone = str(phone_number).strip()
            if clean_phone and not clean_phone.startswith('+'):
                clean_phone = '+' + clean_phone
                
            phone_folder = os.path.join(save_path, clean_phone)
            if not os.path.exists(phone_folder):
                os.makedirs(phone_folder)
                
            txt_path = os.path.join(phone_folder, f"{clean_phone}.txt")
            with open(txt_path, 'a', encoding='utf-8') as f:
                f.write(f"邮箱：{email}：{password}\n")
                
            self.logger.info(f"[{index}] 已成功将账号信息保存至: {txt_path}", "流水线")
        except Exception as e:
            self.logger.error(f"[{index}] 保存账号资料文件时发生异常: {e}", "流水线")
