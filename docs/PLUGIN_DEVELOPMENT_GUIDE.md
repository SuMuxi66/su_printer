# Dify 打印机插件开发指南

## 1. 插件概述

本插件提供了向网络打印机发送打印请求的功能，支持多种打印协议和内容类型。

### 1.1 功能特性

- 支持文本直接打印
- 支持从URL下载内容打印（支持图片、PDF、文本）
- 支持多种打印协议：
  - RAW TCP/IP（端口9100）
  - IPP（Internet Printing Protocol，端口631）
  - LPD（Line Printer Daemon，端口515）
- 支持打印机状态查询
- 支持打印队列管理
- 支持中文等非ASCII字符打印
- 自动协议检测

## 2. 插件构建流程

### 2.1 环境准备

1. 安装Python 3.12或更高版本
2. 安装Dify CLI工具
3. 克隆或创建插件项目目录

### 2.2 项目结构

```
su_printer/
├── _assets/              # 插件资源文件
│   ├── icon.svg
│   └── icon-dark.svg
├── provider/             # 插件提供者配置
│   └── su_printer.yaml
├── tools/                # 工具定义
│   ├── print_text.py     # 文本打印工具
│   ├── print_text.yaml   # 文本打印配置
│   ├── print_url.py      # URL内容打印工具
│   ├── print_url.yaml    # URL内容打印配置
│   ├── print_status.py   # 打印机状态查询工具
│   ├── print_status.yaml # 打印机状态查询配置
│   ├── print_queue.py    # 打印队列管理工具
│   └── print_queue.yaml  # 打印队列管理配置
├── main.py               # 插件入口
├── manifest.yaml         # 插件元信息
├── requirements.txt      # 依赖列表
└── README.md             # 插件说明
```

### 2.3 开发步骤

#### 2.3.1 创建基础结构

1. 使用Dify CLI初始化插件项目
2. 创建插件元信息文件（manifest.yaml）
3. 创建插件入口文件（main.py）
4. 创建插件提供者配置（provider/su_printer.yaml）

#### 2.3.2 开发工具

1. **创建Python工具类**：
   - 继承自`dify_plugin.Tool`类
   - 实现`_invoke`方法处理工具调用
   - 实现相关辅助方法

2. **创建YAML配置文件**：
   - 定义工具身份信息
   - 定义工具参数
   - 定义工具描述
   - 配置工具元信息

3. **添加工具引用**：
   - 在`provider/su_printer.yaml`中添加工具引用

#### 2.3.3 测试和验证

1. 编译检查：
   ```bash
   python -m py_compile tools/*.py
   ```

2. 打包插件：
   ```bash
   cd /path/to/plugin/parent
   dify plugin package su_printer
   ```

3. 部署测试：
   - 将生成的`.difypkg`文件上传到Dify平台
   - 测试插件功能

## 3. 代码结构和规范

### 3.1 Python代码规范

1. **类命名**：
   - 工具类名应遵循`CamelCase`命名规范
   - 类名应包含`Tool`后缀，例如`PrintTextTool`

2. **方法命名**：
   - 公共方法使用`snake_case`命名
   - 私有方法使用`_snake_case`命名（单下划线前缀）

3. **参数处理**：
   - 从`tool_parameters`字典中获取参数
   - 提供合理的默认值
   - 进行参数验证

4. **异常处理**：
   - 捕获特定异常类型
   - 提供有意义的错误信息
   - 使用`yield self.create_json_message()`返回错误结果

### 3.2 YAML配置规范

所有工具配置文件必须使用相同的YAML结构：

```yaml
# 工具名称
identity:
  name: "tool_name"
  author: "author_name"
  label:
    en_US: "English Label"
    zh_Hans: "中文标签"
    pt_BR: "Portuguese Label"
    ja_JP: "Japanese Label"
description:
  human:
    en_US: "Human description in English"
    zh_Hans: "中文人类描述"
    pt_BR: "Descrição humana em português"
    ja_JP: "日本語の人間向け説明"
  llm: "LLM description"
parameters:
  - name: parameter_name
    type: string|number|boolean
    required: true|false
    label:
      en_US: "English Label"
      zh_Hans: "中文标签"
      pt_BR: "Portuguese Label"
      ja_JP: "Japanese Label"
    human_description:
      en_US: "Human description in English"
      zh_Hans: "中文人类描述"
      pt_BR: "Descrição humana em português"
      ja_JP: "日本語の人間向け説明"
    llm_description: "LLM description"
    form: llm
    # 其他可选字段
    default: default_value
    min: minimum_value
    max: maximum_value
    enum:
      - label: "Option Label"
        value: "option_value"
extra:
  python:
    source: tools/tool_file.py
    class: ToolClassName
```

### 3.3 协议支持规范

1. **协议自动检测**：
   ```python
   def _detect_protocol(self, printer_ip, printer_port):
       protocol_map = {
           9100: "raw",  # RAW TCP/IP
           631: "ipp",   # IPP
           515: "lpd"    # LPD
       }
       return protocol_map.get(printer_port, "raw")
   ```

