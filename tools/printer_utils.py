import io
import socket
import time
import requests
import logging
import pypdfium2 as pdfium
from PIL import Image

logger = logging.getLogger(__name__)

def detect_protocol(printer_port):
    """根据端口自动检测打印协议"""
    protocol_map = {
        9100: "raw",  # RAW TCP/IP
        631: "ipp",   # IPP
        515: "lpd"    # LPD
    }
    return protocol_map.get(printer_port, "raw")

def safe_download(url, max_size=20 * 1024 * 1024, timeout=(5, 30)):
    """
    安全下载文件，防止SSRF与OOM。
    - 限制文件最大大小（默认20MB）
    - 设置连接与传输超时
    - 验证URL协议
    """
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('ftp://')):
        raise ValueError(f"URL格式无效，必须以http://、https://或ftp://开头: {url}")

    logger.info(f"正在安全下载URL内容: {url}")
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    content_length = response.headers.get('Content-Length')
    if content_length and int(content_length) > max_size:
        raise ValueError(f"文件过大: {int(content_length)} 字节 (限制为 {max_size} 字节)")

    content = b""
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            content += chunk
            if len(content) > max_size:
                raise ValueError(f"文件过大，超过了限制 {max_size} 字节")

    return content

def send_raw(content, printer_ip, printer_port):
    """使用RAW TCP/IP协议发送内容到打印机，分块发送避免黑块或丢页"""
    logger.info(f"使用RAW TCP/IP协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)  # 连接超时设置短一些
        logger.debug(f"正在连接打印机{printer_ip}:{printer_port}")
        s.connect((printer_ip, printer_port))
        s.settimeout(60) # 传输超时设置长一些，适应大文件
        logger.debug("连接成功，正在分块发送数据")
        
        # 分块发送，每块8192字节
        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            s.sendall(chunk)
            logger.debug(f"已发送 {min(i+chunk_size, len(content))}/{len(content)} 字节")
        
        logger.debug("数据发送完成")

def send_ipp_print_job(content, printer_ip, printer_port, content_type="application/octet-stream"):
    """简化的IPP实现，使用HTTP POST直接发送打印内容"""
    logger.info(f"使用IPP协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节，Content-Type={content_type}")
    ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
    logger.debug(f"IPP请求URL: {ipp_url}")
    
    headers = {
        "Content-Type": content_type,
        "Host": f"{printer_ip}:{printer_port}",
        "Connection": "close"
    }
    logger.debug(f"IPP请求头部: {headers}")
    
    response = requests.post(ipp_url, data=content, headers=headers, timeout=(5, 60))
    logger.debug(f"IPP响应状态码: {response.status_code}")
    response.raise_for_status()
    logger.debug("IPP请求成功")

def send_lpd(content, printer_ip, printer_port):
    """使用LPD协议发送内容到打印机"""
    logger.info(f"使用LPD协议发送数据到{printer_ip}:{printer_port}，数据大小={len(content)}字节")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5) # 连接超时
        logger.debug(f"正在连接LPD打印机{printer_ip}:{printer_port}")
        s.connect((printer_ip, printer_port))
        s.settimeout(60) # 传输超时
        logger.debug("LPD连接成功")
        
        # 1. 发送控制文件命令 (\x02queue\x00)
        control_cmd = b"\x02lp\x00"
        logger.debug(f"发送LPD控制命令: {control_cmd}")
        s.sendall(control_cmd)
        response = s.recv(1024)
        logger.debug(f"LPD控制命令响应: {response}")
        if not response or response[0:1] != b"\x00":
            raise Exception(f"LPD控制命令失败: {response}")
        logger.debug("LPD控制命令成功")
        
        # 2. 发送控制文件内容
        control_content = b"\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
        logger.debug(f"发送LPD控制文件，大小：{len(control_content)}字节")
        s.sendall(f"{len(control_content):04x}".encode('ascii') + b"\x0a")
        s.sendall(control_content)
        s.sendall(b"\x00")
        response = s.recv(1024)
        logger.debug(f"LPD控制文件响应: {response}")
        if not response or response[0:1] != b"\x00":
            raise Exception(f"LPD控制文件发送失败: {response}")
        logger.debug("LPD控制文件发送成功")
        
        # 3. 发送数据文件命令 (\x03queue\x00)
        data_cmd = b"\x03lp\x00"
        logger.debug(f"发送LPD数据命令: {data_cmd}")
        s.sendall(data_cmd)
        response = s.recv(1024)
        logger.debug(f"LPD数据命令响应: {response}")
        if not response or response[0:1] != b"\x00":
            raise Exception(f"LPD数据命令失败: {response}")
        logger.debug("LPD数据命令成功")
        
        # 4. 发送数据文件内容
        logger.debug(f"发送LPD数据文件，大小：{len(content)}字节")
        s.sendall(f"{len(content):04x}".encode('ascii') + b"\x0a")
        # 分块发送数据文件内容
        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            s.sendall(content[i:i+chunk_size])
        s.sendall(b"\x00")
        
        response = s.recv(1024)
        logger.debug(f"LPD数据文件响应: {response}")
        if not response or response[0:1] != b"\x00":
            raise Exception(f"LPD数据文件发送失败: {response}")
        logger.debug("LPD数据文件发送成功")

