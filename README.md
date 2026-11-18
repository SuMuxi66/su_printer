# su_printer — Network Printer Plugin for Dify

**English** | [Chinese](readme/README_zh_Hans.md) | [Japanese](readme/README_ja_JP.md) | [Portuguese (BR)](readme/README_pt_BR.md)

[![GitHub license](https://img.shields.io/github/license/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/network)

Print from your Dify workflows and agents to real network printers — laser printers and ESC/POS thermal receipt printers. Paste text or a document URL, pick a paper size, select a printer from an **auto-discovered dropdown**, and print.

> **Docker-friendly:** every dependency is pip-installable. No Ghostscript, no system packages, no custom Dify images — install the plugin on a standard Docker-deployed Dify and it just works.

## ✨ Features

### Two purpose-built print nodes

| Node | Target | Output | Paper settings |
|------|--------|--------|----------------|
| **Laser Printer** (`print_laser`) | PCL-compatible laser / LED printers | PCL5e raster @ 300 dpi | A4 / A5 / B5 / Letter / Legal |
| **Thermal Printer** (`print_thermal`) | ESC/POS receipt printers (Rongta, Xprinter, Epson TM, …) | ESC/POS text & raster @ 203 dpi | 58 mm (384 dots) / 80 mm (576 dots) |

- **Paper-size-aware layout** — text is typeset to the selected paper size (or roll width) *before* rendering, so pages come out straight and centered instead of skewed or clipped.
- **Rich content input** — plain text, or a URL (`http`/`https`) pointing to **txt / Markdown / Word (.doc, .docx) / PDF / image** files. Markdown and Word are converted to properly laid-out PDF pages; images are scaled to fit the printable area.
- **Clear CJK printing** — a bundled Noto Sans SC font renders Chinese (and other CJK) text crisply on both laser and thermal output. No more garbled characters.
- **Copies** — print 1–10 copies in one call.

### Auto-discovered printer dropdown

The **Printer IP** field is a dynamic dropdown. When you open a print node, the plugin scans your LAN for hosts with port **9100** open (the standard RAW printing port) and lists every printer it finds — no typing IP addresses.

- Concurrent scan (128 workers), up to 1024 addresses, ~1–2 s for a /24, results cached for 30 s.
- Hostnames are resolved and shown as labels when available.
- Printers that don't answer the scan can be added permanently via **Manual Printer IPs** in plugin settings.

### Protocol support (laser node)

| Port | Protocol | Notes |
|------|----------|-------|
| 9100 | RAW TCP/IP | Default for most network printers |
| 631 | IPP | Modern network printers / CUPS |
| 515 | LPD | Legacy network printers |

The protocol is detected automatically from the selected port. Thermal printers use RAW TCP (9100).

### Management tools

- **Print Status** (`print_status`) — query printer state and toner/supply levels via SNMP.
- **Print Queue** (`print_queue`) — list or cancel print jobs via IPP.

## 📦 Installation

### From the Dify Marketplace

1. Open your Dify workspace → **Plugins**.
2. Search for **su_printer** and click **Install**.

### From a local package

1. Download `su_printer.difypkg` from [Releases](https://github.com/SuMuxi66/su_printer/releases) (or build it yourself, see below).
2. Dify → **Plugins** → **Install plugin** → **Local package file** → upload the `.difypkg`.

All Python dependencies are installed automatically into the plugin's isolated environment by the Dify plugin daemon.

> **Docker networking note:** the plugin runs inside the `plugin_daemon` container. Make sure that container can reach your printers' LAN (on Linux hosts, `network_mode: host` for the plugin daemon, or proper routing between the Docker network and the printer subnet, works well).

## ⚙️ Configuration

Requires **Dify ≥ 1.5.1** (the version that introduced dynamic-select plugin parameters). No third-party API keys or tokens are needed — the two settings below are stored as encrypted plugin credentials by Dify itself.

Open **Plugins → su_printer → Settings** and configure:

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| **Scan Subnet** | yes | `192.168.1.0/24` | LAN subnet scanned for printers (port 9100). Max 1024 addresses. Set this to your actual subnet. |
| **Manual Printer IPs** | no | — | Comma-separated IPs (e.g. `192.168.1.201,192.168.1.202`) that always appear in the dropdown, for printers the scan can't find. |

## 🚀 Usage

### Laser printing

1. Add the **Laser Printer** node to your workflow (or let an agent call it).
2. **Print Content**: enter text, or a URL to a txt/Markdown/Word/PDF/image file.
3. **Paper Size**: A4 / A5 / B5 / Letter / Legal — layout adapts automatically.
4. **Printer IP**: pick from the auto-discovered dropdown.
5. **Printer Port**: 9100 (RAW) / 631 (IPP) / 515 (LPD).
6. **Copies**: 1–10. Run.

### Thermal (receipt) printing

1. Add the **Thermal Printer** node.
2. **Print Content**: text or a document/image URL.
3. **Paper Width**: 58 mm or 80 mm — text wraps and images scale to the roll width.
4. **Printer IP**: pick from the dropdown. **Port**: usually 9100.
5. **Copies**: 1–10. Run.

### Status & queue

- **Print Status**: enter the printer IP (port optional, auto-detected) to read state and supply levels.
- **Print Queue**: enter the printer IP and IPP port (default 631), choose *list* or *cancel*; for cancel, provide the job ID.

## 🧱 How it works

```
content (text / URL)
   │  fetch & detect type (txt · md · doc/docx · pdf · image)
   ▼
paper-aware PDF layout ── reportlab + bundled Noto Sans SC (text/images)
   │                      pypandoc (bundled pandoc) + WeasyPrint (md/Word)
   ▼
rasterize ── pypdfium2 (pure-wheel PDF renderer, no Ghostscript)
   │
   ├─ laser:   PCL5e @300 dpi, paper-size command (ESC&l#A) → RAW / IPP / LPD
   └─ thermal: ESC/POS @203 dpi, GBK text or GS v 0 raster → RAW 9100
```

Everything ships as pip wheels or bundled assets, which is why the plugin installs cleanly on Docker-deployed Dify with no host-level prerequisites.

## 🔧 Development

Requirements: Python **3.12**, [Dify plugin CLI](https://docs.dify.ai/plugin-dev-en/0312-publish-to-dify-marketplace).

```bash
git clone https://github.com/SuMuxi66/su_printer.git
cd su_printer
pip install -r requirements.txt

# package into su_printer.difypkg
dify plugin package .
```

### Project structure

```
su_printer/
├── _assets/                  # icons & bundled Noto Sans SC font
├── provider/
│   ├── su_printer.yaml       # provider config & credential schema (scan subnet, manual IPs)
│   └── su_printer.py         # credential validation
├── tools/
│   ├── print_laser.py/.yaml      # laser node (PCL, paper sizes)
│   ├── print_thermal.py/.yaml    # thermal node (ESC/POS, roll widths)
│   ├── print_status.py/.yaml     # SNMP status query
│   ├── print_queue.py/.yaml      # IPP queue list/cancel
│   ├── printer_discovery.py      # LAN scan → dynamic dropdown options
│   ├── printer_utils.py          # protocols, PCL & ESC/POS encoding
│   └── content_utils.py          # fetch/convert content → paper-aware PDF
├── main.py                   # plugin entrypoint
├── manifest.yaml             # plugin metadata
└── requirements.txt          # pip-only dependencies
```

### Key dependencies

| Package | Purpose |
|---------|---------|
| `dify_plugin ==0.10.2` | Plugin SDK (0.10+ required for dynamic-select on tool-only providers) |
| `pypdfium2` | PDF rasterization — pure wheel, replaces Ghostscript |
| `pypandoc-binary` | Markdown/Word → HTML/PDF — bundled pandoc binary |
| `weasyprint` | HTML → PDF with `@page` paper-size CSS |
| `reportlab` | Text/image → PDF layout |
| `Pillow` | Image processing & dithering |
| `pysnmp` | Printer status / supply levels |
| `requests` | URL content download |

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git switch -c feat/my-change`.
3. Commit your changes: `git commit -m 'Add my change'`.
4. Push: `git push origin feat/my-change`.
5. Open a Pull Request.

Issues and printer-compatibility reports are welcome — please include your printer model and protocol.

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

## 📞 Contact

- GitHub: [@SuMuxi66](https://github.com/SuMuxi66)
- Project: <https://github.com/SuMuxi66/su_printer>

---

**Happy printing!** 🖨️