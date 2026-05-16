import time
import os
import sys
import ctypes
import ctypes.wintypes
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import ConfigManager
from core.ldconsole import LDConsole

VK_F8 = 0x77
SW_RESTORE = 9

# 创建优先级控制的录制操作锁
f8_condition = threading.Condition()
waiting_stops = 0
f8_busy = False

def bring_window_to_front_and_press_f8(window_title, is_stop=False):
    """
    带线程锁的安全置前操作。
    通过查找窗口标题将模拟器置于前台，并发送原生的F8快捷键触发雷电自身的录制。
    所有窗口排队进行此操作，优先处理停止录制请求，避免 F8 焦点冲突。
    """
    global waiting_stops, f8_busy
    with f8_condition:
        if is_stop:
            waiting_stops += 1
            while f8_busy:
                f8_condition.wait()
            waiting_stops -= 1
        else:
            while f8_busy or waiting_stops > 0:
                f8_condition.wait()
        f8_busy = True

    try:
        return _do_f8(window_title)
    finally:
        with f8_condition:
            f8_busy = False
            f8_condition.notify_all()

def _do_f8(window_title):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible

    target_hwnd = None

    def foreach_window(hwnd, lParam):
        nonlocal target_hwnd
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                if window_title in buff.value:
                    target_hwnd = hwnd
                    return False
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)

    if target_hwnd:
        # 激活窗口，避免窗口被最小化
        user32.ShowWindow(target_hwnd, SW_RESTORE)
        
        fg_hwnd = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
        my_thread = kernel32.GetCurrentThreadId()
        
        # 强制夺取焦点
        if fg_hwnd != target_hwnd and fg_thread != 0 and fg_thread != my_thread:
            user32.AttachThreadInput(my_thread, fg_thread, True)
            user32.SetForegroundWindow(target_hwnd)
            user32.AttachThreadInput(my_thread, fg_thread, False)
        else:
            user32.SetForegroundWindow(target_hwnd)

        # 再次确保置顶
        time.sleep(0.5)
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        user32.SetWindowPos(target_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        time.sleep(0.1)
        user32.SetWindowPos(target_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        time.sleep(0.8)  # 给足够的缓冲时间

        # 模拟按下F8 (雷电模拟器默认录制视频快捷键)
        user32.keybd_event(VK_F8, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(VK_F8, 0, 2, 0)
        
        # 额外等待稍微一会再结束，防止下一个窗口过快竞争
        time.sleep(1.0)
        return target_hwnd
    return None

def close_ld_popups_by_pid(main_hwnd):
    """根据模拟器主窗口的进程ID（PID），强制关闭该进程衍生的其它可见视窗（即录制弹窗）"""
    user32 = ctypes.windll.user32
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(main_hwnd, ctypes.byref(pid))
    target_pid = pid.value
    
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    
    closed_any = False

    def foreach_window(hwnd, lParam):
        nonlocal closed_any
        if user32.IsWindowVisible(hwnd) and hwnd != main_hwnd:
            win_pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
            if win_pid.value == target_pid:
                # 获取标题用于打印日志
                length = GetWindowTextLength(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buff, length + 1)
                    title = buff.value
                else:
                    title = "无标题窗口"
                
                print(f"-> 检测到属于该模拟器的附属视窗: [{title}]，发送强制关闭指令...")
                user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
                closed_any = True
        return True
    
    print("正在扫描并关闭关联的弹窗...")
    for _ in range(5):
        EnumWindows(EnumWindowsProc(foreach_window), 0)
        if closed_any:
            break
        time.sleep(0.5)
        
    if not closed_any:
        print("-> 未检测到需要额外关闭的附属弹窗(可能已被ESC直接关闭)。")

def wait_for_emulator_boot(console, index, timeout=120):
    start_time = time.time()
    while time.time() - start_time < timeout:
        instances = console.list2()
        instance = next((inst for inst in instances if inst['index'] == index), None)
        if instance and instance['android_status'] == 1:
            break
        time.sleep(2)
        
    while time.time() - start_time < timeout:
        try:
            res = console.adb(index, "shell getprop sys.boot_completed")
            if res and "1" in res:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

def test_record():
    config = ConfigManager()
    ld_path = config.get_ld_path()
    
    if not ld_path or not os.path.exists(ld_path):
        print("错误: 找不到雷电模拟器控制台路径。")
        return
        
    console = LDConsole(ld_path)
    new_name = f"Test_Record_{int(time.time())}"
    print(f"正在复制新模拟器: {new_name}...")
    console.copy(new_name, 0)
    
    time.sleep(2)
    instances = console.list2()
    new_instance = next((inst for inst in instances if inst['name'] == new_name), None)
    if not new_instance:
        print("错误: 模拟器复制失败。")
        return
        
    target_index = new_instance['index']
    
    # 获取视频保存目录
    ld_dir = os.path.dirname(ld_path)
    video_dir = os.path.join(ld_dir, "vms", "video")
    if not os.path.exists(video_dir):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            documents = winreg.QueryValueEx(key, "Personal")[0]
            video_dir = os.path.join(documents, "XuanZhi", "Video")
            if not os.path.exists(video_dir):
                os.makedirs(video_dir, exist_ok=True)
        except:
            os.makedirs(video_dir, exist_ok=True)

    try:
        print(f"1. 启动新模拟器 {target_index} ({new_name})")
        console.launch(target_index)
        
        if not wait_for_emulator_boot(console, target_index):
            print("错误: 模拟器启动超时。")
            return
            
        print("2. 模拟器完全启动，休眠等待 10 秒以确保桌面加载完毕...")
        time.sleep(10)
        
        # 记录开始前的视频文件 (排除临时录制文件)
        before_files = set(f for f in os.listdir(video_dir) if f.endswith(".mp4") and not f.endswith("_tmp.mp4"))

        print("3. 正准备调用 F8 (方案1)，系统会自动排队抢焦点...")
        if not bring_window_to_front_and_press_f8(new_name, is_stop=False):
            print(f"警告: 无法根据名称({new_name})匹配到窗口，尝试查找包含'雷电'的窗口...")
            bring_window_to_front_and_press_f8("雷电", is_stop=False)
            
        print("4. 当前应该已开始录制（可在模拟器顶部看到红点提示）。正等待 15 秒...")
        time.sleep(15)
        
        print("5. 再次排队调用 F8 以停止录制...")
        hwnd_used = bring_window_to_front_and_press_f8(new_name, is_stop=True)
        
        # 等待视频文件写入完成，并检测关闭“视频录制”弹窗
        if hwnd_used:
            close_ld_popups_by_pid(hwnd_used)
        else:
            print("未能获取到有效窗口句柄，跳过多余弹窗清理。")
        
        time.sleep(2) # 附加一点时间确保视频文件彻底保存完毕
        
        # 探测产生的新视频文件
        after_files = set(f for f in os.listdir(video_dir) if f.endswith(".mp4") and not f.endswith("_tmp.mp4"))
        new_files = after_files - before_files
        
        target_video_file = None
        if new_files:
            # 获取最新创建的文件 (按修改时间排序)
            target_video_file = sorted(list(new_files), key=lambda x: os.path.getmtime(os.path.join(video_dir, x)))[-1]
            print(f"-> 探测到新创建的录像文件: {target_video_file}")
        else:
            print("-> 警告: 没有探测到新创建的录像文件，请检查视频保持路径是否为: " + video_dir)

        print("\n=== 录像操作已完成！ ===")
        
        if target_video_file:
            import random
            old_path = os.path.join(video_dir, target_video_file)
            random_num = random.randint(1000, 9999)
            new_name_str = f"测试录制_{target_index}_{random_num}.mp4"
            new_path = os.path.join(video_dir, new_name_str)
            
            # 使用循环重试机制进行重命名，以防雷电模拟器还在进行视频文件封装占用
            for _ in range(5):
                try:
                    os.rename(old_path, new_path)
                    print(f"【成功】已将视频安全重命名为目标名称: {new_name_str}")
                    print(f"精准调取路径: {new_path}")
                    break
                except Exception as e:
                    time.sleep(1.5)
            else:
                print(f"【失败】多次尝试重命名失败，文件可能被占用: {old_path}")
        
        print("\n【说明】无论并发多少个窗口，此方案都会精准记录自身对应的临时文件并在结束时独立重命名。")
        input("按下 【回车键】 立即销毁并清理当前测试的模拟器...")
        
    finally:
        print(f"清理临时模拟器 {target_index}...")
        console.quit(target_index)
        time.sleep(3)
        try:
            console.remove(target_index)
            print("清理完毕。")
        except:
            print("清理报错，可手动在多开器中删除即可。")

if __name__ == "__main__":
    test_record()
