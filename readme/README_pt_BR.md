# su_printer — Plugin de Impressora de Rede para Dify

[English](../README.md) | [简体中文](README_zh_Hans.md) | [日本語](README_ja_JP.md) | **Português (BR)**

[![GitHub license](https://img.shields.io/github/license/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/network)

Imprima diretamente dos seus workflows e agentes Dify em impressoras de rede reais — impressoras laser e impressoras térmicas de recibos ESC/POS. Cole um texto ou a URL de um documento, escolha o tamanho do papel, selecione a impressora em um **menu suspenso com descoberta automática** e imprima.

> **Compatível com Docker:** todas as dependências são instaláveis via pip. Sem Ghostscript, sem pacotes de sistema, sem imagens Dify personalizadas — instale o plugin em um Dify padrão implantado com Docker e funciona.

## ✨ Recursos

### Dois nós de impressão dedicados

| Nó | Equipamento | Saída | Configuração de papel |
|----|-------------|-------|----------------------|
| **Impressora Laser** (`print_laser`) | Impressoras laser / LED compatíveis com PCL | Raster PCL5e @ 300 dpi | A4 / A5 / B5 / Letter / Legal |
| **Impressora Térmica** (`print_thermal`) | Impressoras de recibos ESC/POS (Rongta, Xprinter, Epson TM, …) | Texto e raster ESC/POS @ 203 dpi | 58 mm (384 pontos) / 80 mm (576 pontos) |

- **Layout adaptado ao papel** — o texto é diagramado no tamanho de papel (ou largura da bobina) selecionado *antes* da renderização, então as páginas saem retas e centralizadas, sem tortas ou cortadas.
- **Entrada de conteúdo rica** — texto simples, ou uma URL (`http`/`https`) apontando para arquivos **txt / Markdown / Word (.doc, .docx) / PDF / imagem**. Markdown e Word são convertidos em páginas PDF bem diagramadas; imagens são redimensionadas para a área imprimível.
- **CJK nítido** — a fonte Noto Sans SC incluída renderiza chinês (e outros idiomas CJK) com nitidez tanto na saída laser quanto térmica. Chega de caracteres corrompidos.
- **Cópias** — imprima de 1 a 10 cópias em uma única chamada.

### Menu suspenso com descoberta automática de impressoras

O campo **IP da Impressora** é um menu suspenso dinâmico. Ao abrir um nó de impressão, o plugin varre sua LAN em busca de hosts com a porta **9100** aberta (a porta padrão de impressão RAW) e lista todas as impressoras encontradas — sem digitar endereços IP.

- Varredura concorrente (128 workers), até 1024 endereços, ~1–2 s para uma /24, resultados em cache por 30 s.
- Nomes de host são resolvidos e exibidos como rótulos quando disponíveis.
- Impressoras que não respondem à varredura podem ser adicionadas permanentemente em **IPs Manuais** nas configurações do plugin.

### Protocolos suportados (nó laser)

| Porta | Protocolo | Observações |
|-------|-----------|-------------|
| 9100 | RAW TCP/IP | Padrão da maioria das impressoras de rede |
| 631 | IPP | Impressoras de rede modernas / CUPS |
| 515 | LPD | Impressoras de rede legadas |

O protocolo é detectado automaticamente a partir da porta selecionada. Impressoras térmicas usam RAW TCP (9100).

### Ferramentas de gerenciamento

- **Status da Impressora** (`print_status`) — consulta o estado da impressora e os níveis de toner/suprimentos via SNMP.
- **Fila de Impressão** (`print_queue`) — lista ou cancela trabalhos de impressão via IPP.

## 📦 Instalação

### Pelo Marketplace do Dify

1. Abra seu workspace Dify → **Plugins**.
2. Pesquise por **su_printer** e clique em **Instalar**.

### Por pacote local

1. Baixe `su_printer.difypkg` em [Releases](https://github.com/SuMuxi66/su_printer/releases) (ou gere você mesmo, veja abaixo).
2. Dify → **Plugins** → **Instalar plugin** → **Arquivo de pacote local** → envie o `.difypkg`.

Todas as dependências Python são instaladas automaticamente no ambiente isolado do plugin pelo daemon de plugins do Dify.

> **Nota de rede no Docker:** o plugin roda dentro do contêiner `plugin_daemon`. Garanta que esse contêiner alcance a LAN das impressoras (em hosts Linux, `network_mode: host` para o daemon de plugins, ou roteamento adequado entre a rede Docker e a sub-rede das impressoras, funciona bem).

## ⚙️ Configuração

Requer **Dify ≥ 1.5.1** (versão que introduziu parâmetros dynamic-select em plugins). Nenhuma chave de API ou token de terceiros é necessário — as duas configurações abaixo são armazenadas pelo Dify como credenciais criptografadas do plugin.

Abra **Plugins → su_printer → Configurações** e configure:

| Configuração | Obrigatória | Padrão | Descrição |
|--------------|-------------|--------|-----------|
| **Sub-rede de Varredura** | sim | `192.168.1.0/24` | Sub-rede LAN varrida em busca de impressoras (porta 9100). Máx. 1024 endereços. Ajuste para sua sub-rede real. |
| **IPs Manuais** | não | — | IPs separados por vírgula (ex.: `192.168.1.201,192.168.1.202`) que sempre aparecem no menu suspenso, para impressoras que a varredura não encontra. |

## 🚀 Uso

### Impressão laser

1. Adicione o nó **Impressora Laser** ao seu workflow (ou deixe um agente chamá-lo).
2. **Conteúdo**: digite texto, ou uma URL para um arquivo txt/Markdown/Word/PDF/imagem.
3. **Tamanho do Papel**: A4 / A5 / B5 / Letter / Legal — o layout se adapta automaticamente.
4. **IP da Impressora**: escolha no menu suspenso com descoberta automática.
5. **Porta**: 9100 (RAW) / 631 (IPP) / 515 (LPD).
6. **Cópias**: 1–10. Execute.

### Impressão térmica (recibos)

1. Adicione o nó **Impressora Térmica**.
2. **Conteúdo**: texto ou URL de documento/imagem.
3. **Largura do Papel**: 58 mm ou 80 mm — o texto quebra linha e as imagens escalam conforme a largura da bobina.
4. **IP da Impressora**: escolha no menu suspenso. **Porta**: geralmente 9100.
5. **Cópias**: 1–10. Execute.

### Status e fila

- **Status da Impressora**: informe o IP da impressora (porta opcional, detectada automaticamente) para ler o estado e os níveis de suprimentos.
- **Fila de Impressão**: informe o IP e a porta IPP (padrão 631), escolha *listar* ou *cancelar*; para cancelar, forneça o ID do trabalho.

## 🧱 Como funciona

```
conteúdo (texto / URL)
   │  baixar e detectar tipo (txt · md · doc/docx · pdf · imagem)
   ▼
PDF diagramado conforme o papel ── reportlab + Noto Sans SC incluída (texto/imagens)
   │                               pypandoc (pandoc incluído) + WeasyPrint (md/Word)
   ▼
rasterização ── pypdfium2 (renderizador PDF em wheel puro, sem Ghostscript)
   │
   ├─ laser:   PCL5e @300 dpi, comando de papel (ESC&l#A) → RAW / IPP / LPD
   └─ térmica: ESC/POS @203 dpi, texto GBK ou raster GS v 0 → RAW 9100
```

Tudo é distribuído como wheels pip ou recursos incluídos, por isso o plugin instala de forma limpa em Dify implantado com Docker, sem pré-requisitos no host.

## 🔧 Desenvolvimento

Requisitos: Python **3.12**, [CLI de plugins Dify](https://docs.dify.ai/plugin-dev-en/0312-publish-to-dify-marketplace).

```bash
git clone https://github.com/SuMuxi66/su_printer.git
cd su_printer
pip install -r requirements.txt

# empacotar em su_printer.difypkg
dify plugin package .
```

### Estrutura do projeto

```
su_printer/
├── _assets/                  # ícones e fonte Noto Sans SC incluída
├── provider/
│   ├── su_printer.yaml       # config do provedor e esquema de credenciais (sub-rede, IPs manuais)
│   └── su_printer.py         # validação de credenciais
├── tools/
│   ├── print_laser.py/.yaml      # nó laser (PCL, tamanhos de papel)
│   ├── print_thermal.py/.yaml    # nó térmico (ESC/POS, larguras de bobina)
│   ├── print_status.py/.yaml     # consulta de status SNMP
│   ├── print_queue.py/.yaml      # listar/cancelar fila IPP
│   ├── printer_discovery.py      # varredura LAN → opções do menu dinâmico
│   ├── printer_utils.py          # protocolos, codificação PCL e ESC/POS
│   └── content_utils.py          # buscar/converter conteúdo → PDF conforme o papel
├── main.py                   # ponto de entrada do plugin
├── manifest.yaml             # metadados do plugin
└── requirements.txt          # dependências somente pip
```

### Dependências principais

| Pacote | Finalidade |
|--------|-----------|
| `dify_plugin ==0.10.2` | SDK do plugin (0.10+ necessário para select dinâmico em provedores só de ferramentas) |
| `pypdfium2` | Rasterização de PDF — wheel puro, substitui o Ghostscript |
| `pypandoc-binary` | Markdown/Word → HTML/PDF — binário pandoc incluído |
| `weasyprint` | HTML → PDF com CSS de tamanho de papel `@page` |
| `reportlab` | Texto/imagem → layout PDF |
| `Pillow` | Processamento de imagem e dithering |
| `pysnmp` | Status da impressora / níveis de suprimentos |
| `requests` | Download de conteúdo por URL |

## 🤝 Contribuindo

1. Faça um fork do repositório.
2. Crie um branch de recurso: `git switch -c feat/my-change`.
3. Commit suas mudanças: `git commit -m 'Add my change'`.
4. Push: `git push origin feat/my-change`.
5. Abra um Pull Request.

Issues e relatos de compatibilidade de impressoras são bem-vindos — inclua o modelo da impressora e o protocolo usado.

## 📄 Licença

MIT — veja [LICENSE](../LICENSE) para detalhes.

## 📞 Contato

- GitHub: [@SuMuxi66](https://github.com/SuMuxi66)
- Projeto: <https://github.com/SuMuxi66/su_printer>

---

**Boas impressões!** 🖨️