import uiautomator2 as u2
import time
import os

class U2Manager:
    def __init__(self, console, index):
        self.console = console
        self.index = index
        self.d = None
        self._connect()

    def _connect(self):
        """尝试连接到指定索引的雷电模拟器"""
        # 雷电模拟器默认 adb 端口规则：5555 + index * 2
        port = 5555 + self.index * 2
        device_addr = f"127.0.0.1:{port}"
        
        try:
            self.d = u2.connect(device_addr)
            # 设置全局隐式等待时间，让元素查找更稳定
            self.d.implicitly_wait(10.0) 
            print(f"[{self.index}] 成功连接 uiautomator2 到 {device_addr}")
        except Exception as e:
            print(f"[{self.index}] 连接 uiautomator2 失败: {e}")

    def execute_steps(self, steps):
        """
        按顺序执行从 Weditor 录制提取的步骤。
        支持的步骤格式示例:
        [
            {"action": "click", "text": "抹除APP"},
            {"action": "click", "resourceId": "com.weiba:id/btn_ok"},
            {"action": "click", "xpath": "//android.widget.Button[@text='确定']"},
            {"action": "wait", "text": "成功", "timeout": 30},
            {"action": "delay", "time": 2}
        ]
        """
        if not self.d:
            print("设备未连接！")
            return False

        for i, step in enumerate(steps):
            action = step.get("action")
            print(f"[{self.index}] 执行步骤 {i+1}: {step}")
            
            try:
                if action == "click":
                    kwargs = {k: v for k, v in step.items() if k not in ["action"]}
                    self.d(**kwargs).click()
                    
                elif action == "wait":
                    timeout = step.get("timeout", 10)
                    kwargs = {k: v for k, v in step.items() if k not in ["action", "timeout"]}
                    if not self.d(**kwargs).wait(timeout=timeout):
                        print(f"[{self.index}] 等待超时: {step}")
                        return False
                        
                elif action == "delay":
                    time.sleep(step.get("time", 1))
                    
            except Exception as e:
                print(f"[{self.index}] 步骤执行异常: {e}")
                return False
                
        return True
