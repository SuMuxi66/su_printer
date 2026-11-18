import logging
import os
import tempfile
from collections.abc import Generator
from typing import Any

from reportlab.lib.pagesizes import A4, A5, B5, LETTER, LEGAL

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from .content_utils import fetch_content, build_pdf
from .printer_discovery import fetch_ip_options
from .printer_utils import (
    PCL_PAPER_CODES,
    detect_protocol,
    pdf_to_pcl,
    send_raw,
    send_ipp_print_job,
    send_lpd,
)

logger = logging.getLogger(__name__)

PAGESIZES = {"A4": A4, "A5": A5, "B5": B5, "Letter": LETTER, "Legal": LEGAL}


class PrintLaserTool(Tool):
    """激光打印机打印工具：文本/URL内容按纸张尺寸排版为PCL光栅打印"""

    def _fetch_parameter_options(self, parameter: str):
        return fetch_ip_options(self.runtime.credentials, parameter)

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        content = tool_parameters.get("content")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port", 9100))
        paper = tool_parameters.get("paper_size", "A4")
        copies = int(tool_parameters.get("copies", 1))

        logger.info(f"激光打印请求: 打印机={printer_ip}:{printer_port}, 纸张={paper}, 份数={copies}")

        try:
            if not content:
                yield self.create_json_message({"result": "打印失败: 内容为空"})
                return
            if paper not in PAGESIZES:
                yield self.create_json_message({"result": f"打印失败: 不支持的纸张尺寸 {paper}"})
                return
            if copies < 1 or copies > 10:
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return

            data, kind = fetch_content(content)
            logger.info(f"内容类型: {kind}, 大小={len(data)}字节")
            pdf = build_pdf(data, kind, PAGESIZES[paper])

            with tempfile.TemporaryDirectory() as tmp:
                pdf_path = os.path.join(tmp, "input.pdf")
                pcl_path = os.path.join(tmp, "output.pcl")
                with open(pdf_path, "wb") as f:
                    f.write(pdf)
                pdf_to_pcl(pdf_path, pcl_path, PCL_PAPER_CODES[paper])
                with open(pcl_path, "rb") as f:
                    pcl = f.read()

            protocol = detect_protocol(printer_port)
            for i in range(copies):
                logger.info(f"发送第{i + 1}/{copies}份, 协议={protocol}")
                if protocol == "raw":
                    send_raw(pcl, printer_ip, printer_port)
                elif protocol == "ipp":
                    send_ipp_print_job(pcl, printer_ip, printer_port)
                elif protocol == "lpd":
                    send_lpd(pcl, printer_ip, printer_port)
                else:
                    yield self.create_json_message({"result": f"打印失败: 不支持的协议 - {protocol}"})
                    return

            yield self.create_json_message({
                "result": f"打印成功，共{copies}份，纸张={paper}，协议={protocol}，模式：PCL激光"
            })
        except Exception as e:
            logger.exception(f"激光打印失败: {e}")
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})