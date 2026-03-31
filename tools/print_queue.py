from collections.abc import Generator
from typing import Any
import socket
import requests
import logging

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from .printer_utils import build_ipp_request, parse_ipp_response

# 获取日志器
logger = logging.getLogger(__name__)

class PrintQueueTool(Tool):
    """打印队列管理工具"""
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """管理打印队列"""
        printer_ip = tool_parameters.get("printer_ip")
        printer_port = int(tool_parameters.get("printer_port", 631))
        action = tool_parameters.get("action", "list")
        job_id = tool_parameters.get("job_id")
        
        logger.info(f"接收到打印队列管理请求: IP={printer_ip}, 端口={printer_port}, 操作={action}, 作业ID={job_id}")
        
        try:
            # 1. 验证打印机IP
            if not printer_ip:
                logger.warning("操作失败: 打印机IP为空")
                yield self.create_json_message({"result": "操作失败: 打印机IP为空"})
                return
            
            # 2. 执行相应操作
            if action == "list":
                # 查看打印队列
                logger.info(f"正在查询打印队列: {printer_ip}:{printer_port}")
                queue = self._get_print_queue(printer_ip, printer_port)
                logger.info(f"打印队列查询成功，共{queue.get('total_jobs', 0)}个作业")
                yield self.create_json_message({"result": "打印队列查询成功", "queue": queue})
            elif action == "cancel":
                # 取消打印作业
                if not job_id:
                    logger.warning("操作失败: 作业ID为空")
                    yield self.create_json_message({"result": "操作失败: 作业ID为空"})
                    return
                
                logger.info(f"正在取消打印作业: 作业ID={job_id}, 打印机={printer_ip}:{printer_port}")
                result = self._cancel_print_job(printer_ip, printer_port, job_id)
                logger.info(f"打印作业取消结果: {result}")
                yield self.create_json_message({"result": result})
            else:
                logger.warning(f"操作失败: 不支持的操作 - {action}")
                yield self.create_json_message({"result": f"操作失败: 不支持的操作 - {action}"})
        except socket.error as e:
            logger.error(f"操作失败: 无法连接打印机 - {str(e)}")
            yield self.create_json_message({"result": f"操作失败: 无法连接打印机 - {str(e)}"})
        except ValueError as e:
            logger.error(f"操作失败: 参数无效 - {str(e)}")
            yield self.create_json_message({"result": f"操作失败: 参数无效 - {str(e)}"})
        except Exception as e:
            logger.exception(f"操作失败: {str(e)}")
            yield self.create_json_message({"result": f"操作失败: {str(e)}"})
    
    def _get_print_queue(self, printer_ip, printer_port):
        """获取打印队列"""
        logger.info(f"开始获取打印队列: {printer_ip}:{printer_port}")
        # IPP请求URL
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
        ipp_data = build_ipp_request(
            operation_id=0x000B,  # Get-Jobs操作码
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
            status_code, request_id, attributes, job_attributes = parse_ipp_response(response.content)
            logger.debug(f"IPP响应解析成功: 状态码={status_code}, 请求ID={request_id}, 作业数量={len(job_attributes)}")
            
            # 整理作业列表
            jobs = []
            for job in job_attributes:
                job_info = {
                    "job_id": job.get('job-id', ''),
                    "job_name": job.get('job-name', ''),
                    "user_name": job.get('job-originating-user-name', ''),
                    "job_state": job.get('job-state', ''),
                    "job_state_reasons": job.get('job-state-reasons', ''),
                    "document_format": job.get('document-format', ''),
                    "job_uri": job.get('job-uri', '')
                }
                jobs.append(job_info)
                logger.debug(f"添加作业到队列: {job_info}")
            
            queue = {
                "protocol": "ipp",
                "printer_uri": f'ipp://{printer_ip}:{printer_port}/ipp/print',
                "total_jobs": len(jobs),
                "jobs": jobs
            }
            
            logger.info(f"打印队列获取成功，共{len(jobs)}个作业")
            return queue
        
        logger.warning("IPP响应内容为空")
        return {"protocol": "ipp", "total_jobs": 0, "jobs": []}
    
    def _cancel_print_job(self, printer_ip, printer_port, job_id):
        """取消打印作业"""
        logger.info(f"开始取消打印作业: 作业ID={job_id}, 打印机={printer_ip}:{printer_port}")
        # IPP请求URL
        ipp_url = f"http://{printer_ip}:{printer_port}/ipp/print"
        logger.debug(f"IPP请求URL: {ipp_url}")
        
        # 构建IPP请求属性
        attributes = [
            (0x47, 'attributes-charset', 'utf-8'),  # charset
            (0x48, 'attributes-natural-language', 'en-us'),  # language
            (0x45, 'printer-uri', f'ipp://{printer_ip}:{printer_port}/ipp/print'),  # printer URI
            (0x45, 'job-uri', f'ipp://{printer_ip}:{printer_port}/ipp/print/{job_id}'),  # job URI
        ]
        logger.debug(f"IPP请求属性: {attributes}")
        
        # 构建IPP请求
        ipp_data = build_ipp_request(
            operation_id=0x0008,  # Cancel-Job操作码
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
            status_code, request_id, attributes, _ = parse_ipp_response(response.content)
            logger.debug(f"IPP响应解析成功: 状态码={status_code}, 请求ID={request_id}")
            
            # 检查操作是否成功
            if status_code == 0x0000 or (0x0100 <= status_code <= 0x01ff):
                logger.info(f"作业 {job_id} 已成功取消")
                return f"作业 {job_id} 已成功取消"
            else:
                logger.error(f"取消作业 {job_id} 失败，状态码：{status_code}")
                return f"取消作业 {job_id} 失败，状态码：{status_code}"
        
        logger.warning(f"取消作业 {job_id} 失败，未收到响应")
        return f"取消作业 {job_id} 失败，未收到响应"