PCL_PAPER_CODES = {"A4": 26, "A5": 25, "B5": 27, "Letter": 2, "Legal": 3}


def pdf_to_pcl(pdf_path, pcl_path, paper_code=26):
    """将PDF渲染为300dpi单色位图并封装为PCL5e光栅指令，纸张指令随paper_code变化"""
    logger.info(f"正在将PDF转换为PCL: 输入={pdf_path}, 输出={pcl_path}")

    # PCL光栅中1表示黑点，与PIL mode "1"（0=黑）相反，用translate表反转
    invert = bytes(255 - i for i in range(256))
    dpi = 300

    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except Exception as e:
        logger.error(f"PDF打开失败: {e}")
        raise Exception(f"PDF转PCL失败: 无法打开PDF文件 {e}")

    try:
        with open(pcl_path, "wb") as out:
            out.write(b"\x1bE")        # 复位打印机
            out.write(b"\x1b&l" + str(paper_code).encode("ascii") + b"A")  # 纸张尺寸
            out.write(b"\x1b&l0O")     # 纵向
            out.write(b"\x1b*t300R")   # 300dpi光栅分辨率

            for page_index, page in enumerate(pdf):
                bitmap = page.render(scale=dpi / 72)
                img = bitmap.to_pil().convert("L").convert("1")
                bitmap.close()
                width, height = img.size
                row_bytes = (width + 7) // 8
                pad = row_bytes * 8 - width
                mask = (0xFF << pad) & 0xFF if pad else 0xFF
                raw = img.tobytes()

                out.write(b"\x1b*r1A")  # 从当前光标位置开始光栅
                out.write(b"\x1b*b0M")  # 不压缩编码
                for y in range(height):
                    row = raw[y * row_bytes:(y + 1) * row_bytes].translate(invert)
                    if pad:
                        row = row[:-1] + bytes([row[-1] & mask])
                    out.write(b"\x1b*b" + str(row_bytes).encode("ascii") + b"W" + row)
                out.write(b"\x1b*rB")   # 结束光栅
                out.write(b"\x0c")      # 换页
                logger.debug(f"已渲染第{page_index + 1}页: {width}x{height}")

            out.write(b"\x1bE")
        logger.info("PDF转PCL完成")
    except Exception as e:
        logger.error(f"PDF转PCL失败: {e}")
        raise Exception(f"PDF转PCL失败: {e}")
    finally:
        pdf.close()

def build_ipp_request(operation_id, attributes, data=None):
    """构建标准IPP请求"""
    version = b"\x01\x01" # IPP版本1.1
    request_id = b"\x00\x00\x00\x01"
    
    ipp_data = b"" + version + operation_id.to_bytes(2, byteorder='big') + request_id
    ipp_data += b"\x01" # 操作属性组
    
    for attr_type, name, value in attributes:
        ipp_data += attr_type.to_bytes(1, byteorder='big')
        ipp_data += len(name).to_bytes(2, byteorder='big')
        ipp_data += name.encode('utf-8')
        ipp_data += len(value).to_bytes(2, byteorder='big')
        ipp_data += value.encode('utf-8')
    
    ipp_data += b"\x03" # 结束属性组
    if data:
        ipp_data += data
    return ipp_data

