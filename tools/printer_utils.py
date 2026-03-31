import os
import socket
import requests
import subprocess
import logging

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

def pdf_to_pcl(pdf_path, pcl_path):
    """将PDF转换为PCL5e格式，避免黑块问题"""
    logger.info(f"正在将PDF转换为PCL: 输入={pdf_path}, 输出={pcl_path}")
    
    # 动态获取当前项目的字体绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.abspath(os.path.join(current_dir, "..", "_assets", "fonts"))
    
    try:
        result = subprocess.run(
            [
                "gs",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-dEmbedAllFonts=true",
                "-dNOTRANSPARENCY",
                f"-sFONTPATH={font_path}",
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
        raise Exception("Ghostscript未安装，请先安装Ghostscript。")

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