2. **协议实现**：
   - 每个协议对应一个独立的方法，例如`_send_raw`、`_send_ipp`、`_send_lpd`
   - 方法应接受相同的参数格式
   - 方法应抛出适当的异常

## 4. 测试和验证

### 4.1 编译检查

在开发过程中，应定期进行编译检查，确保代码没有语法错误：

```bash
python -m py_compile tools/*.py
```

### 4.2 打包测试

每次修改后，应重新打包插件并进行测试：

```bash
cd /path/to/plugin/parent
dify plugin package su_printer
```

### 4.3 功能测试

1. **文本打印测试**：
   - 测试不同编码的文本打印
   - 测试不同打印协议
   - 测试不同打印份数

2. **URL内容打印测试**：
   - 测试文本URL打印
   - 测试图片URL打印
   - 测试PDF URL打印

3. **打印机状态查询测试**：
   - 测试IPP协议状态查询
   - 测试SNMP协议状态查询
   - 测试TCP连接测试

4. **打印队列管理测试**：
   - 测试查看打印队列
   - 测试取消打印作业

## 5. 问题预防措施

### 5.1 配置文件一致性

1. **统一YAML结构**：所有工具配置文件必须使用相同的YAML结构
2. **检查字段完整性**：确保所有必需字段都已填写
3. **验证引用关系**：确保所有工具都在provider配置中正确引用
4. **避免冗余配置**：删除不必要的配置字段

### 5.2 代码质量

1. **遵循编码规范**：使用统一的编码规范
2. **添加注释**：为复杂代码添加注释
3. **处理异常**：捕获并处理所有可能的异常
4. **使用类型提示**：添加适当的类型提示
5. **测试边界情况**：测试空值、无效值等边界情况

### 5.3 依赖管理

1. **明确依赖版本**：在requirements.txt中指定精确的依赖版本
2. **避免冲突**：确保依赖之间没有版本冲突
3. **定期更新**：定期更新依赖到最新稳定版本
4. **最小化依赖**：只添加必要的依赖

### 5.4 协议实现

1. **遵循标准协议**：严格按照协议规范实现
2. **处理不同打印机特性**：考虑不同品牌打印机的差异
3. **添加超时处理**：为网络请求添加适当的超时设置
4. **实现优雅降级**：在协议不支持时提供备选方案

### 5.5 安全性

1. **验证输入**：验证所有用户输入
2. **防止注入攻击**：对所有外部输入进行适当的转义
3. **保护敏感信息**：不存储或打印敏感信息
4. **使用安全连接**：优先使用HTTPS等安全连接

## 6. 常见问题及解决方案

### 6.1 插件解析失败

**问题**：Failed to parse response from plugin daemon

**解决方案**：
1. 检查所有YAML配置文件格式是否一致
2. 确保所有工具都在provider配置中正确引用
3. 检查YAML文件是否有语法错误
4. 确保所有Python文件都能正常编译

### 6.2 打印机连接失败

**问题**：无法连接到打印机

**解决方案**：
1. 检查打印机IP地址和端口是否正确
2. 检查打印机是否在线
3. 检查网络连接是否正常
4. 检查防火墙设置是否允许访问打印机端口

### 6.3 中文乱码

**问题**：打印的中文显示为乱码

**解决方案**：
1. 尝试使用不同的编码格式（UTF-8、GBK）
2. 确保打印机支持所选编码
3. 检查打印机驱动是否正确安装

### 6.4 IPP请求失败

**问题**：IPP请求返回错误

**解决方案**：
1. 检查打印机是否支持IPP协议
2. 检查IPP端口是否正确（默认631）
3. 检查IPP请求格式是否符合标准
4. 查看打印机日志获取详细错误信息

## 7. 部署和发布

### 7.1 打包插件

```bash
cd /path/to/plugin/parent
dify plugin package su_printer
```

### 7.2 上传到Dify平台

1. 登录Dify平台
2. 进入插件管理页面
3. 点击"上传插件"
4. 选择生成的`.difypkg`文件
5. 等待插件审核通过

### 7.3 更新插件

1. 修改插件代码或配置
2. 重新打包插件
3. 在Dify平台上传更新后的插件
4. 等待插件审核通过

## 8. 后续改进方向

1. **添加更多协议支持**：例如添加LPR协议支持
2. **增强打印机状态查询**：支持更多打印机状态参数
3. **添加打印模板支持**：允许用户自定义打印模板
4. **添加批量打印功能**：支持批量打印多个文件
5. **增强错误处理**：提供更详细的错误信息和解决方案
6. **添加打印机驱动支持**：支持更多打印机型号
7. **添加打印预览功能**：允许用户预览打印内容
8. **增强安全性**：添加认证和授权机制

## 9. 参考资源

- [Dify 插件开发文档](https://docs.dify.ai/zh-CN/developer-guide/plugin-development)
- [IPP 协议规范](https://tools.ietf.org/html/rfc8010)
- [LPD 协议规范](https://tools.ietf.org/html/rfc1179)
- [RAW TCP/IP 打印协议](https://en.wikipedia.org/wiki/RAW_printing)
- [SNMP 协议规范](https://tools.ietf.org/html/rfc3411)

## 10. 联系方式

如有问题或建议，欢迎联系插件开发者。
