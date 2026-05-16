import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
sys.path.append(os.path.join(os.path.dirname(__file__), "gui"))

try:
    from PyQt6.QtWidgets import QApplication
    from gui.app_window import AppWindow

    if __name__ == "__main__":
        app = QApplication(sys.argv)
        window = AppWindow()
        window.show()
        sys.exit(app.exec())
except ImportError as e:
    print("环境错误，请确保安装了 PyQt6: pip install PyQt6")
    print("错误信息: ", e)
