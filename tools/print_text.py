from collections.abc import Generator
from typing import Any
import socket
import requests
import tempfile
import os
import subprocess
import base64
import logging
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from .printer_utils import (
    detect_protocol, 
    pdf_to_pcl, 
    send_raw, 
    send_ipp_print_job, 
    send_lpd
)

# 获取日志器
logger = logging.getLogger(__name__)

class PrintTextTool(Tool):
    """文本打印工具"""
    
    def _text_to_pdf(self, text_content, output_path):
        """将文本转换为PDF，嵌入Noto Sans SC字体"""
        # 注册Noto Sans SC字体
        font_name = "NotoSC"
        font_path = os.path.join(os.path.dirname(__file__), "..", "_assets", "fonts", "static", "NotoSansSC-Regular.ttf")
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        
        # 创建PDF文档
        doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=1 * inch, bottomMargin=1 * inch)
        
        # 创建ParagraphStyle，强制使用NotoSC字体
        from reportlab.lib.styles import ParagraphStyle
        style = ParagraphStyle(
            name="Body",
            fontName=font_name,  # 强制使用NotoSC字体
            fontSize=12,
            leading=16
        )
        
        story = []
        
        # 创建段落，所有文本都使用NotoSC字体
        for line in text_content.split('\n'):
            para = Paragraph(line, style)
            story.append(para)
        
        # 生成PDF
        doc.build(story)
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """调用打印机打印文字内容"""
        text_content = tool_parameters.get("text_content")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port"))
        
        # 打印选项
        copies = int(tool_parameters.get("copies", 1))  # 打印份数，默认1份
        encoding = tool_parameters.get("encoding", "utf-8")  # 编码格式，默认UTF-8
        
        logger.info(f"接收到打印请求: 内容长度={len(text_content)}, 打印机={printer_ip}:{printer_port}, 份数={copies}, 编码={encoding}")
        
        try:
            # 1. 验证文本内容
            if not text_content:
                logger.warning("打印失败: 文本内容为空")
                yield self.create_json_message({"result": "打印失败: 文本内容为空"})
                return
            
            # 2. 验证打印选项
            if copies < 1 or copies > 10:
                logger.warning(f"打印失败: 打印份数必须在1-10之间，当前值={copies}")
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return
            
            # 3. 自动检测协议
            protocol = detect_protocol(printer_port)
            logger.info(f"检测到协议: {protocol}")
            
            # 4. 文本转PDF再转PCL
            with tempfile.TemporaryDirectory() as tmpdir:
                # 创建临时PDF文件
                pdf_path = os.path.join(tmpdir, "temp.pdf")
                logger.debug(f"创建临时PDF文件: {pdf_path}")
                self._text_to_pdf(text_content, pdf_path)
                
                # 创建临时PCL文件
                pcl_path = os.path.join(tmpdir, "temp.pcl")
                logger.debug(f"创建临时PCL文件: {pcl_path}")
                pdf_to_pcl(pdf_path, pcl_path)
                
                # 读取PCL内容
                with open(pcl_path, "rb") as f:
                    pcl_content = f.read()
                
                logger.info(f"生成PCL数据: 大小={len(pcl_content)}字节")
                
                # 5. 发送到打印机，根据份数重复发送
                for i in range(copies):
                    logger.info(f"发送第{i+1}/{copies}份到打印机")
                    if protocol == "raw":
                        logger.debug(f"使用RAW协议发送到{printer_ip}:{printer_port}")
                        send_raw(pcl_content, printer_ip, printer_port)
                    elif protocol == "ipp":
                        logger.debug(f"使用IPP协议发送到{printer_ip}:{printer_port}")
                        # IPP协议直接发送PCL内容
                        send_ipp_print_job(pcl_content, printer_ip, printer_port)
                    elif protocol == "lpd":
                        logger.debug(f"使用LPD协议发送到{printer_ip}:{printer_port}")
                        send_lpd(pcl_content, printer_ip, printer_port)
                    else:
                        logger.error(f"打印失败: 不支持的协议 - {protocol}")
                        yield self.create_json_message({"result": f"打印失败: 不支持的协议 - {protocol}"})
                        return
            
            logger.info(f"文本打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}")
            yield self.create_json_message({"result": f"文本打印成功，共{copies}份，使用编码：{encoding}，协议：{protocol}"})
        except socket.error as e:
            logger.error(f"打印失败: 无法连接打印机 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 无法连接打印机 - {str(e)}"})
        except ValueError as e:
            logger.error(f"打印失败: 参数无效 - {str(e)}")
            yield self.create_json_message({"result": f"打印失败: 参数无效 - {str(e)}"})
        except Exception as e:
            logger.exception(f"打印失败: {str(e)}")
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})