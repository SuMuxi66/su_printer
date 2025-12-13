from collections.abc import Generator
from typing import Any
import os
import tempfile
import requests
import pypandoc
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class DocToPDFTool(Tool):
    """文档转PDF工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """将文档转换为PDF"""
        document_url = tool_parameters.get("document_url")
        
        try:
            # 1. 验证文档URL
            if not document_url:
                yield self.create_json_message({"result": "转换失败: 文档URL为空"})
                return
            
            # 2. 下载文档
            file_content, file_name = self._download_document(document_url)
            
            # 3. 检测文件类型
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # 4. 转换为PDF
            pdf_content = self._convert_to_pdf(file_content, file_ext, file_name)
            
            # 5. 返回转换结果
            yield self.create_json_message({"result": "文档转换成功", "pdf_content": pdf_content})
        except requests.RequestException as e:
            yield self.create_json_message({"result": f"转换失败: 下载文档失败 - {str(e)}"})
        except Exception as e:
            yield self.create_json_message({"result": f"转换失败: {str(e)}"})
    
    def _download_document(self, url):
        """从URL下载文档"""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 从URL获取文件名
        file_name = url.split('/')[-1].split('?')[0]
        if not file_name:
            file_name = "document"
        
        return response.content, file_name
    
    def _convert_to_pdf(self, file_content, file_ext, file_name):
        """将不同格式的文档转换为PDF"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建临时输入文件
            input_path = os.path.join(tmpdir, file_name)
            with open(input_path, 'wb') as f:
                f.write(file_content)
            
            # 创建临时输出文件
            output_path = os.path.join(tmpdir, f"output_{os.path.splitext(file_name)[0]}.pdf")
            
            # 根据文件类型选择转换方法
            if file_ext in ['.md']:
                # Markdown to PDF
                self._md_to_pdf(input_path, output_path)
            elif file_ext in ['.doc', '.docx']:
                # Word to PDF
                self._word_to_pdf(input_path, output_path)
            elif file_ext in ['.txt']:
                # Text to PDF
                self._txt_to_pdf(input_path, output_path)
            else:
                raise Exception(f"不支持的文件格式: {file_ext}")
            
            # 读取PDF内容
            with open(output_path, 'rb') as f:
                pdf_content = f.read()
            
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
        """将文本文件转换为PDF"""
        # 使用reportlab创建PDF
        doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=1 * inch, bottomMargin=1 * inch)
        styles = getSampleStyleSheet()
        story = []
        
        # 读取文本内容
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 创建段落
        for line in content.split('\n'):
            para = Paragraph(line, styles['Normal'])
            story.append(para)
        
        # 生成PDF
        doc.build(story)
