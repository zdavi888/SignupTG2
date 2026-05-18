import sys
import os
import time
import random
import uiautomator2 as u2

# 修复路径引用，确保能找到 core 模块
current_path = os.path.dirname(os.path.abspath(__file__))
if current_path not in sys.path:
    sys.path.insert(0, current_path)
parent_path = os.path.dirname(current_path)
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)

try:
    from core.config import ConfigManager
    from core.ldconsole import LDConsole
    from core.logger import AppLogger
except ImportError:
    # 兼容直接在 core 目录下运行的情况
    sys.path.insert(0, os.path.join(os.getcwd()))
    from config import ConfigManager
    from ldconsole import LDConsole
    from logger import AppLogger

def select_device():
    config = ConfigManager()
    ld_path = config.get_ld_path()
    if not ld_path:
        print("【错误】 请先在系统配置中设置雷电模拟器根目录 (ld_path)。")
        return None

    console = LDConsole(ld_path)
    instances = console.list2()
    
    running_instances = [inst for inst in instances if inst["android_status"] == 1]
    
    if not running_instances:
        print("当前没有任何处于开启状态的模拟器，请先启动您要测试的模拟器！！")
        return None
        
    print("当前运行状态的模拟器列表:")
    for idx, inst in enumerate(running_instances):
        print(f" [{idx}] 号选项 -> 面板索引: {inst['index']}, 名称: {inst['name']}")
        
    print("-" * 50)
    selection = input("请输入要运行测试的模拟器编号 (例如输入 0 选第一个): ").strip()
    
    try:
        selection_idx = int(selection)
        if selection_idx < 0 or selection_idx >= len(running_instances):
            raise ValueError()
        target_inst = running_instances[selection_idx]
        return target_inst["index"]
    except ValueError:
        print("输入无效。")
        return None

# 获取多开索引
target_index = select_device()
if target_index is None:
    sys.exit(1)

# 按 get_API_Hash.py 的规律连接设备
port = 5555 + target_index * 2
device_addr = f"127.0.0.1:{port}"

# 通用的延时函数
def random_delay():
    delay = random.uniform(3, 10)
    print(f"  [等待] 随机延时 {delay:.1f} 秒...")
    time.sleep(delay)

def get_api_app_name():
    # 获取项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    app_name_file = os.path.join(root_dir, "data", "API预设名称.txt")
    
    if not os.path.exists(app_name_file):
        print(f"【错误】 预设名称文件不存在: {app_name_file}")
        return None

    app_name = None
    try:
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
            # 立即从文件中移除
            with open(app_name_file, 'w', encoding='utf-8') as f:
                f.writelines(valid_lines[1:])
            print(f"成功提取并从文件中移除名称: {app_name}")
    except Exception as e:
        print(f"读取API预设名称出错: {e}")
            
    return app_name

def save_account_data(phone_number, api_id, api_hash, app_title, short_name):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        save_path = os.path.join(root_dir, "data", "账号资料")

        if not os.path.exists(save_path):
            os.makedirs(save_path)
            print(f"创建根文件夹: {save_path}")
        
        clean_phone = str(phone_number).strip()
        if clean_phone and not clean_phone.startswith('+'):
            clean_phone = '+' + clean_phone
            
        phone_folder = os.path.join(save_path, clean_phone)
        if not os.path.exists(phone_folder):
            os.makedirs(phone_folder)
            print(f"为号码 {clean_phone} 创建新文件夹")
        else:
            print(f"号码 {clean_phone} 的文件夹已存在，准备追加数据")
            
        txt_path = os.path.join(phone_folder, f"{clean_phone}.txt")
        
        is_new = not os.path.exists(txt_path)
        mode = 'a' if os.path.exists(txt_path) else 'w'
        
        with open(txt_path, mode, encoding='utf-8') as f:
            if is_new:
                f.write(f"手机号：{clean_phone}\n")
            f.write(f"\nApp api_id：{api_id}\n")
            f.write(f"App api_hash：{api_hash}\n")
            f.write(f"App title：{app_title}\n")
            f.write(f"Short name：{short_name}\n")
            
        print(f"账号API资料保存/追加完成: {txt_path}")
        return True
    except Exception as e:
        print(f"写入资料文件失败: {e}")
        return False