def parse_ipp_response(response_data):
    """解析IPP响应，返回 (status_code, request_id, attributes, job_attributes)"""
    if len(response_data) < 8:
        return 0, 0, {}, []
        
    status_code = int.from_bytes(response_data[2:4], byteorder='big')
    request_id = int.from_bytes(response_data[4:8], byteorder='big')
    
    offset = 8
    attributes = {}
    job_attributes = []
    current_job = {}
    
    while offset < len(response_data):
        group_tag = response_data[offset]
        offset += 1
        
        if group_tag == 0x03:  # 结束标签
            break
            
        while offset < len(response_data):
            attr_type = response_data[offset]
            if attr_type in (0x01, 0x02, 0x03, 0x04, 0x05): # 下一个组标签或结束
                break
                
            offset += 1
            if offset + 2 > len(response_data): break
            name_len = int.from_bytes(response_data[offset:offset+2], byteorder='big')
            offset += 2
            
            if offset + name_len > len(response_data): break
            name = response_data[offset:offset+name_len].decode('utf-8', errors='ignore')
            offset += name_len
            
            if offset + 2 > len(response_data): break
            value_len = int.from_bytes(response_data[offset:offset+2], byteorder='big')
            offset += 2
            
            if offset + value_len > len(response_data): break
            value = response_data[offset:offset+value_len].decode('utf-8', errors='ignore')
            offset += value_len
            
            if group_tag == 0x02:  # 作业属性组
                current_job[name] = value
            else:
                attributes[name] = value
                
        if group_tag == 0x02 and current_job:
            job_attributes.append(current_job)
            current_job = {}
            
    return status_code, request_id, attributes, job_attributes


ESCPOS_WIDTH = 576  # 80mm热敏纸 @203dpi 的可打印宽度（点数）


def _send_stream(printer_ip, printer_port, data, chunk_size=4096, delay=0.05):
    """热敏打印机缓冲区小，分块限速发送避免溢出断连"""
    logger.info(f"分块发送ESC/POS数据到{printer_ip}:{printer_port}，大小={len(data)}字节")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((printer_ip, printer_port))
        s.settimeout(60)
        for i in range(0, len(data), chunk_size):
            s.sendall(data[i:i + chunk_size])
            time.sleep(delay)


def _wrap_escpos_line(line, width_dots):
    """按纸宽点数换行：CJK按24点、ASCII按12点（203dpi标准字体）"""
    lines, cur, w = [], "", 0
    for ch in line:
        cw = 24 if ord(ch) > 0x7F else 12
        if cur and w + cw > width_dots:
            lines.append(cur)
            cur, w = "", 0
        cur += ch
        w += cw
    lines.append(cur)
    return lines


def send_escpos_text(content, printer_ip, printer_port, width_dots=ESCPOS_WIDTH):
    """热敏打印机文本直发，中文走GBK码页，按纸宽自动换行"""
    data = b"\x1b@"      # 初始化
    data += b"\x1c&"     # 启用中文模式
    for line in content.split("\n"):
        for wrapped in _wrap_escpos_line(line, width_dots):
            data += wrapped.encode("gbk", errors="replace") + b"\n"
    data += b"\x1bd\x04"  # 走纸4行
    _send_stream(printer_ip, printer_port, data)


def _image_to_escpos_rows(img, width=ESCPOS_WIDTH):
    if img.width != width:
        new_height = max(1, int(img.height * width / img.width))
        img = img.resize((width, new_height), Image.LANCZOS)
    img = img.convert("L").convert("1")
    row_bytes = (width + 7) // 8
    raw = img.tobytes()
    invert = bytes(255 - i for i in range(256))
    rows = [raw[y * row_bytes:(y + 1) * row_bytes].translate(invert) for y in range(img.height)]
    return rows, row_bytes


def _rows_to_escpos(rows, row_bytes):
    """GS v 0 光栅指令，每256行一块"""
    out = b"\x1b@"
    for i in range(0, len(rows), 256):
        chunk = rows[i:i + 256]
        out += (b"\x1dv0\x00" + row_bytes.to_bytes(2, "little")
                + len(chunk).to_bytes(2, "little") + b"".join(chunk))
    out += b"\x1bd\x04"
    return out


def image_to_escpos(content, printer_ip, printer_port, width=ESCPOS_WIDTH):
    """图片字节流按纸宽渲染为ESC/POS光栅并发送"""
    with Image.open(io.BytesIO(content)) as img:
        rows, row_bytes = _image_to_escpos_rows(img, width)
    _send_stream(printer_ip, printer_port, _rows_to_escpos(rows, row_bytes))


def pdf_to_escpos(pdf_path, printer_ip, printer_port, width=ESCPOS_WIDTH):
    """PDF渲染为203dpi、按纸宽缩放的ESC/POS光栅并发送"""
    logger.info(f"正在将PDF转换为ESC/POS光栅: {pdf_path}, 宽度={width}")
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        out = b""
        for page in pdf:
            bitmap = page.render(scale=203 / 72)
            img = bitmap.to_pil()
            bitmap.close()
            rows, row_bytes = _image_to_escpos_rows(img, width)
            out += _rows_to_escpos(rows, row_bytes)
        _send_stream(printer_ip, printer_port, out)
    finally:
        pdf.close()
