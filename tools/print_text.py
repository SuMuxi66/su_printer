from collections.abc import Generator
from typing import Any
import socket
import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class PrintTextTool(Tool):
    """文本打印工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """调用打印机打印文字内容"""
        text_content = tool_parameters.get("text_content")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port"))
        
        # 打印选项
        copies = int(tool_parameters.get("copies", 1))  # 打印份数，默认1份
        encoding = tool_parameters.get("encoding", "utf-8")  # 编码格式，默认UTF-8
        
        try:
            # 1. 验证文本内容
            if not text_content:
                yield self.create_json_message({"result": "打印失败: 文本内容为空"})
                return
            
            # 2. 验证打印选项
            if copies < 1 or copies > 10:
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return
            
            # 3. 自动检测协议
            protocol = self._detect_protocol(printer_ip, printer_port)
            
            # 4. 准备打印内容
            encoded_content = text_content.encode(encoding)
            
            # 5. 发送到打印机，根据份数重复发送
            for i in range(copies):
                if protocol == "raw":
                    self._send_raw(printer_ip, printer_port, encoded_content)
                elif protocol == "ipp":
                    self._send_ipp(printer_ip, printer_port, text_content, encoding)
                elif protocol == "lpd":
                    self._send_lpd(printer_ip, printer_port, encoded_content)
                else:
                    yield self.create_json_message({"result": f"打印失败: 不支持的协议 - {protocol}"})
                    return
            
            yield self.create_json_message({"result": f"文本打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}"})
        except socket.error as e:
            yield self.create_json_message({"result": f"打印失败: 无法连接打印机 - {str(e)}"})
        except ValueError as e:
            yield self.create_json_message({"result": f"打印失败: 参数无效 - {str(e)}"})
        except Exception as e:
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})
    
    def _detect_protocol(self, printer_ip, printer_port):
        """根据端口自动检测打印协议"""
        protocol_map = {
            9100: "raw",  # RAW TCP/IP
            631: "ipp",   # IPP
            515: "lpd"    # LPD
        }
        
        return protocol_map.get(printer_port, "raw")
    
    def _send_raw(self, printer_ip, printer_port, content):
        """使用RAW TCP/IP协议发送内容到打印机"""
        # 创建TCP连接
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((printer_ip, printer_port))
            
            # 发送内容
            s.sendall(content)
    
    def _send_ipp(self, printer_ip, printer_port, text_content, encoding):
        """使用IPP协议发送内容到打印机"""
        # 简化的IPP实现，使用HTTP POST直接发送文本
        # 这种方式对大多数打印机更兼容
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        
        # 使用更简单的方法发送打印请求
        # 对于某些打印机，直接发送文本可能比完整的IPP请求更有效
        headers = {
            "Content-Type": "text/plain",
            "Host": f"{printer_ip}:{printer_port}",
            "Connection": "close"
        }
        
        # 直接发送文本内容
        response = requests.post(ipp_url, data=text_content.encode(encoding), headers=headers, timeout=10)
        response.raise_for_status()
        
        # 简化响应处理
        if response.status_code != 200:
            raise Exception(f"IPP打印失败，状态码：{response.status_code}")
    
    def _send_lpd(self, printer_ip, printer_port, content):
        """使用LPD协议发送内容到打印机"""
        # LPD协议实现
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((printer_ip, printer_port))
            
            # 1. 发送控制文件命令
            # 控制文件命令格式：\x02queue\x00
            control_cmd = b"\x02lp\x00"  # lp是默认队列名
            s.sendall(control_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制命令失败: {response}")
            
            # 2. 发送控制文件内容
            # 控制文件内容格式：\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            control_content = b"\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            # 发送控制文件大小和内容
            s.sendall(f"{len(control_content):04x}".encode('ascii') + b"\x0a")
            s.sendall(control_content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制文件发送失败: {response}")
            
            # 3. 发送数据文件命令
            # 数据文件命令格式：\x03queue\x00
            data_cmd = b"\x03lp\x00"
            s.sendall(data_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据命令失败: {response}")
            
            # 4. 发送数据文件内容
            # 发送数据文件大小和内容
            s.sendall(f"{len(content):04x}".encode('ascii') + b"\x0a")
            s.sendall(content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据文件发送失败: {response}")