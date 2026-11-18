import logging
import os
import tempfile
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from .content_utils import fetch_content, build_pdf
from .printer_discovery import fetch_ip_options
from .printer_utils import (
    send_escpos_text,
    image_to_escpos,
    pdf_to_escpos,
)

logger = logging.getLogger(__name__)

WIDTH_DOTS = {"58mm": 384, "80mm": 576}


class PrintThermalTool(Tool):
    """热敏打印机打印工具：文本按纸宽换行直发，图片/PDF/文档按纸宽光栅打印"""

    def _fetch_parameter_options(self, parameter: str):
        return fetch_ip_options(self.runtime.credentials, parameter)

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        content = tool_parameters.get("content")
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port", 9100))
        paper = tool_parameters.get("paper_width", "80mm")
        copies = int(tool_parameters.get("copies", 1))

        logger.info(f"热敏打印请求: 打印机={printer_ip}:{printer_port}, 纸宽={paper}, 份数={copies}")

        try:
            if not content:
                yield self.create_json_message({"result": "打印失败: 内容为空"})
                return
            if paper not in WIDTH_DOTS:
                yield self.create_json_message({"result": f"打印失败: 不支持的纸宽 {paper}"})
                return
            if copies < 1 or copies > 10:
                yield self.create_json_message({"result": "打印失败: 打印份数必须在1-10之间"})
                return

            width = WIDTH_DOTS[paper]
            data, kind = fetch_content(content)
            logger.info(f"内容类型: {kind}, 大小={len(data)}字节, 光栅宽度={width}点")

            for i in range(copies):
                logger.info(f"发送第{i + 1}/{copies}份 (ESC/POS)")
                if kind == "txt":
                    send_escpos_text(data.decode("utf-8", errors="replace"),
                                     printer_ip, printer_port, width)
                elif kind == "image":
                    image_to_escpos(data, printer_ip, printer_port, width)
                else:
                    # md/docx/pdf：按纸宽排版为PDF后光栅化
                    page_w = width * 72 / 203
                    pdf = build_pdf(data, kind, (page_w, page_w * 200 / 58))
                    with tempfile.TemporaryDirectory() as tmp:
                        pdf_path = os.path.join(tmp, "input.pdf")
                        with open(pdf_path, "wb") as f:
                            f.write(pdf)
                        pdf_to_escpos(pdf_path, printer_ip, printer_port, width)

            yield self.create_json_message({
                "result": f"打印成功，共{copies}份，纸宽={paper}，模式：ESC/POS热敏"
            })
        except Exception as e:
            logger.exception(f"热敏打印失败: {e}")
            yield self.create_json_message({"result": f"打印失败: {str(e)}"})