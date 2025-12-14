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
    
    def _detect_protocol(self, printer_port):
        """根据端口自动检测打印协议"""
        protocol_map = {
            9100: "raw",  # RAW TCP/IP
            631: "ipp",   # IPP
            515: "lpd"    # LPD
        }
        
        return protocol_map.get(printer_port, "raw")
    
    def _send_to_printer(self, pdf_content, printer_ip, printer_port):
        """将PDF内容发送到打印机"""
        # 检测协议
        protocol = self._detect_protocol(printer_port)
        logger.info(f"开始发送到打印机: 协议={protocol}, 打印机={printer_ip}:{printer_port}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建临时PDF文件
            pdf_path = os.path.join(tmpdir, "temp.pdf")
            logger.debug(f"创建临时PDF文件: {pdf_path}")
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)
            
            # 创建临时PCL文件
            pcl_path = os.path.join(tmpdir, "temp.pcl")
            logger.debug(f"创建临时PCL文件: {pcl_path}")
            
            # 将PDF转换为PCL
            logger.info("正在将PDF转换为PCL格式")
            self._pdf_to_pcl(pdf_path, pcl_path)
            logger.info("PDF转PCL成功")
            
            # 读取PCL内容
            with open(pcl_path, "rb") as f:
                pcl_content = f.read()
            logger.info(f"PCL内容读取成功，大小={len(pcl_content)}字节")
            
            # 发送PCL内容到打印机
            if protocol == "raw":
                # 使用RAW TCP/IP协议发送PCL
                logger.info(f"使用RAW协议发送PCL到{printer_ip}:{printer_port}")
                self._send_raw(pcl_content, printer_ip, printer_port)
                logger.debug("RAW协议发送成功")
            elif protocol == "ipp":
                # 使用IPP协议发送PCL
                logger.info(f"使用IPP协议发送PCL到{printer_ip}:{printer_port}")
                self._send_ipp(pcl_content, printer_ip, printer_port)
                logger.debug("IPP协议发送成功")
            elif protocol == "lpd":
                # 使用LPD协议发送PCL
                logger.info(f"使用LPD协议发送PCL到{printer_ip}:{printer_port}")
                self._send_lpd(pcl_content, printer_ip, printer_port)
                logger.debug("LPD协议发送成功")
            else:
                # 默认使用RAW协议发送PCL
                logger.warning(f"未知协议{protocol}，默认使用RAW协议发送")
                self._send_raw(pcl_content, printer_ip, printer_port)
                logger.debug("默认RAW协议发送成功")
    
    def _send_raw(self, content, printer_ip, printer_port):
        """使用RAW TCP/IP协议发送内容到打印机，分块发送避免黑块或丢页"""
        logger.info(f"使用RAW TCP/IP协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            logger.debug(f"正在连接打印机{printer_ip}:{printer_port}")
            s.connect((printer_ip, printer_port))
            logger.debug("连接成功，正在分块发送数据")
            
            # 分块发送，每块8192字节，避免黑块或丢页
            chunk_size = 8192
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                s.sendall(chunk)
                logger.debug(f"已发送 {min(i+chunk_size, len(content))}/{len(content)} 字节")
            
            logger.debug("数据发送完成")
    
    def _send_ipp(self, content, printer_ip, printer_port):
        """使用IPP协议发送内容到打印机"""
        logger.info(f"使用IPP协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
        import requests
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        logger.debug(f"IPP请求URL: {ipp_url}")
        
        headers = {
            "Content-Type": "application/pdf",
            "Host": f"{printer_ip}:{printer_port}",
            "Connection": "close"
        }
        logger.debug(f"IPP请求头部: {headers}")
        
        response = requests.post(ipp_url, data=content, headers=headers, timeout=10)
        logger.debug(f"IPP响应状态码: {response.status_code}")
        response.raise_for_status()
        logger.debug("IPP请求成功")
    
    def _pdf_to_pcl(self, pdf_path, pcl_path):
        """将PDF转换为PCL5e格式"""
        logger.info(f"正在将PDF转换为PCL: 输入={pdf_path}, 输出={pcl_path}")
        # 使用Ghostscript将PDF转换为PCL，使用Brother防黑块标准参数
        try:
            result = subprocess.run(
                [
                    "gs",
                    "-dSAFER",
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-dEmbedAllFonts=true",
                    "-dNOTRANSPARENCY",
                    "-sFONTPATH=/app/assets/fonts",  # 必须使用绝对路径，Docker可访问
                    "-r300",
                    "-sDEVICE=ljet4",  # 必须使用PCL5e，Brother最稳
                    f"-sOutputFile={pcl_path}",
                    pdf_path
                ],
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"Ghostscript执行成功: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ghostscript执行失败: {e.stderr}")
            raise Exception(f"PDF转PCL失败: {e.stderr}")
        except FileNotFoundError:
            logger.error("Ghostscript未安装")
            raise Exception("自动打印失败: 未安装Ghostscript")
    
    def _send_lpd(self, content, printer_ip, printer_port):
        """使用LPD协议发送内容到打印机"""
        logger.info(f"使用LPD协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            logger.debug(f"正在连接LPD打印机{printer_ip}:{printer_port}")
            s.connect((printer_ip, printer_port))
            logger.debug("LPD连接成功")
            
            # 1. 发送控制文件命令
            control_cmd = b"\x02lp\x00"
            logger.debug(f"发送LPD控制命令: {control_cmd}")
            s.sendall(control_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD控制命令响应: {response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制命令失败: {response}")
            logger.debug("LPD控制命令成功")
            
            # 2. 发送控制文件内容
            control_content = b"\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            logger.debug(f"发送LPD控制文件，大小：{len(control_content)}字节")
            s.sendall(f"{len(control_content):04x}".encode('ascii') + b"\x0a")
            s.sendall(control_content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD控制文件响应: {response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD控制文件发送失败: {response}")
            logger.debug("LPD控制文件发送成功")
            
            # 3. 发送数据文件命令
            data_cmd = b"\x03lp\x00"
            logger.debug(f"发送LPD数据命令: {data_cmd}")
            s.sendall(data_cmd)
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD数据命令响应: {response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据命令失败: {response}")
            logger.debug("LPD数据命令成功")
            
            # 4. 发送数据文件内容
            logger.debug(f"发送LPD数据文件，大小：{len(content)}字节")
            s.sendall(f"{len(content):04x}".encode('ascii') + b"\x0a")
            s.sendall(content)
            s.sendall(b"\x00")
            
            # 接收服务器响应
            response = s.recv(1024)
            logger.debug(f"LPD数据文件响应: {response}")
            if response[0:1] != b"\x00":
                raise Exception(f"LPD数据文件发送失败: {response}")
            logger.debug("LPD数据文件发送成功")
    
    def _send_pcl_to_printer(self, pcl_content, printer_ip, printer_port):
        """将PCL内容发送到打印机"""
        logger.info(f"使用RAW TCP/IP协议发送PCL内容到{printer_ip}:{printer_port}，数据大小={len(pcl_content)}字节")
        # 使用RAW TCP/IP协议发送PCL内容
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            logger.debug(f"正在连接打印机{printer_ip}:{printer_port}")
            s.connect((printer_ip, printer_port))
            logger.debug("连接成功，正在发送PCL数据")
            s.sendall(pcl_content)
            logger.debug("PCL数据发送完成")
