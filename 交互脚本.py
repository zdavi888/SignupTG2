import os
import json
import traceback
import subprocess
import ctypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

TARGET_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 5044

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class SyncHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/sync':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(post_data)
                files = data.get('files', [])
                
                def process_nodes(nodes, current_path=""):
                    for node in nodes:
                        node_path = os.path.join(TARGET_DIR, current_path, node['name'])
                        if node['type'] == 'folder':
                            if not os.path.exists(node_path):
                                os.makedirs(node_path)
                            if 'children' in node:
                                process_nodes(node['children'], os.path.join(current_path, node['name']))
                        elif node['type'] == 'file':
                            if node['name'] in ['ld_config.json', '交互脚本.py', 'sync.py']:
                                continue
                            content = node.get('content', '')
                            
                            should_write = True
                            if os.path.exists(node_path):
                                with open(node_path, 'r', encoding='utf-8') as f:
                                    if f.read() == content:
                                        should_write = False
                            if should_write:
                                with open(node_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                print(f"[+] 更新文件: {node['path']}")
                
                print("\n[*] 📥 接收到来自云端的代码推送...")
                process_nodes(files)
                print("[*] ✅ 代码同步成功！在下方输入 1 测试运行。")
                
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                
            except Exception as e:
                print(f"[x] 解析推送代码失败: {e}")
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 取消默认请求日志输出

def start_server():
    server = HTTPServer(('127.0.0.1', PORT), SyncHandler)
    print(f"[*] 🚀 本地监听服务已启动 (127.0.0.1:{PORT})")
    print(f"[*] ⏳ 请在浏览器页面中点击【同步推送代码到本地】按钮...")
    server.serve_forever()

def run_main():
    print("[*] 🏃 正在启动主程序 main.py ...")
    main_file = os.path.join(TARGET_DIR, "main.py")
    if not os.path.exists(main_file):
        print("[x] 找不到 main.py，请先在云端推送！")
        return
        
    try:
        process = subprocess.Popen([sys.executable, main_file])
        rc = process.wait()
        
        if rc != 0:
            print(f"\n[!] ⚠️ 主程序异常退出，错误码: {rc}")
            print(f"[!] 💡 请将报错信息反馈给 AI 进行修复。")
        else:
            print(f"\n[*] 🏁 主程序正常关闭。")
            
    except Exception as e:
        print(f"[x] 运行主程序失败: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 雷电自动化 - 本地同步服务")
    print("=" * 60)
    
    if not is_admin():
        print("\n[!] ⚠️ 警告: 检测到当前暂无【管理员权限】！")
        print("[!] 请以【管理员身份运行】 VSCode 或 PowerShell，否则操作雷电可能会报 [WinError 740]\n")
    
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    while True:
        print("\n选项菜单:")
        print("  [1] 运行主程序 main.py 测试")
        print("  [0] 退出服务")
        choice = input("请输入选择: ").strip()
        
        if choice == '1':
            print("-" * 50)
            run_main()
        elif choice == '0':
            print("再见！👏")
            break
