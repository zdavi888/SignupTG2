import xml.etree.ElementTree as ET
import time
import re

class UIAutomator:
    def __init__(self, console, index):
        self.console = console
        self.index = index

    def dump_ui(self):
        import tempfile
        import os
        
        self.console.adb(self.index, "shell rm /sdcard/window_dump.xml")
        self.console.adb(self.index, "shell uiautomator dump /sdcard/window_dump.xml")
        
        temp_dir = tempfile.gettempdir()
        local_xml = os.path.join(temp_dir, f"window_dump_{self.index}.xml")
        if os.path.exists(local_xml):
            os.remove(local_xml)
        
        # Pull the file directly to avoid stdout encoding/truncation issues
        self.console.adb(self.index, f"pull /sdcard/window_dump.xml {local_xml}")
        
        if not os.path.exists(local_xml):
            return ""
            
        try:
            with open(local_xml, "r", encoding="utf-8") as f:
                xml_res = f.read()
            return xml_res
        except Exception:
            return ""

    def find_nodes(self, **kwargs):
        nodes = []
        xml_str = self.dump_ui()
        if not xml_str:
            return nodes
            
        try:
            root = ET.fromstring(xml_str)
            for node in root.iter('node'):
                attrib = node.attrib
                match = True
                for k, v in kwargs.items():
                    if k == 'text_contains' and v not in attrib.get('text', ''): match = False
                    elif k == 'content_desc' and v not in attrib.get('content-desc', ''): match = False
                    elif k == 'resource_id' and v != attrib.get('resource-id', ''): match = False
                    elif k == 'class_name' and v != attrib.get('class', ''): match = False
                
                if match:
                    bounds_str = attrib.get('bounds')
                    if bounds_str:
                        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                        if m:
                            nodes.append({
                                'x1': int(m.group(1)),
                                'y1': int(m.group(2)),
                                'x2': int(m.group(3)),
                                'y2': int(m.group(4)),
                                'center_x': (int(m.group(1)) + int(m.group(3))) // 2,
                                'center_y': (int(m.group(2)) + int(m.group(4))) // 2,
                                'attrib': attrib
                            })
        except Exception:
            pass
        return nodes

    def find_node(self, **kwargs):
        nodes = self.find_nodes(**kwargs)
        return nodes[0] if nodes else None

    def tap(self, node_or_x, y=None):
        if y is not None:
            self.console.adb(self.index, f"shell input tap {node_or_x} {y}")
        elif isinstance(node_or_x, dict):
            cx = node_or_x['center_x']
            cy = node_or_x['center_y']
            self.console.adb(self.index, f"shell input tap {cx} {cy}")

    def tap_by(self, **kwargs):
        node = self.find_node(**kwargs)
        if node:
            self.tap(node)
            return True
        return False

    def wait_and_tap(self, timeout=10, **kwargs):
        start = time.time()
        while time.time() - start < timeout:
            if self.tap_by(**kwargs):
                return True
            time.sleep(1)
        return False
        
    def wait_for(self, timeout=10, **kwargs):
        start = time.time()
        while time.time() - start < timeout:
            node = self.find_node(**kwargs)
            if node: return node
            time.sleep(1)
        return None

    def input_text(self, text):
        # Escape single quotes and other shell special characters
        import shlex
        escaped_text = shlex.quote(text)
        self.console.adb(self.index, f"shell input text {escaped_text}")
