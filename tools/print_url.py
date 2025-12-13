from collections.abc import Generator
from typing import Any
import socket
import requests
import tempfile
import os
import io
from PIL import Image
from PyPDF2 import PdfReader

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class PrintURLTool(Tool):
    """URL内容打印工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """从URL下载内容并打印"""
        url = tool_parameters.get("url")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port"))
        
        try:
            # 1. 验证URL
            if not url:
                yield self.create_json_message({"result": "打印失败: URL为空"})
                return
            
            # 2. 验证URL格式
            if not (url.startswith('http://') or url.startswith('https://') or url.startswith('ftp://')):
                yield self.create_json_message({"result": "打印失败: URL格式无效，必须以http://、https://或ftp://开头"})
                return
            
            # 3. 下载URL内容
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.content
            
            # 4. 检测文件类型并处理
            file_type = self._detect_file_type(url, content)
            
            if file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                # 处理图片文件
                print_content = self._process_image(content)
            elif file_type == 'pdf':
                # 处理PDF文件
                print_content = self._process_pdf(content)
            else:
                # 作为纯文本处理
                print_content = content
            
            # 获取打印份数
            copies = int(tool_parameters.get("copies", 1))
            # 获取编码格式
            encoding = tool_parameters.get("encoding", "utf-8")
            
            # 验证打印份数
            if copies < 1 or copies > 10:
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return
            
            # 6. 处理文本内容的编码
            if file_type == 'txt':
                # 对于文本文件，使用指定的编码格式
                try:
                    # 尝试解码再重新编码，确保使用指定的编码
                    text = print_content.decode('utf-8')
                    print_content = text.encode(encoding)
                except UnicodeDecodeError:
                    # 如果无法用UTF-8解码，尝试直接使用指定编码
                    try:
                        print_content = print_content.decode(encoding).encode(encoding)
                    except Exception:
                        # 如果仍然失败，保持原内容不变
                        pass
            
            # 7. 自动检测协议
            protocol = self._detect_protocol(printer_ip, printer_port)
            
            # 8. 发送到打印机，根据份数重复发送
            for i in range(copies):
                if protocol == "raw":
                    self._send_raw(printer_ip, printer_port, print_content)
                elif protocol == "ipp":
                    self._send_ipp(printer_ip, printer_port, print_content, encoding)
                elif protocol == "lpd":
                    self._send_lpd(printer_ip, printer_port, print_content)
                else:
                    yield self.create_json_message({"result": f"打印失败: 不支持的协议 - {protocol}"})
                    return
            
            yield self.create_json_message({"result": f"{file_type.upper()}内容打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}"})
        except ValueError as e:
            # 无效的URL格式或其他值错误
            yield self.create_json_message({"result": f"打印失败: 参数无效 - {str(e)}"})
        except socket.error as e:
            # 确保清理临时文件
            yield self.create_json_message({"result": f"打印失败: 无法连接打印机 - {str(e)}"})
        except requests.RequestException as e:
            # 确保清理临时文件
            yield self.create_json_message({"result": f"打印失败: 下载URL内容失败 - {str(e)}"})
        except Exception as e:
            # 确保清理临时文件
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})
    
    def _detect_protocol(self, printer_ip, printer_port):
        """根据端口自动检测打印协议"""
        protocol_map = {
            9100: "raw",  # RAW TCP/IP
            631: "ipp",   # IPP
            515: "lpd"    # LPD
        }
        
        return protocol_map.get(printer_port, "raw")
    
    def _detect_file_type(self, url, content):
        """检测文件类型"""
        # 从URL获取文件扩展名
        ext = url.split('.')[-1].lower()
        
        # 支持的图片格式
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        
        # 支持的文档格式
        document_extensions = ['pdf', 'txt']
        
        if ext in image_extensions:
            return ext
        elif ext == 'pdf':
            return 'pdf'
        else:
            return 'txt'
    
    def _process_image(self, content):
        """处理图片文件"""
        # 使用Pillow打开并处理图片
        with Image.open(io.BytesIO(content)) as img:
            # 转换为灰度图，降低打印复杂度
            img = img.convert('L')
            
            # 调整图片大小，适应标准纸张
            width, height = img.size
            max_width = 80  # 假设打印机每行80字符
            aspect_ratio = height / width
            new_width = max_width
            new_height = int(new_width * aspect_ratio)
            img = img.resize((new_width, new_height))
            
            # 转换为ASCII字符
            ascii_chars = "@%#*+=-:. "
            pixels = img.getdata()
            ascii_str = ""
            
            for pixel in pixels:
                ascii_str += ascii_chars[pixel * len(ascii_chars) // 256]
            
            # 添加换行符
            ascii_image = ""
            for i in range(0, len(ascii_str), new_width):
                ascii_image += ascii_str[i:i+new_width] + "\n"
            
            return ascii_image.encode('utf-8')
    
    def _process_pdf(self, content):
        """处理PDF文件"""
        # 使用PyPDF2读取PDF内容
        pdf_reader = PdfReader(io.BytesIO(content))
        text = ""
        
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n\f"
        
        return text.encode('utf-8')
    
    def _send_raw(self, printer_ip, printer_port, content):
        """使用RAW TCP/IP协议发送内容到打印机"""
        # 创建TCP连接
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((printer_ip, printer_port))
            
            # 发送内容
            s.sendall(content)
    
    def _send_ipp(self, printer_ip, printer_port, content, encoding):
        """使用IPP协议发送内容到打印机"""
        # 简化的IPP实现，使用HTTP POST直接发送文本
        # 这种方式对大多数打印机更兼容
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        
        # 检测内容类型并转换为文本
        text_content = ""
        if isinstance(content, bytes):
            # 尝试解码为文本
            try:
                text_content = content.decode(encoding)
            except UnicodeDecodeError:
                # 如果无法解码，使用UTF-8尝试
                text_content = content.decode('utf-8', errors='ignore')
        else:
            text_content = str(content)
        
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