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
    send_lpd,
    print_pdf_content,
    add_watermark_to_pdf
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
            
            # 获取打印份数
            copies = int(tool_parameters.get("copies", 1))
            # 获取编码格式
            encoding = tool_parameters.get("encoding", "utf-8")
            watermark = tool_parameters.get("watermark", "")
            
            # 高级打印选项
            print_options = {
                "color_mode": tool_parameters.get("color_mode", "monochrome"),
                "page_range": tool_parameters.get("page_range", ""),
                "duplex": tool_parameters.get("duplex", False)
            }
            
            logger.info(f"打印配置: 份数={copies}，编码={encoding}，高级选项={print_options}")
            
            # 验证打印份数
            if copies < 1 or copies > 10:
                logger.warning(f"打印失败: 打印份数必须在1-10之间，当前值={copies}")
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return
            
            if file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                # 处理图片文件 - 直接转PDF打印，实现高清打印
                logger.info("正在将图片处理为高清PDF格式")
                pdf_content = self._process_image_to_pdf(content)
                if watermark:
                    try:
                        pdf_content = add_watermark_to_pdf(pdf_content, watermark)
                    except Exception as e:
                        logger.warning(f"添加水印失败 (忽略错误): {e}")
                
                print_pdf_content(pdf_content, printer_ip, printer_port, copies, options=print_options)
                
                logger.info(f"图片高清打印成功，共{copies}份")
                yield self.create_json_message({"result": f"图片高清打印成功，共{copies}份"})
                return
            elif file_type == 'pdf':
                # 处理PDF文件 - 不再只提取文本，而是原生打印
                logger.info("正在处理原生PDF文件")
                pdf_content = content
                if watermark:
                    try:
                        pdf_content = add_watermark_to_pdf(pdf_content, watermark)
                    except Exception as e:
                        logger.warning(f"添加水印失败 (忽略错误): {e}")
                        
                print_pdf_content(pdf_content, printer_ip, printer_port, copies, options=print_options)
                
                logger.info(f"PDF原生打印成功，共{copies}份")
                yield self.create_json_message({"result": f"PDF原生打印成功，共{copies}份"})
                return
            elif file_type == 'html':
                # HTML 格式交由专门的方法处理
                logger.info("正在将HTML渲染为PDF")
                pdf_content = self._process_html_to_pdf(content)
                if watermark:
                    try:
                        pdf_content = add_watermark_to_pdf(pdf_content, watermark)
                    except Exception as e:
                        logger.warning(f"添加水印失败 (忽略错误): {e}")
                        
                print_pdf_content(pdf_content, printer_ip, printer_port, copies, options=print_options)
                
                logger.info(f"HTML网页渲染打印成功，共{copies}份")
                yield self.create_json_message({"result": f"HTML网页渲染打印成功，共{copies}份"})
                return
            else:
                # 作为纯文本处理
                logger.info(f"将内容作为文本类型处理")
                print_content = content
            
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
        elif ext in ['html', 'htm']:
            return 'html'
        else:
            return 'txt'
    
    def _process_image_to_pdf(self, content):
        """将图片转换为PDF文件以供高清打印"""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from PIL import Image
        
        # 1. 读取图片
        img = Image.open(io.BytesIO(content))
        img_width, img_height = img.size
        
        # 2. 准备PDF Buffer
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        a4_width, a4_height = A4
        
        # 3. 计算缩放比例，适应A4页面并居中
        margin = 30
        avail_w = a4_width - 2 * margin
        avail_h = a4_height - 2 * margin
        
        ratio = min(avail_w / img_width, avail_h / img_height)
        new_width = img_width * ratio
        new_height = img_height * ratio
        
        x = (a4_width - new_width) / 2
        y = (a4_height - new_height) / 2
        
        # 4. 绘制并保存
        img_reader = ImageReader(img)
        c.drawImage(img_reader, x, y, width=new_width, height=new_height)
        c.showPage()
        c.save()
        
        return pdf_buffer.getvalue()
        
    def _process_html_to_pdf(self, content):
        """将HTML内容渲染为PDF"""
        import pypandoc
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.html")
            output_path = os.path.join(tmpdir, "output.pdf")
            
            with open(input_path, 'wb') as f:
                f.write(content)
                
            pypandoc.convert_file(
                input_path,
                'pdf',
                outputfile=output_path,
                extra_args=['--pdf-engine=weasyprint']
            )
            
            with open(output_path, 'rb') as f:
                return f.read()