# ntt-xg200ki-scraper

NTTのホームゲートウェイ「XG-200KI」のWeb管理画面から設定値、接続端末一覧、ログを取得し、ファイル（テキスト、Markdown、JSON）に保存するツール。

## 対象機種

本ツールは **XG-200KI 専用** です。NTTのレンタルルーターは機種（PR-500、RS-500、RX-600、XG-100NEなど）ごとに管理画面のHTML構造やCGI仕様が異なるため、他機種では動作しません。

## 動作環境

- Python 3.10 以上
- 依存パッケージ: `requests`, `beautifulsoup4`

```bash
pip install -r requirements.txt
```

## 使い方

1. 設定ファイルの作成
   `.env.example` を `.env` にコピーし、ルーターの接続情報を設定します。

   ```bash
   cp .env.example .env
   ```

   ```env
   ROUTER_HOST=192.168.1.1
   ROUTER_USER=user
   ROUTER_PASSWORD=your_password
   ```

2. 実行

   ```bash
   python main.py
   ```

## 出力ファイル

実行結果は `output/` ディレクトリに保存されます。

- `router_settings_report.txt`: 設定とログのプレーンテキスト
- `router_settings_report.md`: Markdown形式のレポート
- `router_settings.json`: 構造化JSONデータ

※ 初期化や再起動などの変更系CGIは巡回対象から除外し、参照系ページのみを取得します。

## 免責事項

- 本ツールは個人が作成した非公式ツールであり、東日本電信電話株式会社および西日本電信電話株式会社（NTT）とは関係ありません。
- 本ツールの利用に伴って生じたいかなる損害や不具合についても、作者は責任を負いません。自己責任でご利用ください。

## ライセンス

[MIT License](LICENSE)

