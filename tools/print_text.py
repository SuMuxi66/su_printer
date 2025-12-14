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
    
    def _pdf_to_pcl(self, pdf_path, pcl_path):
        """将PDF转换为PCL5e格式，避免黑块问题"""
        # 使用Ghostscript将PDF转换为PCL5e，使用Brother防黑块标准参数
        try:
            subprocess.run(
                [
                    "gs",
                    "-dSAFER",
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-dEmbedAllFonts=true",
                    "-dNOTRANSPARENCY",
                    "-sFONTPATH=/app/assets/fonts",  # 必须使用绝对路径，Docker可访问
                    "-r300",
                    "-sDEVICE=ljet4",  # 必须使用PCL5e，不能用pxlmono/PCL6
                    f"-sOutputFile={pcl_path}",
                    pdf_path
                ],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"PDF转PCL失败: {e.stderr}")
        except FileNotFoundError:
            raise Exception("Ghostscript未安装，请先安装Ghostscript。安装命令: apt-get update && apt-get install -y ghostscript")
    
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
            protocol = self._detect_protocol(printer_ip, printer_port)
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
                self._pdf_to_pcl(pdf_path, pcl_path)
                
                # 读取PCL内容
                with open(pcl_path, "rb") as f:
                    pcl_content = f.read()
                
                logger.info(f"生成PCL数据: 大小={len(pcl_content)}字节")
                
                # 5. 发送到打印机，根据份数重复发送
                for i in range(copies):
                    logger.info(f"发送第{i+1}/{copies}份到打印机")
                    if protocol == "raw":
                        logger.debug(f"使用RAW协议发送到{printer_ip}:{printer_port}")
                        self._send_raw(pcl_content, printer_ip, printer_port)
                    elif protocol == "ipp":
                        logger.debug(f"使用IPP协议发送到{printer_ip}:{printer_port}")
                        # IPP协议直接发送PCL内容
                        self._send_ipp(pcl_content, printer_ip, printer_port)
                    elif protocol == "lpd":
                        logger.debug(f"使用LPD协议发送到{printer_ip}:{printer_port}")
                        self._send_lpd(pcl_content, printer_ip, printer_port)
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
    
    def _detect_protocol(self, printer_ip, printer_port):
        """根据端口自动检测打印协议"""
        protocol_map = {
            9100: "raw",  # RAW TCP/IP
            631: "ipp",   # IPP
            515: "lpd"    # LPD
        }
        
        return protocol_map.get(printer_port, "raw")
    
    def _send_raw(self, content, printer_ip, printer_port):
        """使用RAW TCP/IP协议发送内容到打印机，分块发送避免黑块或丢页"""
        import socket
        # 创建TCP连接
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((printer_ip, printer_port))
            
            # 分块发送，每块8192字节，避免黑块或丢页
            chunk_size = 8192
            for i in range(0, len(content), chunk_size):
                s.sendall(content[i:i+chunk_size])
    
    def _send_ipp(self, content, printer_ip, printer_port):
        """使用IPP协议发送内容到打印机"""
        # 简化的IPP实现，使用HTTP POST直接发送PCL内容
        # 这种方式对大多数打印机更兼容
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        
        # 使用更简单的方法发送打印请求
        # 对于某些打印机，直接发送PCL内容可能比完整的IPP请求更有效
        headers = {
            "Content-Type": "application/octet-stream",
            "Host": f"{printer_ip}:{printer_port}",
            "Connection": "close"
        }
        
        # 直接发送PCL内容
        response = requests.post(ipp_url, data=content, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 简化响应处理
        if response.status_code != 200:
            raise Exception(f"IPP打印失败，状态码：{response.status_code}")
    
    def _send_lpd(self, content, printer_ip, printer_port):
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