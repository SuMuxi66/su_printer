#!/usr/bin/env python3
"""测试插件日志输出功能"""

import sys
import logging
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置日志级别
def test_logging():
    """测试日志输出"""
    print("=== 测试插件日志功能 ===")
    
    # 尝试导入插件模块
    try:
        from tools.print_text import PrintTextTool
        from tools.print_url import PrintURLTool
        from tools.print_status import PrintStatusTool
        from tools.print_queue import PrintQueueTool
        from tools.doc_to_pdf import DocToPDFTool
        
        print("✓ 成功导入所有工具模块")
        
        # 配置日志
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        print("✓ 日志配置完成")
        
        # 创建测试用的工具实例
        print_text_tool = PrintTextTool()
        print_url_tool = PrintURLTool()
        print_status_tool = PrintStatusTool()
        print_queue_tool = PrintQueueTool()
        doc_to_pdf_tool = DocToPDFTool()
        
        print("✓ 成功创建所有工具实例")
        
        # 测试日志输出
        print("\n=== 测试日志输出 ===")
        print("测试 info 级别日志...")
        logging.info("这是一条测试 info 日志")
        
        print("测试 debug 级别日志...")
        logging.debug("这是一条测试 debug 日志")
        
        print("测试 warning 级别日志...")
        logging.warning("这是一条测试 warning 日志")
        
        print("测试 error 级别日志...")
        logging.error("这是一条测试 error 日志")
        
        print("\n=== 工具日志测试 ===")
        from tools.print_text import logger as text_logger
        text_logger.info("PrintTextTool 测试日志")
        
        from tools.print_url import logger as url_logger
        url_logger.info("PrintURLTool 测试日志")
        
        from tools.print_status import logger as status_logger
        status_logger.info("PrintStatusTool 测试日志")
        
        from tools.print_queue import logger as queue_logger
        queue_logger.info("PrintQueueTool 测试日志")
        
        from tools.doc_to_pdf import logger as pdf_logger
        pdf_logger.info("DocToPDFTool 测试日志")
        
        print("\n=== 测试完成 ===")
        print("所有日志测试通过！")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_logging()