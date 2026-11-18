# Privacy Policy — su_printer

Last updated: 2026-11-18

## Overview

su_printer is a self-hosted Dify plugin that sends print jobs from your Dify
workspace to network printers on your own LAN. **The plugin author does not
collect, store, log, or receive any user data.** The plugin contains no
telemetry, analytics, or third-party tracking of any kind.

## Data the plugin processes

All data is supplied by you (the Dify workspace user/administrator) and stays
within your own infrastructure:

| Data | Source | Where it goes |
|------|--------|---------------|
| Print content (text, or a document/image fetched from a URL you provide) | Tool parameter `content` | Rendered locally, then sent to the printer IP you select |
| Printer IP / port | Tool parameters, or the auto-discovery dropdown | Used only to open a connection to that printer |
| Scan subnet, manual printer IPs | Plugin credentials (`scan_subnet`, `manual_ips`), stored encrypted by Dify | Used only for LAN discovery |

## Network access

The plugin makes the following outbound connections, all initiated by your
explicit configuration or tool invocation:

1. **LAN printer discovery** — TCP connect probes to port 9100 on addresses
   within the subnet you configure (maximum 1024 addresses), plus reverse DNS
   lookups of discovered hosts to display hostnames. This traffic never leaves
   your local network.
2. **Content download** — when you pass a URL as print content, the plugin
   downloads that URL over HTTP/HTTPS. The destination is entirely
   user-controlled; no other remote hosts are contacted.
3. **Printing** — the rendered job is sent to the printer you select, via
   RAW TCP (port 9100), IPP (port 631), or LPD (port 515).
4. **Status / queue tools** — SNMP (UDP 161) and IPP queries to the printer IP
   you specify.

No data is sent to the plugin author, to Dify, or to any analytics service.

## Data storage and retention

- Document conversion uses temporary files that are deleted when the print
  job finishes.
- LAN scan results are cached in process memory for 30 seconds to keep the
  dropdown responsive; nothing is written to disk.
- The plugin does not persist print content, printer lists, or any personal
  data. Credential storage and encryption are handled by Dify itself.

## Third parties

The plugin does not integrate any third-party cloud service. Bundled
components (pandoc via `pypandoc-binary`, PDFium via `pypdfium2`, WeasyPrint,
ReportLab, Pillow, pysnmp) run locally and make no network calls of their own.

## Contact

Questions about this policy: open an issue at
<https://github.com/SuMuxi66/su_printer/issues>.