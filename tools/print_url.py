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
from .printer_utils import (
    detect_protocol, 
    safe_download, 
    send_raw, 
    send_ipp_print_job, 
    send_lpd
)

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
            content = safe_download(url)
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
            protocol = detect_protocol(printer_port)
            logger.info(f"检测到协议: {protocol}")
            
            # 8. 发送到打印机，根据份数重复发送
            for i in range(copies):
                logger.info(f"发送第{i+1}/{copies}份到打印机")
                if protocol == "raw":
                    logger.debug(f"使用RAW协议发送")
                    send_raw(print_content, printer_ip, printer_port)
                elif protocol == "ipp":
                    logger.debug(f"使用IPP协议发送")
                    send_ipp_print_job(print_content, printer_ip, printer_port, content_type=f"text/plain; charset={encoding}")
                elif protocol == "lpd":
                    logger.debug(f"使用LPD协议发送")
                    send_lpd(print_content, printer_ip, printer_port)
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
            logger.error(f"打印失败: 无法连接打印机 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 无法连接打印机 - {str(e)}"})
        except requests.RequestException as e:
            logger.error(f"打印失败: 下载URL内容失败 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 下载URL内容失败 - {str(e)}"})
        except Exception as e:
            logger.exception(f"打印失败: {str(e)}")
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})
    
    def _detect_file_type(self, url, content):
        """检测文件类型"""
        import urllib.parse
        
        # 从URL解析出纯净的路径，去除查询参数等
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        
        # 获取扩展名
        ext = path.split('.')[-1].lower() if '.' in path else ''
        
        # 支持的图片格式
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        
        if ext in image_extensions:
            return ext
        elif ext == 'pdf':
            return 'pdf'
        else:
            return 'txt'
    
    def _process_image(self, content):
        """处理图片文件"""
        # 设置最大像素限制以防解压炸弹
        Image.MAX_IMAGE_PIXELS = 100000000
        
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
            
            # 预计算查找表以优化性能
            lookup_table = [ascii_chars[p * len(ascii_chars) // 256] for p in range(256)]
            ascii_str = "".join([lookup_table[pixel] for pixel in pixels])
            
            # 添加换行符
            ascii_image = "\n".join([ascii_str[i:i+new_width] for i in range(0, len(ascii_str), new_width)]) + "\n"
            
            return ascii_image.encode('utf-8')
    
    def _process_pdf(self, content):
        """处理PDF文件"""
        # 使用PyPDF2读取PDF内容
        pdf_reader = PdfReader(io.BytesIO(content))
        text = ""
        
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n\f"
        
        return text.encode('utf-8')