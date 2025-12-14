from collections.abc import Generator
from typing import Any
import socket
import requests
import logging

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

# 获取日志器
logger = logging.getLogger(__name__)

class PrintStatusTool(Tool):
    """打印机状态查询工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """查询打印机状态"""
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port", 0))
        
        logger.info(f"接收到打印机状态查询请求: IP={printer_ip}, 端口={printer_port}")
        
        try:
            # 1. 验证打印机IP
            if not printer_ip:
                logger.warning("查询失败: 打印机IP为空")
                yield self.create_json_message({"result": "查询失败: 打印机IP为空"})
                return
            
            # 2. 自动检测协议
            protocol = self._detect_protocol(printer_ip, printer_port)
            logger.info(f"检测到协议: {protocol}")
            
            # 3. 查询打印机状态
            status = {}
            
            if protocol == "ipp" or printer_port == 631:
                # 使用IPP协议查询状态
                logger.info(f"使用IPP协议查询状态")
                status = self._get_status_ipp(printer_ip, printer_port)
            else:
                # 使用SNMP协议查询状态（默认）
                logger.info(f"使用SNMP协议查询状态")
                status = self._get_status_snmp(printer_ip)
            
            # 4. 返回状态信息
            logger.info(f"打印机状态查询成功，状态: {status}")
            yield self.create_json_message({"result": f"打印机状态查询成功", "status": status})
        except socket.error as e:
            logger.error(f"查询失败: 无法连接打印机 - {str(e)}")
            yield self.create_json_message({"result": f"查询失败: 无法连接打印机 - {str(e)}"})
        except ValueError as e:
            logger.error(f"查询失败: 参数无效 - {str(e)}")
            yield self.create_json_message({"result": f"查询失败: 参数无效 - {str(e)}"})
        except Exception as e:
            logger.exception(f"查询失败: {str(e)}")
            yield self.create_json_message({"result": f"查询失败: {str(e)}"})
    
    def _detect_protocol(self, printer_ip, printer_port):
        """根据端口自动检测打印协议"""
        protocol_map = {
            9100: "raw",  # RAW TCP/IP
            631: "ipp",   # IPP
            515: "lpd"    # LPD
        }
        
        return protocol_map.get(printer_port, "raw")
    
    def _get_status_ipp(self, printer_ip, printer_port):
        """使用IPP协议查询打印机状态"""
        logger.info(f"使用IPP协议查询打印机状态: {printer_ip}:{printer_port}")
        # IPP状态查询URL
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        logger.debug(f"IPP请求URL: {ipp_url}")
        
        # 构建IPP请求属性
        attributes = [
            (0x47, 'attributes-charset', 'utf-8'),  # charset
            (0x48, 'attributes-natural-language', 'en-us'),  # language
            (0x45, 'printer-uri', f'ipp://{printer_ip}:{printer_port}/ipp/print'),  # printer URI
        ]
        logger.debug(f"IPP请求属性: {attributes}")
        
        # 构建IPP请求
        ipp_data = self._build_ipp_request(
            operation_id=0x0001,  # Get-Printer-Attributes操作码
            attributes=attributes
        )
        logger.debug(f"IPP请求数据大小: {len(ipp_data)}字节")
        
        # 发送IPP请求
        headers = {
            "Content-Type": "application/ipp",
            "Host": f"{printer_ip}:{printer_port}",
            "Connection": "close"
        }
        logger.debug(f"IPP请求头部: {headers}")
        
        response = requests.post(ipp_url, data=ipp_data, headers=headers, timeout=10)
        logger.debug(f"IPP响应状态码: {response.status_code}")
        response.raise_for_status()
        
        # 解析IPP响应
        if response.content:
            logger.debug(f"IPP响应数据大小: {len(response.content)}字节")
            status_code, request_id, attributes = self._parse_ipp_response(response.content)
            logger.debug(f"IPP响应解析成功: 状态码={status_code}, 请求ID={request_id}, 属性数量={len(attributes)}")
            
            # 提取关键状态信息
            status = {
                "protocol": "ipp",
                "status_code": status_code,
                "attributes": attributes
            }
            
            # 转换状态码为可读信息
            if status_code == 0x0000 or (0x0100 <= status_code <= 0x01ff):
                status["status"] = "正常"
                logger.info(f"IPP查询成功，打印机状态正常")
            elif 0x0200 <= status_code <= 0x02ff:
                status["status"] = "警告"
                logger.warning(f"IPP查询成功，打印机状态警告")
            else:
                status["status"] = "错误"
                logger.error(f"IPP查询成功，打印机状态错误")
            
            return status
        
        logger.warning(f"IPP响应内容为空")
        return {"protocol": "ipp", "status": "未知"}
    
    def _get_status_snmp(self, printer_ip):
        """使用SNMP协议查询打印机状态"""
        logger.info(f"使用SNMP协议查询打印机状态: {printer_ip}")
        try:
            # 尝试导入SNMP库
            from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
            logger.debug("SNMP库导入成功")
            
            # 打印机状态OID映射
            oids = {
                "printer_status": "1.3.6.1.2.1.25.3.5.1.1.1",  # hrPrinterStatus
                "printer_model": "1.3.6.1.2.1.25.3.2.1.3.1",  # hrDeviceDescr
                "toner_level": "1.3.6.1.2.1.43.11.1.1.9.1.1"  # prtMarkerSuppliesLevel
            }
            logger.debug(f"SNMP OID映射: {oids}")
            
            status = {"protocol": "snmp", "status": "未知"}
            
            # 获取打印机基本状态
            logger.debug("正在获取打印机基本状态...")
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(SnmpEngine(),
                       CommunityData('public', mpModel=0),
                       UdpTransportTarget((printer_ip, 161)),
                       ContextData(),
                       ObjectType(ObjectIdentity(oids["printer_status"])))
            )
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    status_value = int(varBind[1])
                    # hrPrinterStatus映射
                    status_map = {
                        1: "其他",
                        2: "未知",
                        3: "空闲",
                        4: "打印",
                        5: "预热",
                        6: "停止",
                        7: "测试",
                        8: "维护"
                    }
                    status["status"] = status_map.get(status_value, "未知")
                    logger.info(f"SNMP获取打印机状态成功: {status['status']}")
            else:
                logger.warning(f"SNMP获取打印机状态失败: errorIndication={errorIndication}, errorStatus={errorStatus}")
            
            # 获取打印机型号
            logger.debug("正在获取打印机型号...")
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(SnmpEngine(),
                       CommunityData('public', mpModel=0),
                       UdpTransportTarget((printer_ip, 161)),
                       ContextData(),
                       ObjectType(ObjectIdentity(oids["printer_model"])))
            )
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    status["model"] = str(varBind[1])
                    logger.info(f"SNMP获取打印机型号成功: {status['model']}")
            else:
                logger.warning(f"SNMP获取打印机型号失败: errorIndication={errorIndication}, errorStatus={errorStatus}")
            
            # 获取墨粉余量
            logger.debug("正在获取墨粉余量...")
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(SnmpEngine(),
                       CommunityData('public', mpModel=0),
                       UdpTransportTarget((printer_ip, 161)),
                       ContextData(),
                       ObjectType(ObjectIdentity(oids["toner_level"])))
            )
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    status["toner_level"] = int(varBind[1])
                    logger.info(f"SNMP获取墨粉余量成功: {status['toner_level']}")
            else:
                logger.warning(f"SNMP获取墨粉余量失败: errorIndication={errorIndication}, errorStatus={errorStatus}")
            
            return status
        except ImportError:
            # 如果SNMP库不可用，使用基本的TCP连接测试
            logger.warning("SNMP库导入失败，将使用TCP连接测试")
            return self._get_status_tcp(printer_ip)
        except Exception as e:
            logger.exception(f"SNMP查询失败: {str(e)}")
            return self._get_status_tcp(printer_ip)
    
    def _get_status_tcp(self, printer_ip):
        """使用TCP连接测试打印机状态"""
        logger.info(f"使用TCP连接测试打印机状态: {printer_ip}")
        status = {"protocol": "tcp", "status": "未知"}
        
        # 测试常用打印机端口
        ports = [9100, 631, 515]
        logger.debug(f"将测试以下端口: {ports}")
        
        for port in ports:
            try:
                logger.debug(f"正在测试端口 {port}...")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect((printer_ip, port))
                    status["status"] = "正常"
                    status["open_port"] = port
                    logger.info(f"TCP端口 {port} 连接成功，打印机状态正常")
                    break
            except socket.error:
                logger.debug(f"TCP端口 {port} 连接失败")
                continue
        
        if status["status"] == "未知":
            logger.warning(f"所有测试端口都连接失败，打印机状态未知")
        
        return status
    
    def _build_ipp_request(self, operation_id, attributes, data=None):
        """构建标准IPP请求"""
        # IPP版本1.1
        version = b"\x01\x01"
        
        # 请求ID
        request_id = b"\x00\x00\x00\x01"
        
        # 开始构建IPP数据
        ipp_data = b""
        ipp_data += version
        ipp_data += operation_id.to_bytes(2, byteorder='big')
        ipp_data += request_id
        
        # 添加属性组：操作属性（组标签0x01）
        ipp_data += b"\x01"
        
        # 添加属性
        for attr_type, name, value in attributes:
            # 属性名称长度和值
            ipp_data += attr_type.to_bytes(1, byteorder='big')
            ipp_data += len(name).to_bytes(2, byteorder='big')
            ipp_data += name.encode('utf-8')
            ipp_data += len(value).to_bytes(2, byteorder='big')
            ipp_data += value.encode('utf-8')
        
        # 结束属性组
        ipp_data += b"\x03"
        
        # 添加数据（如果有）
        if data:
            ipp_data += data
        
        return ipp_data
    
    def _parse_ipp_response(self, response_data):
        """解析IPP响应"""
        # 跳过版本号（2字节）和状态码（2字节）
        status_code = int.from_bytes(response_data[2:4], byteorder='big')
        request_id = int.from_bytes(response_data[4:8], byteorder='big')
        
        # 解析响应数据
        offset = 8
        attributes = {}
        
        while offset < len(response_data):
            # 读取组标签
            group_tag = response_data[offset]
            offset += 1
            
            if group_tag == 0x03:  # 结束标签
                break
            
            # 读取属性
            while offset < len(response_data):
                attr_type = response_data[offset]
                offset += 1
                
                if attr_type == 0x03:  # 结束标签
                    break
                
                # 读取名称长度和值
                name_len = int.from_bytes(response_data[offset:offset+2], byteorder='big')
                offset += 2
                name = response_data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                value_len = int.from_bytes(response_data[offset:offset+2], byteorder='big')
                offset += 2
                value = response_data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                
                attributes[name] = value
        
        return status_code, request_id, attributes
