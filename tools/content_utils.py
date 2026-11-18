import io
import os
import tempfile
from xml.sax.saxutils import escape

import pypandoc
from PIL import Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.platypus import Image as RLImage

from .printer_utils import safe_download

_FONT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "_assets", "fonts", "static", "NotoSansSC-Regular.ttf"))
_MARGIN = 15 * mm


def is_url(content):
    return content.startswith(('http://', 'https://', 'ftp://'))


def fetch_content(content):
    """统一输入：文本或URL，返回 (字节内容, 类型txt/md/doc/docx/pdf/image)"""
    if is_url(content):
        data = safe_download(content)
        ext = content.split('?')[0].split('.')[-1].lower()
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp'):
            return data, 'image'
        if ext in ('pdf', 'md', 'doc', 'docx'):
            return data, ext
        return data, 'txt'
    data = content.encode('utf-8')
    if content.startswith('# '):
        return data, 'md'
    return data, 'txt'


def _body_style():
    pdfmetrics.registerFont(TTFont("NotoSC", _FONT))
    return ParagraphStyle(name="Body", fontName="NotoSC", fontSize=12, leading=16)


def _pandoc_pdf(data, kind, pagesize, out_path):
    import sys
    engine = os.path.join(os.path.dirname(sys.executable), "weasyprint")
    if not os.path.exists(engine):
        engine = "weasyprint"
    w_mm, h_mm = pagesize[0] / mm, pagesize[1] / mm
    css_path = out_path + ".css"
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(f"@page {{ size: {w_mm:.1f}mm {h_mm:.1f}mm; margin: 15mm; }}\n"
                f"@font-face {{ font-family: 'NotoSC'; src: url('{_FONT}'); }}\n"
                "body { font-family: 'NotoSC', sans-serif; }\n")
    with tempfile.NamedTemporaryFile(suffix="." + kind, delete=False) as f:
        f.write(data)
        input_path = f.name
    try:
        pypandoc.convert_file(
            input_path, 'pdf', outputfile=out_path,
            extra_args=[f'--pdf-engine={engine}', f'--css={css_path}'])
    finally:
        os.unlink(input_path)


def build_pdf(data, kind, pagesize):
    """按纸张尺寸排版为PDF；PDF输入原样返回"""
    if kind == 'pdf':
        return data
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.pdf")
        if kind == 'image':
            with Image.open(io.BytesIO(data)) as img:
                avail_w, avail_h = pagesize[0] - 2 * _MARGIN, pagesize[1] - 2 * _MARGIN
                scale = min(avail_w / img.width, avail_h / img.height)
                w, h = img.width * scale, img.height * scale
            doc = SimpleDocTemplate(out, pagesize=pagesize,
                                    topMargin=_MARGIN, bottomMargin=_MARGIN,
                                    leftMargin=_MARGIN, rightMargin=_MARGIN)
            im = RLImage(io.BytesIO(data), width=w, height=h)
            im.hAlign = "CENTER"
            doc.build([im])
        elif kind in ('md', 'doc', 'docx'):
            _pandoc_pdf(data, kind, pagesize, out)
        else:
            doc = SimpleDocTemplate(out, pagesize=pagesize,
                                    topMargin=_MARGIN, bottomMargin=_MARGIN,
                                    leftMargin=_MARGIN, rightMargin=_MARGIN)
            style = _body_style()
            text = data.decode('utf-8', errors='replace')
            doc.build([Paragraph(escape(line), style) for line in text.split('\n')])
        with open(out, 'rb') as f:
            return f.read()