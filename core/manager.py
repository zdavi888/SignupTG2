from .config import ConfigManager
from .logger import AppLogger
from .ldconsole import LDConsole
from .weiba import WeibaAutomation
import time

class AutomationManager:
    def __init__(self, logger: AppLogger):
        self.config = ConfigManager()
        self.logger = logger
        self.logger.manager = self
        self.console = None
        
        ld_path = self.config.get_ld_path()
        if ld_path:
            self.console = LDConsole(ld_path)

    def set_ld_path(self, path):
        self.config.set_ld_path(path)
        self.console = LDConsole(path)
        self.logger.info(f"保存雷电模拟器路径成功: {path}", status="成功")

    def _check_console(self):
        if not self.console:
            raise Exception("请先设置雷电模拟器路径！")

    def get_instances(self):
        self._check_console()
        return self.console.list2()

    def get_instance_name(self, index):
        self._check_console()
        for inst in self.console.list2():
            if str(inst['index']) == str(index):
                return inst['name']
        return str(index)

    def clone_instances(self, from_index, count, prefix="TG", target_group="默认分组"):
        self._check_console()
        self.logger.info(f"开始复制模拟器，源序号: {from_index}, 数量: {count}, 前缀: {prefix}", status="进行中")
        
        new_indices = []
        try:
            current_instances = self.console.list2()
            existing_names = [inf['name'] for inf in current_instances]
            
            idx = 1
            success_count = 0
            
            for _ in range(count):
                while f"{prefix}{idx}" in existing_names:
                    idx += 1
                
                new_name = f"{prefix}{idx}"
                self.logger.info(f"正在生成克隆体: {new_name}")
                
                self.console.copy(new_name, from_index)
                time.sleep(2)  
                
                latest_instances = self.console.list2()
                new_inst = next((x for x in latest_instances if x['name'] == new_name), None)
                if new_inst:
                    new_idx = new_inst['index']
                    new_indices.append(new_idx)
                
                existing_names.append(new_name)
                success_count += 1
                idx += 1
                self.logger.info(f"复制 {new_name} 完成并加入分组 {target_group}", status="子任务成功")
                
            self.logger.info(f"批量复制任务完成，成功复制 {success_count} 个模拟器", status="已完成")
            self.console.restart_multiplayer()
            return new_indices
        except Exception as e:
            self.logger.error(f"复制模拟器失败: {str(e)}", status="失败")
            return new_indices

    def launch_instance(self, index):
        self._check_console()
        try:
            self.logger.info(f"正在启动模拟器序号: {index}", status="启动中")
            self.console.launch(index)
            self.logger.info(f"启动命令发送成功", status="完成")
        except Exception as e:
            self.logger.error(f"启动失败: {str(e)}", status="失败")

    def remove_instance(self, index):
        self._check_console()
        try:
            self.logger.info(f"准备删除模拟器序号: {index}，正执行关闭操作...", status="进行中")
            self.console.quit(index)
            # 等待模拟器完全关闭，最多等待15秒
            for _ in range(15):
                instances = self.console.list2()
                inst = next((x for x in instances if x['index'] == index), None)
                if inst is None or inst.get('android_status') == 0:
                    break
                time.sleep(1)
            
            time.sleep(2)
            self.logger.info(f"关闭完成，开始从多开面板彻底删除序号: {index}", status="进行中")
            self.console.remove(index)
            # 刷新多开面板
            self.console.restart_multiplayer()
        except Exception as e:
            self.logger.error(f"彻底删除操作失败: {str(e)}", status="失败")
            
    def run_weiba(self, index_list):
        if not hasattr(self, 'weiba_automation'):
            self.weiba_automation = WeibaAutomation(self, self.logger)
        self.weiba_automation.run_weiba_on_selected(index_list)
