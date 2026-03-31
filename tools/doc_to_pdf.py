from collections.abc import Generator
from typing import Any
import os
import tempfile
import requests
import pypandoc
import base64
import subprocess
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
    safe_download, 
    send_raw, 
    send_ipp_print_job, 
    send_lpd,
    pdf_to_pcl
)

# 获取日志器
logger = logging.getLogger(__name__)

class DocToPDFTool(Tool):
    """文档转PDF工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """将文档转换为PDF"""
        document_content = tool_parameters.get("document_content")
        auto_print = tool_parameters.get("auto_print", False)
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port", 9100))
        
        logger.info(f"接收到文档转PDF请求: 自动打印={auto_print}, 打印机={printer_ip}:{printer_port}")
        
        try:
            # 1. 验证输入
            if not document_content:
                logger.warning("转换失败: 文档内容或URL为空")
                yield self.create_json_message({"result": "转换失败: 文档内容或URL为空"})
                return
            
            # 2. 判断输入类型并获取文件内容
            if self._is_url(document_content):
                # 从URL下载文档
                logger.info(f"检测到URL输入: {document_content[:50]}...")
                file_content, file_name = self._download_document(document_content)
                logger.info(f"文档下载成功: 文件名={file_name}, 大小={len(file_content)}字节")
            else:
                # 直接使用文本内容
                logger.info(f"检测到文本输入，长度={len(document_content)}字符")
                file_content = document_content.encode('utf-8')
                # 默认使用txt格式，或根据内容判断格式
                file_name, file_ext = self._detect_content_format(document_content)
                logger.info(f"检测到文本格式: 文件名={file_name}, 扩展名={file_ext}")
            
            # 3. 转换为PDF
            logger.info(f"正在转换文档为PDF: {file_name}")
            pdf_content = self._convert_to_pdf(file_content, file_ext, file_name)
            logger.info(f"文档转换成功，PDF大小={len(pdf_content)}字节")
            
            # 4. 自动打印处理
            if auto_print:
                if not printer_ip:
                    logger.warning("自动打印失败: 打印机IP为空")
                    yield self.create_json_message({"result": "自动打印失败: 打印机IP为空"})
                    return
                
                # 发送打印请求
                logger.info(f"正在自动打印PDF: 打印机={printer_ip}:{printer_port}")
                self._send_to_printer(pdf_content, printer_ip, printer_port)
                logger.info("PDF自动打印成功")
                
                # 5. 返回转换和打印结果
                yield self.create_json_message({"result": "文档转换成功并已自动打印", "printer_ip": printer_ip, "printer_port": printer_port})
            else:
                # 5. 仅返回转换结果
                # 将二进制PDF内容转换为Base64编码字符串，以便JSON序列化
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
                logger.info("文档转换成功，返回Base64编码的PDF内容")
                yield self.create_json_message({"result": "文档转换成功", "pdf_content": pdf_base64})
        except requests.RequestException as e:
            logger.error(f"转换失败: 下载文档失败 - {str(e)}")
            yield self.create_json_message({"result": f"转换失败: 下载文档失败 - {str(e)}"})
        except Exception as e:
            logger.exception(f"转换失败: {str(e)}")
            yield self.create_json_message({"result": f"转换失败: {str(e)}"})
    
    def _is_url(self, content):
        """判断输入是否为URL"""
        return content.startswith(('http://', 'https://'))
    
    def _detect_content_format(self, content):
        """检测内容格式"""
        # 简单的格式检测
        if content.startswith('# '):
            # Markdown格式
            return "document.md", ".md"
        elif content.count('\t') > 5 or content.count('  ') > 5:
            # 可能是纯文本
            return "document.txt", ".txt"
        else:
            # 默认使用txt格式
            return "document.txt", ".txt"
    
    def _download_document(self, url):
        """从URL安全下载文档"""
        content = safe_download(url)
        
        # 从URL获取文件名
        file_name = url.split('/')[-1].split('?')[0]
        if not file_name:
            file_name = "document"
        
        return content, file_name
    
    def _convert_to_pdf(self, file_content, file_ext, file_name):
        """将不同格式的文档转换为PDF"""
        logger.info(f"开始文档转换: 文件名={file_name}, 格式={file_ext}")
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建临时输入文件
            input_path = os.path.join(tmpdir, file_name)
            logger.debug(f"创建临时输入文件: {input_path}")
            with open(input_path, 'wb') as f:
                f.write(file_content)
            
            # 创建临时输出文件
            output_path = os.path.join(tmpdir, f"output_{os.path.splitext(file_name)[0]}.pdf")
            logger.debug(f"创建临时输出文件: {output_path}")
            
            # 根据文件类型选择转换方法
            if file_ext in ['.md']:
                # Markdown to PDF
                logger.info("正在将Markdown转换为PDF")
                self._md_to_pdf(input_path, output_path)
                logger.info("Markdown转PDF成功")
            elif file_ext in ['.doc', '.docx']:
                # Word to PDF
                logger.info("正在将Word文档转换为PDF")
                self._word_to_pdf(input_path, output_path)
                logger.info("Word转PDF成功")
            elif file_ext in ['.txt']:
                # Text to PDF
                logger.info("正在将文本文件转换为PDF")
                self._txt_to_pdf(input_path, output_path)
                logger.info("文本转PDF成功")
            else:
                logger.error(f"不支持的文件格式: {file_ext}")
                raise Exception(f"不支持的文件格式: {file_ext}")
            
            # 读取PDF内容
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
            
            logger.debug(f"PDF文件生成成功，大小={len(pdf_content)}字节")
            return pdf_content
    
    def _md_to_pdf(self, input_path, output_path):
        """将Markdown转换为PDF"""
        # 使用pypandoc转换Markdown到PDF
        pypandoc.convert_file(
            input_path,
            'pdf',
            outputfile=output_path,
            extra_args=['--pdf-engine=weasyprint']
        )
    
    def _word_to_pdf(self, input_path, output_path):
        """将Word文档转换为PDF"""
        # 使用pypandoc转换Word到PDF
        pypandoc.convert_file(
            input_path,
            'pdf',
            outputfile=output_path,
            extra_args=['--pdf-engine=weasyprint']
        )
    
    def _txt_to_pdf(self, input_path, output_path):
        """将文本文件转换为PDF，嵌入Noto Sans SC字体"""
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
        
        # 读取文本内容
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 创建段落，所有文本都使用NotoSC字体
        for line in content.split('\n'):
            para = Paragraph(line, style)
            story.append(para)
        
        # 生成PDF
        doc.build(story)
