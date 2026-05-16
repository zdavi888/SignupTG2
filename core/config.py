import json
import os

CONFIG_FILE = "config.json"

class ConfigManager:
    def __init__(self):
        self.config = {
            "ld_path": "",
            "groups": {
                "默认分组": [] # group_name: [list of instance names/indices]
            },
            "hero_sms_api_key": "",
            "target_count": 10,
            "concurrency": 3,
            "sms_service": "telegram",
            "sms_country": "any",
            "sms_price": "default(min)",
            "enable_password_setup": True,
            "enable_get_api": False,
            "enable_get_session": False,
        }
        self.load_config()
        # Enforce fixed paths
        self.config["account_data_path"] = "data/账号资料"
        self.config["email_file_path"] = "data/Email列表.txt"
        self.config["proxy_file"] = "data/代理文件.txt"
        self.config["failed_video_path"] = "data/注册失败退款视频"
        self.config["success_video_path"] = "data/注册成功视频"
        self.config["api_app_preset"] = "data/API预设名称.txt"

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def set_ld_path(self, path):
        self.config["ld_path"] = path
        self.save_config()

    def get_ld_path(self):
        return self.config.get("ld_path", "")

    def get_groups(self):
        # Ensure 默认分组 group exists
        if "groups" not in self.config:
            self.config["groups"] = {"默认分组": []}
        if "默认分组" not in self.config["groups"]:
            # If Default exists, rename it to 默认分组
            if "Default" in self.config["groups"]:
                self.config["groups"]["默认分组"] = self.config["groups"].pop("Default")
            else:
                self.config["groups"]["默认分组"] = []
        return self.config["groups"]

    def set_proxy_file(self, path):
        self.config["proxy_file"] = path
        self.save_config()

    def get_proxy_file(self):
        return self.config.get("proxy_file", "data/代理文件.txt")

    def set_hero_sms_api_key(self, api_key):
        self.config["hero_sms_api_key"] = api_key
        self.save_config()

    def get_hero_sms_api_key(self):
        return self.config.get("hero_sms_api_key", "")

    def set_sms_fixed_services(self, val):
        self.config["sms_fixed_services"] = val
        self.save_config()

    def get_sms_fixed_services(self):
        return self.config.get("sms_fixed_services", "")

    def set_sms_fixed_countries(self, val):
        self.config["sms_fixed_countries"] = val
        self.save_config()

    def get_sms_fixed_countries(self):
        return self.config.get("sms_fixed_countries", "")

    def set_target_count(self, val):
        self.config["target_count"] = val
        self.save_config()

    def get_target_count(self):
        return self.config.get("target_count", 10)

    def set_concurrency(self, val):
        self.config["concurrency"] = val
        self.save_config()

    def get_concurrency(self):
        return self.config.get("concurrency", 3)

    def set_sms_service(self, val):
        self.config["sms_service"] = val
        self.save_config()

    def get_sms_service(self):
        return self.config.get("sms_service", "telegram")

    def set_sms_country(self, val):
        self.config["sms_country"] = val
        self.save_config()

    def get_sms_country(self):
        return self.config.get("sms_country", "any")

    def set_sms_price(self, val):
        self.config["sms_price"] = val
        self.save_config()

    def get_sms_price(self):
        return self.config.get("sms_price", "default(min)")

    def set_enable_password_setup(self, val):
        self.config["enable_password_setup"] = val
        self.save_config()

    def get_enable_password_setup(self):
        return self.config.get("enable_password_setup", True)

    def set_email_file_path(self, val):
        self.config["email_file_path"] = val
        self.save_config()

    def get_email_file_path(self):
        return self.config.get("email_file_path", "data/Email列表.txt")

    def set_failed_video_path(self, val):
        self.config["failed_video_path"] = val
        self.save_config()

    def get_failed_video_path(self):
        return self.config.get("failed_video_path", "data/注册失败退款视频")

    def get_success_video_path(self):
        return self.config.get("success_video_path", "data/注册成功视频")

    def set_account_data_path(self, val):
        self.config["account_data_path"] = val
        self.save_config()

    def get_account_data_path(self):
        return self.config.get("account_data_path", "data/账号资料")

    def set_enable_get_api(self, val):
        self.config["enable_get_api"] = val
        self.save_config()

    def get_enable_get_api(self):
        return self.config.get("enable_get_api", False)

    def set_enable_get_session(self, val):
        self.config["enable_get_session"] = val
        self.save_config()

    def get_enable_get_session(self):
        return self.config.get("enable_get_session", False)

    def get_api_app_preset(self):
        return self.config.get("api_app_preset", "data/API预设名称.txt")

    def set_api_names_file(self, val):
        self.config["api_names_file"] = val
        self.save_config()

    def get_api_names_file(self):
        return self.config.get("api_names_file", "")

    def add_group(self, group_name):
        groups = self.get_groups()
        if group_name not in groups:
            groups[group_name] = []
            self.save_config()
            return True
        return False

    def rename_group(self, old_name, new_name):
        if old_name == "Default" or old_name == "默认分组":
            return False
            
        groups = self.get_groups()
        if old_name in groups and new_name not in groups:
            groups[new_name] = groups.pop(old_name)
            self.save_config()
            return True
        return False

    def delete_group(self, group_name):
        if group_name == "Default" or group_name == "默认分组":
            return False
            
        groups = self.get_groups()
        if group_name in groups:
            del groups[group_name]
            self.save_config()
            return True
        return False

    def add_instance_to_group(self, group_name, instance_name):
        groups = self.get_groups()
        if group_name in groups:
            if instance_name not in groups[group_name]:
                groups[group_name].append(instance_name)
                self.save_config()
                return True
        return False

    def remove_instance_from_group(self, group_name, instance_name):
        groups = self.get_groups()
        if group_name in groups and instance_name in groups[group_name]:
            groups[group_name].remove(instance_name)
            self.save_config()
            return True
        return False
