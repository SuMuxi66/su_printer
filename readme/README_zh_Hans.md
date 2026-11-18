# su_printer — Dify 网络打印机插件

[English](../README.md) | **简体中文** | [日本語](README_ja_JP.md) | [Português (BR)](README_pt_BR.md)

[![GitHub license](https://img.shields.io/github/license/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/network)

在 Dify 工作流和 Agent 中直接驱动真实网络打印机——激光打印机与 ESC/POS 热敏票据打印机。粘贴文本或文档 URL，选择纸张大小，从**自动搜索的下拉菜单**中选中打印机，即可打印。

> **Docker 部署友好：** 全部依赖均可通过 pip 自动安装。无需 Ghostscript、无需系统软件包、无需定制 Dify 镜像——在标准 Docker 部署的 Dify 上安装插件即可使用。

## ✨ 功能特性

### 两个专用打印节点

| 节点 | 适用设备 | 输出 | 纸张设置 |
|------|----------|------|----------|
| **激光打印机**（`print_laser`） | 支持 PCL 的激光 / LED 打印机 | PCL5e 光栅 @300 dpi | A4 / A5 / B5 / Letter / Legal |
| **热敏打印机**（`print_thermal`） | ESC/POS 票据打印机（容大、芯烨、爱普生 TM 等） | ESC/POS 文本与光栅 @203 dpi | 58mm（384 点）/ 80mm（576 点） |

- **排版随纸张自适应**——文字先按所选纸张尺寸（或纸卷宽度）排版再渲染，打印端正居中，不歪斜、不裁切。
- **丰富的内容输入**——纯文本，或指向 **txt / Markdown / Word（.doc、.docx）/ PDF / 图片** 的 URL（`http`/`https`）。Markdown 与 Word 自动转换为排版规范的 PDF 页面；图片自动缩放至可打印区域。
- **中文清晰打印**——内置 Noto Sans SC 字体，激光与热敏输出中文均清晰锐利，彻底告别乱码。
- **多份打印**——单次调用可打印 1–10 份。

### 打印机 IP 自动搜索下拉

**打印机IP** 字段为动态下拉菜单。打开打印节点时，插件自动扫描局域网内开放 **9100** 端口（标准 RAW 打印端口）的主机，将发现的打印机全部列出——无需手填 IP。

- 并发扫描（128 线程），最多 1024 个地址，/24 网段约 1–2 秒，结果缓存 30 秒。
- 可解析主机名时，下拉标签会显示主机名。
- 扫描不到的打印机可在插件设置的 **手动补充IP** 中永久添加。

### 协议支持（激光节点）

| 端口 | 协议 | 说明 |
|------|------|------|
| 9100 | RAW TCP/IP | 大多数网络打印机的默认端口 |
| 631 | IPP | 现代网络打印机 / CUPS |
| 515 | LPD | 传统网络打印机 |

协议根据所选端口自动识别。热敏打印机使用 RAW TCP（9100）。

### 管理工具

- **查询打印机状态**（`print_status`）——通过 SNMP 查询打印机状态与墨粉/耗材余量。
- **打印队列管理**（`print_queue`）——通过 IPP 查看或取消打印作业。

## 📦 安装方法

### 从 Dify 插件市场安装

1. 打开 Dify 工作空间 → **插件**。
2. 搜索 **su_printer**，点击 **安装**。

### 本地安装

1. 从 [Releases](https://github.com/SuMuxi66/su_printer/releases) 下载 `su_printer.difypkg`（或自行打包，见下文）。
2. Dify → **插件** → **安装插件** → **本地包文件** → 上传 `.difypkg`。

所有 Python 依赖由 Dify 插件守护进程自动安装到插件的隔离环境中。

> **Docker 网络提示：** 插件运行在 `plugin_daemon` 容器内，请确保该容器能访问打印机所在局域网（Linux 宿主机上可为插件守护进程配置 `network_mode: host`，或打通 Docker 网络与打印机网段的路由）。

## ⚙️ 配置说明

需要 **Dify ≥ 1.5.1**（该版本引入插件动态下拉参数）。无需任何第三方 API Key 或令牌——以下两项设置由 Dify 以加密凭据形式存储。

打开 **插件 → su_printer → 设置**，配置：

| 设置项 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| **扫描网段** | 是 | `192.168.1.0/24` | 自动搜索打印机的局域网网段（扫描 9100 端口），最多 1024 个地址。请改为你的实际网段。 |
| **手动补充IP** | 否 | — | 逗号分隔的 IP（如 `192.168.1.201,192.168.1.202`），始终出现在下拉中，用于扫描不到的打印机。 |

## 🚀 使用指南

### 激光打印

1. 在工作流中添加 **激光打印机** 节点（或由 Agent 调用）。
2. **打印内容**：输入文本，或指向 txt/Markdown/Word/PDF/图片文件的 URL。
3. **纸张大小**：A4 / A5 / B5 / Letter / Legal——排版自动适配。
4. **打印机IP**：从自动搜索的下拉菜单中选择。
5. **打印机端口**：9100（RAW）/ 631（IPP）/ 515（LPD）。
6. **打印份数**：1–10。运行。

### 热敏（票据）打印

1. 添加 **热敏打印机** 节点。
2. **打印内容**：文本或文档/图片 URL。
3. **纸张宽度**：58mm 或 80mm——文本按纸宽自动换行，图片按纸宽缩放。
4. **打印机IP**：从下拉菜单选择。**端口**：通常为 9100。
5. **打印份数**：1–10。运行。

### 状态与队列

- **查询打印机状态**：填写打印机 IP（端口可选，自动检测），读取状态与耗材余量。
- **打印队列管理**：填写打印机 IP 与 IPP 端口（默认 631），选择 *查看队列* 或 *取消作业*；取消时需提供作业 ID。

## 🧱 工作原理

```
内容（文本 / URL）
   │  下载并识别类型（txt · md · doc/docx · pdf · 图片）
   ▼
按纸张排版的 PDF ── reportlab + 内置 Noto Sans SC（文本/图片）
   │                pypandoc（内置 pandoc）+ WeasyPrint（md/Word）
   ▼
光栅化 ── pypdfium2（纯 wheel 的 PDF 渲染器，无需 Ghostscript）
   │
   ├─ 激光：PCL5e @300 dpi，纸张指令（ESC&l#A）→ RAW / IPP / LPD
   └─ 热敏：ESC/POS @203 dpi，GBK 文本或 GS v 0 光栅 → RAW 9100
```

所有组件均以 pip wheel 或内置资源形式提供，因此插件可在 Docker 部署的 Dify 上干净安装，无任何宿主机前置依赖。

## 🔧 开发与贡献

环境要求：Python **3.12**、[Dify 插件 CLI](https://docs.dify.ai/plugin-dev-en/0312-publish-to-dify-marketplace)。

```bash
git clone https://github.com/SuMuxi66/su_printer.git
cd su_printer
pip install -r requirements.txt

# 打包为 su_printer.difypkg
dify plugin package .
```

### 代码结构

```
su_printer/
├── _assets/                  # 图标与内置 Noto Sans SC 字体
├── provider/
│   ├── su_printer.yaml       # 提供者配置与凭据表单（扫描网段、手动IP）
│   └── su_printer.py         # 凭据校验
├── tools/
│   ├── print_laser.py/.yaml      # 激光节点（PCL、纸张尺寸）
│   ├── print_thermal.py/.yaml    # 热敏节点（ESC/POS、纸宽）
│   ├── print_status.py/.yaml     # SNMP 状态查询
│   ├── print_queue.py/.yaml      # IPP 队列查看/取消
│   ├── printer_discovery.py      # 局域网扫描 → 动态下拉选项
│   ├── printer_utils.py          # 协议、PCL 与 ESC/POS 编码
│   └── content_utils.py          # 内容获取/转换 → 按纸张排版的 PDF
├── main.py                   # 插件入口
├── manifest.yaml             # 插件元信息
└── requirements.txt          # 纯 pip 依赖
```

### 关键依赖

| 包 | 用途 |
|----|------|
| `dify_plugin ==0.10.2` | 插件 SDK（纯工具插件的动态下拉需要 0.10+） |
| `pypdfium2` | PDF 光栅化——纯 wheel，替代 Ghostscript |
| `pypandoc-binary` | Markdown/Word → HTML/PDF——内置 pandoc 二进制 |
| `weasyprint` | HTML → PDF，支持 `@page` 纸张尺寸 CSS |
| `reportlab` | 文本/图片 → PDF 排版 |
| `Pillow` | 图像处理与抖动 |
| `pysnmp` | 打印机状态 / 耗材余量 |
| `requests` | URL 内容下载 |

### 贡献指南

1. Fork 本仓库。
2. 创建特性分支：`git switch -c feat/my-change`。
3. 提交更改：`git commit -m 'Add my change'`。
4. 推送分支：`git push origin feat/my-change`。
5. 打开 Pull Request。

欢迎提交 Issue 与打印机兼容性报告——请注明打印机型号与所用协议。

## 📄 许可证

MIT——详见 [LICENSE](../LICENSE)。

## 📞 联系方式

- GitHub: [@SuMuxi66](https://github.com/SuMuxi66)
- 项目链接: <https://github.com/SuMuxi66/su_printer>

---

**享受打印的乐趣！** 🖨️