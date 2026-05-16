import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.config import ConfigManager
from core.ldconsole import LDConsole
from core.tg_password_setup import TGPasswordSetup
from core.logger import AppLogger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_test_standalone():
    print("=" * 50)
    print("      Telegram 自动设置两步验证与绑定邮箱测试工具")
    print("=" * 50)
    
    config = ConfigManager()
    ld_path = config.get_ld_path()
    if not ld_path:
        logging.error("未找到雷电模拟器路径，请先在系统配置中设置 ld_path。")
        return

    console = LDConsole(ld_path)
    instances = console.list2()
    
    running_instances = [inst for inst in instances if inst["android_status"] == 1]
    
    if not running_instances:
        print("当前没有任何运行中的模拟器。请先启动需要测试的模拟器。")
        return
        
    print("当前运行状态的模拟器列表:")
    for idx, inst in enumerate(running_instances):
        print(f" [{idx}] 号选项 -> 模拟器索号: {inst['index']}, 名称: {inst['name']}")
        
    print("-" * 50)
    selection = input("请输入要测试的模拟器选项数值 (例如输入 0 选择第一个运行中的模拟器): ").strip()
    
    try:
        selection_idx = int(selection)
        if selection_idx < 0 or selection_idx >= len(running_instances):
            raise ValueError()
    except ValueError:
        print("输入无效，或者超出选择范围。")
        return
        
    target_inst = running_instances[selection_idx]
    target_index = target_inst["index"]
    
    print(f"\n已选择 模拟器: {target_inst['name']} (索引: {target_index})")
    
    email_file = config.get_email_file_path()
    if not email_file:
        print("\n❌ 错误：未配置邮箱列表文件！")
        print("请先在主界面的“4. 设置密码并绑定邮箱”中选择“邮箱列表”文件。")
        return
    else:
        print(f"\n✅ 读取到界面配置的邮箱列表文件: {email_file}")
        
    print(f"\n即将开始测试...")
    
    # 初始化并运行
    app_logger = AppLogger()
    setup_test = TGPasswordSetup(logger=app_logger)
    try:
        success = setup_test.run(target_index, email_file)
        if success:
            print("\n✅ 测试通过：已成功完成设置密码与绑定邮箱流程。")
        else:
            print("\n❌ 测试失败：流程未顺利完成，请查看上面输出的报错信息。")
    except Exception as e:
        print(f"\n❌ 测试运行中发生致命错误: {str(e)}")

if __name__ == "__main__":
    run_test_standalone()
