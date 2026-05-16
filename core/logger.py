import re

class AppLogger:
    def __init__(self):
        self.manager = None

    def _format_msg(self, msg):
        if not self.manager:
            return msg
        match = re.match(r'^\[(\d+)\] (.*)$', msg)
        if match:
            idx = match.group(1)
            rest = match.group(2)
            try:
                name = self.manager.get_instance_name(idx)
                return f"[{name}] {rest}"
            except:
                pass
        return msg

    def info(self, msg, status="INFO"):
        msg = self._format_msg(msg)
        print(f"[{status}] {msg}")
    
    def warning(self, msg, status="WARN"):
        msg = self._format_msg(msg)
        print(f"[{status}] {msg}")
        
    def error(self, msg, status="ERROR"):
        msg = self._format_msg(msg)
        print(f"[{status}] {msg}")
