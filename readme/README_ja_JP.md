# su_printer — Dify 用ネットワークプリンタープラグイン

[English](../README.md) | [简体中文](README_zh_Hans.md) | **日本語** | [Português (BR)](README_pt_BR.md)

[![GitHub license](https://img.shields.io/github/license/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/SuMuxi66/su_printer)](https://github.com/SuMuxi66/su_printer/network)

Dify のワークフローやエージェントから、実際のネットワークプリンター（レーザープリンターと ESC/POS サーマルレシートプリンター）へ直接印刷できます。テキストやドキュメント URL を貼り付け、用紙サイズを選び、**自動検索されるドロップダウン**からプリンターを選択するだけで印刷できます。

> **Docker 環境対応：** すべての依存関係は pip で自動インストールされます。Ghostscript もシステムパッケージもカスタム Dify イメージも不要——標準の Docker 版 Dify にプラグインをインストールするだけで動作します。

## ✨ 機能

### 2 種類の専用印刷ノード

| ノード | 対象機器 | 出力 | 用紙設定 |
|--------|----------|------|----------|
| **レーザープリンター**（`print_laser`） | PCL 対応レーザー / LED プリンター | PCL5e ラスター @300 dpi | A4 / A5 / B5 / Letter / Legal |
| **サーマルプリンター**（`print_thermal`） | ESC/POS レシートプリンター（Rongta、Xprinter、Epson TM など） | ESC/POS テキスト＆ラスター @203 dpi | 58mm（384 ドット）/ 80mm（576 ドット） |

- **用紙サイズに合わせたレイアウト**——選択した用紙サイズ（またはロール紙幅）に合わせて組版してからレンダリングするため、傾きや切れのない正しい印刷結果になります。
- **豊富なコンテンツ入力**——プレーンテキスト、または **txt / Markdown / Word（.doc、.docx）/ PDF / 画像** を指す URL（`http`/`https`）。Markdown と Word は適切なレイアウトの PDF に変換され、画像は印刷可能領域に合わせて自動縮小されます。
- **CJK（中国語・日本語）も鮮明**——Noto Sans SC フォントを同梱し、レーザー・サーマル両方で文字をくっきり印刷。文字化けとはおさらばです。
- **部数指定**——1 回の呼び出しで 1〜10 部印刷できます。

### プリンター IP の自動検索ドロップダウン

**プリンター IP** フィールドは動的ドロップダウンです。印刷ノードを開くと、プラグインが LAN 内でポート **9100**（標準 RAW 印刷ポート）を開いているホストをスキャンし、見つかったプリンターをすべて一覧表示します——IP の手入力は不要です。

- 並列スキャン（128 ワーカー）、最大 1024 アドレス、/24 で約 1〜2 秒、結果は 30 秒キャッシュ。
- 名前解決できた場合はホスト名をラベルに表示。
- スキャンで見つからないプリンターは、プラグイン設定の **手動追加 IP** で常時表示できます。

### 対応プロトコル（レーザーノード）

| ポート | プロトコル | 説明 |
|--------|-----------|------|
| 9100 | RAW TCP/IP | 多くのネットワークプリンターのデフォルト |
| 631 | IPP | 最新のネットワークプリンター / CUPS |
| 515 | LPD | レガシーなネットワークプリンター |

プロトコルは選択したポートから自動判定されます。サーマルプリンターは RAW TCP（9100）を使用します。

### 管理ツール

- **プリンターステータス**（`print_status`）——SNMP でプリンターの状態とトナー/サプライ残量を取得。
- **印刷キュー**（`print_queue`）——IPP で印刷ジョブの一覧表示・キャンセル。

## 📦 インストール

### Dify マーケットプレイスから

1. Dify ワークスペース → **プラグイン** を開く。
2. **su_printer** を検索して **インストール**。

### ローカルパッケージから

1. [Releases](https://github.com/SuMuxi66/su_printer/releases) から `su_printer.difypkg` をダウンロード（または下記の方法で自分でビルド）。
2. Dify → **プラグイン** → **プラグインをインストール** → **ローカルパッケージ** → `.difypkg` をアップロード。

Python 依存関係は Dify プラグインデーモンがプラグイン専用の隔離環境へ自動インストールします。

> **Docker ネットワークの注意：** プラグインは `plugin_daemon` コンテナ内で動作します。このコンテナからプリンターの LAN に到達できることを確認してください（Linux ホストではプラグインデーモンに `network_mode: host` を設定するか、Docker ネットワークとプリンターサブネット間のルーティングを通します）。

## ⚙️ 設定

**Dify ≥ 1.5.1** が必要です（プラグインの動的セレクトパラメータが導入されたバージョン）。サードパーティの API キーやトークンは不要で、以下の設定は Dify によって暗号化された認証情報として保存されます。

**プラグイン → su_printer → 設定** で以下を構成します：

| 設定項目 | 必須 | デフォルト | 説明 |
|----------|------|-----------|------|
| **スキャンサブネット** | はい | `192.168.1.0/24` | プリンターを検索する LAN サブネット（ポート 9100 をスキャン）。最大 1024 アドレス。実際のサブネットに変更してください。 |
| **手動追加 IP** | いいえ | — | カンマ区切りの IP（例：`192.168.1.201,192.168.1.202`）。スキャンで見つからないプリンターをドロップダウンに常時表示します。 |

## 🚀 使い方

### レーザー印刷

1. ワークフローに **レーザープリンター** ノードを追加（またはエージェントに呼び出させる）。
2. **印刷内容**：テキスト、または txt/Markdown/Word/PDF/画像ファイルの URL。
3. **用紙サイズ**：A4 / A5 / B5 / Letter / Legal——レイアウトは自動で適応。
4. **プリンター IP**：自動検索ドロップダウンから選択。
5. **ポート**：9100（RAW）/ 631（IPP）/ 515（LPD）。
6. **部数**：1〜10。実行。

### サーマル（レシート）印刷

1. **サーマルプリンター** ノードを追加。
2. **印刷内容**：テキストまたはドキュメント/画像の URL。
3. **用紙幅**：58mm または 80mm——テキストは幅で自動折り返し、画像は幅に合わせて縮小。
4. **プリンター IP**：ドロップダウンから選択。**ポート**：通常 9100。
5. **部数**：1〜10。実行。

### ステータスとキュー

- **プリンターステータス**：プリンター IP を入力（ポートは任意、自動判定）して状態とサプライ残量を取得。
- **印刷キュー**：プリンター IP と IPP ポート（デフォルト 631）を入力し、*一覧* または *キャンセル* を選択。キャンセル時はジョブ ID を指定。

## 🧱 仕組み

```
コンテンツ（テキスト / URL）
   │  取得して種別判定（txt · md · doc/docx · pdf · 画像）
   ▼
用紙に合わせた PDF レイアウト ── reportlab + 同梱 Noto Sans SC（テキスト/画像）
   │                            pypandoc（pandoc 同梱）+ WeasyPrint（md/Word）
   ▼
ラスター化 ── pypdfium2（純 wheel の PDF レンダラー、Ghostscript 不要）
   │
   ├─ レーザー：PCL5e @300 dpi、用紙コマンド（ESC&l#A）→ RAW / IPP / LPD
   └─ サーマル：ESC/POS @203 dpi、GBK テキストまたは GS v 0 ラスター → RAW 9100
```

すべての構成要素は pip wheel または同梱アセットとして提供されるため、Docker 版 Dify にホスト側の前提条件なしでクリーンにインストールできます。

## 🔧 開発

要件：Python **3.12**、[Dify プラグイン CLI](https://docs.dify.ai/plugin-dev-en/0312-publish-to-dify-marketplace)。

```bash
git clone https://github.com/SuMuxi66/su_printer.git
cd su_printer
pip install -r requirements.txt

# su_printer.difypkg にパッケージング
dify plugin package .
```

### プロジェクト構成

```
su_printer/
├── _assets/                  # アイコンと同梱 Noto Sans SC フォント
├── provider/
│   ├── su_printer.yaml       # プロバイダー設定と認証情報スキーマ（サブネット、手動 IP）
│   └── su_printer.py         # 認証情報の検証
├── tools/
│   ├── print_laser.py/.yaml      # レーザーノード（PCL、用紙サイズ）
│   ├── print_thermal.py/.yaml    # サーマルノード（ESC/POS、ロール紙幅）
│   ├── print_status.py/.yaml     # SNMP ステータス取得
│   ├── print_queue.py/.yaml      # IPP キュー一覧/キャンセル
│   ├── printer_discovery.py      # LAN スキャン → 動的ドロップダウン選択肢
│   ├── printer_utils.py          # プロトコル、PCL・ESC/POS エンコード
│   └── content_utils.py          # コンテンツ取得/変換 → 用紙対応 PDF
├── main.py                   # プラグインエントリーポイント
├── manifest.yaml             # プラグインメタデータ
└── requirements.txt          # pip のみの依存関係
```

### 主な依存関係

| パッケージ | 用途 |
|-----------|------|
| `dify_plugin ==0.10.2` | プラグイン SDK（ツール専用プロバイダーの動的セレクトには 0.10+ が必要） |
| `pypdfium2` | PDF ラスター化——純 wheel、Ghostscript の代替 |
| `pypandoc-binary` | Markdown/Word → HTML/PDF——pandoc バイナリ同梱 |
| `weasyprint` | HTML → PDF（`@page` 用紙サイズ CSS 対応） |
| `reportlab` | テキスト/画像 → PDF レイアウト |
| `Pillow` | 画像処理とディザリング |
| `pysnmp` | プリンター状態 / サプライ残量 |
| `requests` | URL コンテンツのダウンロード |

## 🤝 コントリビュート

1. リポジトリを Fork。
2. フィーチャーブランチを作成：`git switch -c feat/my-change`。
3. 変更をコミット：`git commit -m 'Add my change'`。
4. プッシュ：`git push origin feat/my-change`。
5. Pull Request を作成。

Issue やプリンター互換性報告も歓迎です——プリンターのモデル名とプロトコルを添えてください。

## 📄 ライセンス

MIT——詳細は [LICENSE](../LICENSE) を参照。

## 📞 連絡先

- GitHub: [@SuMuxi66](https://github.com/SuMuxi66)
- プロジェクト: <https://github.com/SuMuxi66/su_printer>

---

**楽しい印刷を！** 🖨️