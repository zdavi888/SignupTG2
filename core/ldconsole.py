import subprocess
import os

class LDConsole:
    def __init__(self, console_path):
        self.console_path = console_path
        
    def _run_cmd(self, command, args):
        if not self.console_path or not os.path.exists(self.console_path):
            raise Exception(f"控制台程序未找到，请检查路径: {self.console_path}")
            
        full_cmd = [self.console_path, command] + args
        try:
            # Inject __COMPAT_LAYER to bypass WinError 740 (Elevation Required) if compat flagged
            env = os.environ.copy()
            env["__COMPAT_LAYER"] = "RunAsInvoker"
            
            # CREATE_NO_WINDOW flag to prevent console window popping up on windows (0x08000000)
            result = subprocess.run(full_cmd, capture_output=True, creationflags=0x08000000, env=env)
            
            # 尝试不同的解码方式，防止由于特殊字符导致的解码错误
            try:
                stdout = result.stdout.decode('gbk')
            except UnicodeDecodeError:
                try:
                    stdout = result.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    stdout = result.stdout.decode('gbk', errors='ignore')
            
            if stdout is None:
                stdout = ""
            return stdout.strip()
        except Exception as e:
            raise Exception(f"执行命令失败 {command}: {str(e)}")

    def list2(self):
        """返回所有模拟器列表详情"""
        output = self._run_cmd("list2", [])
        instances = []
        if output:
            for line in output.split('\n'):
                if not line.strip():
                    continue
                parts = line.split(',')
                if len(parts) >= 7:
                    instances.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "top_win_handle": parts[2],
                        "bind_win_handle": parts[3],
                        "android_status": int(parts[4]), # 1 means running, 0 means stop
                        "pid": parts[5],
                        "vbox_pid": parts[6]
                    })
        return instances

    def copy(self, new_name, from_index):
        """复制模拟器"""
        return self._run_cmd("copy", ["--name", new_name, "--from", str(from_index)])

    def remove(self, index):
        """删除模拟器"""
        return self._run_cmd("remove", ["--index", str(index)])

    def launch(self, index):
        """启动模拟器"""
        return self._run_cmd("launch", ["--index", str(index)])

    def quit(self, index):
        """关闭模拟器"""
        return self._run_cmd("quit", ["--index", str(index)])

    def backup(self, index, backup_file_path):
        """备份模拟器"""
        return self._run_cmd("backup", ["--index", str(index), "--file", backup_file_path])
        
    def restore(self, index, backup_file_path):
        """还原模拟器"""
        return self._run_cmd("restore", ["--index", str(index), "--file", backup_file_path])

    def runapp(self, index, packagename):
        return self._run_cmd("runapp", ["--index", str(index), "--packagename", packagename])

    def killapp(self, index, packagename):
        return self._run_cmd("killapp", ["--index", str(index), "--packagename", packagename])

    def adb(self, index, command_str):
        return self._run_cmd("adb", ["--index", str(index), "--command", command_str])

    def restart_multiplayer(self):
        """重启官方多开面板以便刷新列表"""
        if not self.console_path:
            return
            
        dir_path = os.path.dirname(self.console_path)
        base_install_dir = os.path.dirname(dir_path)
        
        possible_exes = ["dnmultiplayerex.exe", "ldmultiplayer.exe", "dnmultiplayer.exe"]
        target_exe = None
        target_path = None
        
        ldmutiplayer_dir = os.path.join(base_install_dir, "ldmutiplayer")
        
        for exe in possible_exes:
            path = os.path.join(ldmutiplayer_dir, exe)
            if os.path.exists(path):
                target_exe = exe
                target_path = path
                break

        if not target_path:
            for exe in possible_exes:
                path = os.path.join(dir_path, exe)
                if os.path.exists(path):
                    target_exe = exe
                    target_path = path
                    break
                
        if not target_path:
            target_path = self.console_path.replace("console.exe", "multiplayer.exe")
            target_exe = os.path.basename(target_path)
        
        try:
            for exe in possible_exes:
                subprocess.run(["taskkill", "/F", "/IM", exe, "/T"], capture_output=True)
            if os.path.exists(target_path):
                os.startfile(target_path)
        except Exception:
            pass
