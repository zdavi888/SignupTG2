import os
import sys
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.config import ConfigManager

config = ConfigManager()
ld_path = config.get_ld_path()

if not ld_path:
    print("No ld_path")
    sys.exit(0)

try:
    res = subprocess.run([ld_path, "action", "--help"], capture_output=True, text=True, encoding="gbk", errors="ignore")
    print(res.stdout)
except Exception as e:
    print("Error:", e)
