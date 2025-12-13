# Dify 打印机插件

[![GitHub license](https://img.shields.io/github/license/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/network)

一个功能强大的Dify打印机插件，支持多种打印协议和内容类型，提供友好的用户体验。

## 🌟 功能特性

### 打印功能
- ✅ **文本直接打印**：直接向打印机发送文本内容
- ✅ **URL内容打印**：从URL下载并打印内容
  - 支持文本文件
  - 支持图片（自动转换为ASCII）
  - 支持PDF文档（提取文本）

### 协议支持
- ✅ **RAW TCP/IP**：端口9100，适用于大多数网络打印机
- ✅ **IPP协议**：端口631，支持现代网络打印机
- ✅ **LPD协议**：端口515，支持传统网络打印机
- ✅ **自动协议检测**：根据端口自动选择合适的协议

### 管理功能
- ✅ **打印机状态查询**：查询打印机状态、墨粉余量等信息
- ✅ **打印队列管理**：查看和取消打印作业

### 其他特性
- ✅ **多语言支持**：支持中文、英文、日文、葡萄牙文
- ✅ **编码优化**：支持UTF-8、GBK、ASCII编码，解决中文乱码问题
- ✅ **友好界面**：使用下拉菜单优化用户体验
- ✅ **错误处理**：完善的错误提示和异常处理

## 🛠️ 技术栈

- **开发语言**：Python 3.12+
- **Dify SDK**：dify-plugin>=0.4.0
- **网络请求**：requests>=2.31.0
- **图片处理**：Pillow>=10.0.0
- **PDF处理**：PyPDF2>=3.0.0
- **SNMP支持**：pysnmp>=5.0.0

## 📦 安装方法

### 从Dify插件市场安装
1. 登录Dify平台
2. 进入插件管理页面
3. 搜索"su_printer"并安装

### 本地安装
1. 下载插件包：`su_printer.difypkg`
2. 登录Dify平台
3. 进入插件管理页面
4. 点击"上传插件"，选择下载的插件包

## 🚀 使用指南

### 文本打印

1. 选择"文本打印"工具
2. 填写打印机IP地址
3. 选择打印机端口
4. 输入要打印的文本内容
5. 选择合适的编码格式
6. 点击"执行"开始打印

### URL内容打印

1. 选择"URL内容打印"工具
2. 填写打印机IP地址
3. 选择打印机端口
4. 输入要打印的URL
5. 选择合适的编码格式
6. 点击"执行"开始打印

### 打印机状态查询

1. 选择"查询打印机状态"工具
2. 填写打印机IP地址
3. 选择打印机端口（可选，默认自动检测）
4. 点击"执行"查询状态

### 打印队列管理

1. 选择"打印队列管理"工具
2. 填写打印机IP地址
3. 选择打印机端口
4. 选择操作类型：
   - "查看队列"：查看当前打印队列
   - "取消作业"：取消指定的打印作业
5. 如需取消作业，填写作业ID
6. 点击"执行"执行操作

## ⚙️ 配置说明

### 端口与协议对应关系
| 端口 | 协议类型 | 描述 |
|------|---------|------|
| 9100 | RAW TCP/IP | 大多数网络打印机默认端口 |
| 631 | IPP | 现代网络打印机支持的协议 |
| 515 | LPD | 传统网络打印机支持的协议 |

### 编码选择建议
| 编码 | 适用场景 |
|------|---------|
| UTF-8 | 通用编码，支持多种语言 |
| GBK | 适用于中文环境，特别是Brother打印机 |
| ASCII | 仅适用于英文文本 |

## 🔧 开发与贡献

### 开发环境搭建

1. 克隆仓库：
   ```bash
   git clone https://github.com/SuMuxi66/su_printer.git
   cd su_printer
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 打包插件：
   ```bash
   dify plugin package .
   ```

### 代码结构

```
su_printer/
├── _assets/              # 插件资源文件
├── docs/                 # 文档
├── provider/             # 插件提供者配置
├── tools/                # 工具定义
│   ├── print_text.py     # 文本打印工具
│   ├── print_url.py      # URL内容打印工具
│   ├── print_status.py   # 打印机状态查询工具
│   └── print_queue.py    # 打印队列管理工具
├── main.py               # 插件入口
├── manifest.yaml         # 插件元信息
└── requirements.txt      # 依赖列表
```

### 贡献指南

1. Fork本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送到分支：`git push origin feature/AmazingFeature`
5. 打开Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看[LICENSE](LICENSE)文件了解详情

## 📞 联系方式

- GitHub: [@SuMuxi66](https://github.com/SuMuxi66)
- 项目链接: [https://github.com/SuMuxi66/su_printer](https://github.com/SuMuxi66/su_printer)

## 🙏 致谢

感谢所有为本项目做出贡献的开发者和用户！

---

**享受打印的乐趣！** 🎉