try:
    print(f"尝试连接设备地址: {device_addr}")
    d = u2.connect(device_addr)
    # 增加隐式等待，与 get_API_Hash.py 保持一致
    d.implicitly_wait(10.0)
    print(f"成功连接设备: {d.serial}")
    
    # 模拟器连接成功后，先问手机号（为了后面存资料用）
    phone_number = input("\n请先输入当前模拟器的 Telegram 手机号 (保存资料用, 如 +86...): ").strip()
    if not phone_number:
        print("手机号不能为空，测试终止。")
        sys.exit(1)

    print("\n--- 任务开始 ---")
    
    # 1. 点击确定按钮（如果存在）
    # confirm_btn = d(text="确定")
    # if confirm_btn.exists:
    #     print("发现弹窗，点击“确定”...")
    #     confirm_btn.click()
    #     random_delay()
    # else:
    #     print("未发现“确定”按钮，跳过点击直接进入后续流程")

    while True:
        # 2. 划到顶部
        print("回到顶部...")
        d(scrollable=True).scroll.toBeginning()
        time.sleep(2)
        
        # 3. 提取新名称
        content_text = get_api_app_name()
        if not content_text:
            print("没有可用的名称了，流程终止。")
            break

        # 4. 填写 App title (直接复制 get_API_Hash.py 逻辑)
        try:
            app_title_lbl = d(text="App title:")
            if app_title_lbl.exists:
                print(f"填写 App title: {content_text}")
                app_title_input = app_title_lbl.down(className="android.widget.EditText")
                app_title_input.click()
                time.sleep(0.5)
                app_title_input.set_text(content_text)
                time.sleep(1)
            else:
                print("未找到 App title: 标签，流程终止。")
                break
        except Exception as e:
            print(f"填写 App title 出错: {e}")
            break

        # 5. 填写 Short name (直接复制 get_API_Hash.py 逻辑)
        try:
            short_name_lbl = d(text="Short name:")
            if short_name_lbl.exists:
                print(f"填写 Short name: {content_text}")
                short_name_input = short_name_lbl.down(className="android.widget.EditText")
                short_name_input.click()
                time.sleep(0.5)
                short_name_input.set_text(content_text)
                time.sleep(1)
        except Exception as e:
            print(f"填写 Short name 出错: {e}")

        random_delay()
        
        # 6. URL 留空
        print("确保 URL 留空...")
        try:
             url_tag = d(text="URL:")
             if url_tag.exists:
                 url_input = url_tag.down(className="android.widget.EditText")
                 if url_input.exists:
                     url_input.set_text("")
        except: pass
        random_delay()
        
        # 7. 选择 Android
        print("从标题 Platform 中点击选择 Android...")
        try:
            platform_android = d(text="Android")
            if platform_android.exists:
                platform_android.click()
            time.sleep(1)
        except Exception as e:
            print(f"选择 Platform 出错: {e}")

        random_delay()
        
        # 8. 填写 Description (直接复制 get_API_Hash.py 逻辑)
        try:
            desc_lbl = d(text="Description:")
            if not desc_lbl.exists:
                d.swipe(0.5, 0.7, 0.5, 0.3)
                time.sleep(1)
                
            if desc_lbl.exists:
                print(f"填写 Description: {content_text}")
                desc_input = desc_lbl.down(className="android.widget.EditText")
                desc_input.click()
                time.sleep(0.5)
                desc_input.set_text(content_text)
                time.sleep(1)
        except Exception as e:
            print(f"填写 Description 出错: {e}")

        random_delay()
        
        # 9. 点击 Create application
        print("点击 Create application...")
        create_btn = d(text="Create application", className="android.widget.Button")
        if not create_btn.exists:
            create_btn = d(text="Create application")
        
        if create_btn.exists:
            create_btn.click()
            print("等待服务器响应 (10秒)...")
            time.sleep(10)
            
            # 检查是否成功进入了详情页
            if d(textContains="App api_id:").exists:
                print("【成功】 进入 API 详情页面！")
                
                # 提取数据
                print("提取 api_id 与 api_hash...")
                all_texts = []
                for x in d(className="android.widget.TextView"):
                    try:
                        all_texts.append(x.get_text())
                    except: pass
                
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
                
                print(f"提取结果 -> ID: {api_id}, Hash: {api_hash}")
                
                # 保存数据
                save_account_data(phone_number, api_id, api_hash, app_title, short_name)
                random_delay()
                
                # 10. 保存修改
                print("寻找 Save changes 按钮...")
                d(scrollable=True).scroll.to(text="Save changes")
                time.sleep(1)
                save_btn = d(text="Save changes")
                if save_btn.exists:
                    print("点击 Save changes...")
                    save_btn.click()
                    time.sleep(5)
                
                # 11. 回桌面
                print("流程全部完成，回到桌面。")
                d.press("home")
                break
            else:
                # 检查有没有报错弹窗 (确定, OK, 确 定, etc.)
                error_dismissed = False
                for btn_text in ["确定", "OK", "确 定", "Confirm"]:
                    btn = d(text=btn_text)
                    if btn.exists:
                        print(f"名称 {content_text} 失败 (发现 {btn_text} 弹窗)，点击并更换名称重试...")
                        btn.click()
                        error_dismissed = True
                        break
                
                if error_dismissed:
                    random_delay()
                    continue
                else:
                    print("未能检测到成功后的页面，也没看到报错弹窗。页面可能卡住或报错。")
                    break
        else:
            print("未找到 Create application 按钮，流程异常终止")
            break

except Exception as e:
    print(f"连接模拟器失败: {e}")
    sys.exit(1)
