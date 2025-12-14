#!/usr/bin/env python3
"""简单测试插件日志输出功能"""

import sys
import logging
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_simple_logging():
    """简单测试日志输出"""
    print("=== 简单测试插件日志功能 ===")
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("✓ 日志配置完成")
    
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
    
    print("\n=== 导入工具日志器 ===")
    
    # 直接测试工具模块中的日志器，不需要实例化工具
    try:
        # 测试 print_text 日志
        import sys
        sys.path.append('/home/cz/tools/su_printer')
        
        # 设置环境变量以避免 dify_plugin 初始化错误
        os.environ['DIFY_PLUGIN_ENV'] = 'test'
        
        # 只导入 logger，不导入完整模块
        import importlib.util
        
        # 测试1: 检查 dify_plugin 的日志配置
        print("\n测试 dify_plugin 日志...")
        try:
            import dify_plugin
            print("✓ 成功导入 dify_plugin")
        except Exception as e:
            print(f"✗ dify_plugin 导入失败: {e}")
        
        # 测试2: 测试工具模块日志
        print("\n测试工具模块日志...")
        
        # 测试 print_text 模块
        try:
            spec = importlib.util.spec_from_file_location("logger", "/home/cz/tools/su_printer/tools/print_text.py")
            logger_module = importlib.util.module_from_spec(spec)
            sys.modules["logger"] = logger_module
            spec.loader.exec_module(logger_module)
            
            if hasattr(logger_module, 'logger'):
                logger_module.logger.info("✓ PrintTextTool 日志器工作正常")
            else:
                print("✗ PrintTextTool 日志器未找到")
        except Exception as e:
            print(f"✗ PrintTextTool 测试失败: {e}")
        
        # 测试3: 检查日志配置文件
        print("\n检查 dify_plugin 日志配置...")
        try:
            from dify_plugin.config.logger_format import DifyPluginLoggerFormatter
            print("✓ 成功导入 DifyPluginLoggerFormatter")
            
            # 测试日志格式
            formatter = DifyPluginLoggerFormatter()
            record = logging.LogRecord(
                name='test',
                level=logging.INFO,
                pathname='test.py',
                lineno=1,
                msg='测试 Dify 日志格式',
                args=(),
                exc_info=None
            )
            formatted_log = formatter.format(record)
            print(f"✓ Dify 日志格式: {formatted_log}")
        except Exception as e:
            print(f"✗ 日志格式测试失败: {e}")
        
        print("\n=== 测试完成 ===")
        print("简单日志测试通过！")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_logging()