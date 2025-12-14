from collections.abc import Generator
from typing import Any
import socket
import requests
import tempfile
import os
import io
import logging
from PIL import Image
from PyPDF2 import PdfReader

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# 获取日志器
logger = logging.getLogger(__name__)

class PrintURLTool(Tool):
    """URL内容打印工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """从URL下载内容并打印"""
        url = tool_parameters.get("url")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port"))
        
        logger.info(f"接收到URL打印请求: URL={url}, 打印机={printer_ip}:{printer_port}")
        
        try:
            # 1. 验证URL
            if not url:
                logger.warning("打印失败: URL为空")
                yield self.create_json_message({"result": "打印失败: URL为空"})
                return
            
            # 2. 验证URL格式
            if not (url.startswith('http://') or url.startswith('https://') or url.startswith('ftp://')):
                logger.warning(f"打印失败: URL格式无效，URL={url}")
                yield self.create_json_message({"result": "打印失败: URL格式无效，必须以http://、https://或ftp://开头"})
                return
            
            # 3. 下载URL内容
            logger.info(f"正在下载URL内容: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.content
            logger.info(f"URL内容下载成功，大小={len(content)}字节")
            
            # 4. 检测文件类型并处理
            file_type = self._detect_file_type(url, content)
            logger.info(f"检测到文件类型: {file_type}")
            
            if file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                # 处理图片文件
                logger.info("正在处理图片文件")
                print_content = self._process_image(content)
                logger.debug(f"图片处理完成，转换为ASCII文本，大小={len(print_content)}字节")
            elif file_type == 'pdf':
                # 处理PDF文件
                logger.info("正在处理PDF文件")
                print_content = self._process_pdf(content)
                logger.debug(f"PDF处理完成，提取文本大小={len(print_content)}字节")
            else:
                # 作为纯文本处理
                logger.info(f"将内容作为{file_type}类型处理")
                print_content = content
            
            # 获取打印份数
            copies = int(tool_parameters.get("copies", 1))
            # 获取编码格式
            encoding = tool_parameters.get("encoding", "utf-8")
            logger.info(f"打印配置: 份数={copies}，编码={encoding}")
            
            # 验证打印份数
            if copies < 1 or copies > 10:
                logger.warning(f"打印失败: 打印份数必须在1-10之间，当前值={copies}")
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return
            
            # 6. 处理文本内容的编码
            if file_type == 'txt':
                # 对于文本文件，使用指定的编码格式
                logger.info(f"正在处理文本编码，目标编码={encoding}")
                try:
                    # 尝试解码再重新编码，确保使用指定的编码
                    text = print_content.decode('utf-8')
                    print_content = text.encode(encoding)
                    logger.debug(f"成功将文本转换为{encoding}编码")
                except UnicodeDecodeError:
                    # 如果无法用UTF-8解码，尝试直接使用指定编码
                    try:
                        print_content = print_content.decode(encoding).encode(encoding)
                        logger.debug(f"成功使用{encoding}编码直接处理文本")
                    except Exception:
                        # 如果仍然失败，保持原内容不变
                        logger.warning(f"无法将文本转换为{encoding}编码，保持原内容不变")
                        pass
            
            # 7. 自动检测协议
            protocol = self._detect_protocol(printer_ip, printer_port)
            logger.info(f"检测到协议: {protocol}")
            
            # 8. 发送到打印机，根据份数重复发送
            for i in range(copies):
                logger.info(f"发送第{i+1}/{copies}份到打印机")
                if protocol == "raw":
                    logger.debug(f"使用RAW协议发送")
                    self._send_raw(print_content, printer_ip, printer_port)
                elif protocol == "ipp":
                    logger.debug(f"使用IPP协议发送")
                    self._send_ipp(print_content, printer_ip, printer_port, encoding)
                elif protocol == "lpd":
                    logger.debug(f"使用LPD协议发送")
                    self._send_lpd(print_content, printer_ip, printer_port)
                else:
                    logger.error(f"打印失败: 不支持的协议 - {protocol}")
                    yield self.create_json_message({"result": f"打印失败: 不支持的协议 - {protocol}"})
                    return
            
            logger.info(f"{file_type.upper()}内容打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}")
            yield self.create_json_message({"result": f"{file_type.upper()}内容打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}"})
        except ValueError as e:
            # 无效的URL格式或其他值错误
            logger.error(f"打印失败: 参数无效 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 参数无效 - {str(e)}"})
        except socket.error as e:
            # 确保清理临时文件
            logger.error(f"打印失败: 无法连接打印机 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 无法连接打印机 - {str(e)}"})
        except requests.RequestException as e:
            # 确保清理临时文件
            logger.error(f"打印失败: 下载URL内容失败 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 下载URL内容失败 - {str(e)}"})
        except Exception as e:
            # 确保清理临时文件
            logger.exception(f"打印失败: {str(e)}")
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
    
    def _send_raw(self, content, printer_ip, printer_port):
        """使用RAW TCP/IP协议发送内容到打印机"""
        logger.info(f"使用RAW协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
        # 创建TCP连接
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            logger.debug(f"正在连接打印机{printer_ip}:{printer_port}")
            s.connect((printer_ip, printer_port))
            logger.debug("连接成功，正在发送数据")
            # 发送内容
            s.sendall(content)
            logger.debug("数据发送完成")
    
    def _send_ipp(self, content, printer_ip, printer_port, encoding):
        """使用IPP协议发送内容到打印机"""
        logger.info(f"使用IPP协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节，编码={encoding}")
        # 简化的IPP实现，使用HTTP POST直接发送文本
        # 这种方式对大多数打印机更兼容
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        logger.debug(f"IPP请求URL: {ipp_url}")
        
        # 检测内容类型并转换为文本
        text_content = ""
        if isinstance(content, bytes):
            # 尝试解码为文本
            try:
                text_content = content.decode(encoding)
                logger.debug(f"使用编码{encoding}成功解码内容")
            except UnicodeDecodeError:
                # 如果无法解码，使用UTF-8尝试
                text_content = content.decode('utf-8', errors='ignore')
                logger.warning(f"使用编码{encoding}解码失败，使用UTF-8(忽略错误)解码")
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
        logger.debug(f"正在发送IPP请求，头部：{headers}")
        response = requests.post(ipp_url, data=text_content.encode(encoding), headers=headers, timeout=10)
        logger.debug(f"IPP响应状态码：{response.status_code}")
        response.raise_for_status()
        
        # 简化响应处理
        if response.status_code != 200:
            logger.error(f"IPP打印失败，状态码：{response.status_code}")
            raise Exception(f"IPP打印失败，状态码：{response.status_code}")
        logger.debug("IPP打印成功")
    
    def _send_lpd(self, content, printer_ip, printer_port):
        """使用LPD协议发送内容到打印机"""
        logger.info(f"使用LPD协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
        # LPD协议实现
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            logger.debug(f"正在连接LPD打印机{printer_ip}:{printer_port}")
            s.connect((printer_ip, printer_port))
            logger.debug("LPD连接成功")
            
            # 1. 发送控制文件命令
            # 控制文件命令格式：\x02queue\x00
            control_cmd = b"\x02lp\x00"  # lp是默认队列名
            logger.debug(f"发送LPD控制命令：{control_cmd}")
            s.sendall(control_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD控制命令响应：{response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制命令失败: {response}")
            logger.debug("LPD控制命令成功")
            
            # 2. 发送控制文件内容
            # 控制文件内容格式：\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            control_content = b"\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            # 发送控制文件大小和内容
            logger.debug(f"发送LPD控制文件，大小：{len(control_content)}字节")
            s.sendall(f"{len(control_content):04x}".encode('ascii') + b"\x0a")
            s.sendall(control_content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD控制文件响应：{response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制文件发送失败: {response}")
            logger.debug("LPD控制文件发送成功")
            
            # 3. 发送数据文件命令
            # 数据文件命令格式：\x03queue\x00
            data_cmd = b"\x03lp\x00"
            logger.debug(f"发送LPD数据命令：{data_cmd}")
            s.sendall(data_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD数据命令响应：{response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据命令失败: {response}")
            logger.debug("LPD数据命令成功")
            
            # 4. 发送数据文件内容
            # 发送数据文件大小和内容
            logger.debug(f"发送LPD数据文件，大小：{len(content)}字节")
            s.sendall(f"{len(content):04x}".encode('ascii') + b"\x0a")
            s.sendall(content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD数据文件响应：{response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据文件发送失败: {response}")
            logger.debug("LPD数据文件发送成功")