# LisM トラックボール設定ツール

LisM (ZMK / PAW3222トラックボール) 用の個人利用ツール。
`config/lism_right.conf` と `snippets/trackball-central/trackball.overlay` の
トラックボール設定をGUIで編集し、
GitHubへpush → GitHub Actionsでビルド → ファームウェア取得 → ボードへ書き込み、まで行う。

roBaリポジトリの `roba-tuner` と同じ設計。roBaと違い、CPI等はKconfigではなく
devicetreeのプロパティ(`res-cpi`等)で設定されるため、`overlay_props.py` が
それを直接編集する。「動かす速さに応じてカーソル速度が変わる」ポインタ加速機能も
roBaから移植済み(`src/input_processor_accel.c`)。

キーマップ自体の編集は [ZMK Studio](https://zmk.studio/) を使用する。
書き込み対象は ZMK Studio 対応版 (`lism_right_central_trackball_studio`)。

## 事前準備

1. Git / Python 3 がインストール済みであること
2. [GitHub CLI (`gh`)](https://cli.github.com/) がインストール済みで、`gh auth login` でログイン済みであること
3. リポジトリがこのPCにクローンされ、`origin` へpushできる状態であること

## 使い方

```bash
python tools/lism-tuner/main.py
```

1. 起動すると現在の設定が読み込まれる
2. CPI・Force Awake・軸反転・スクロール分周比・ポインタ加速を変更する
3. 「保存してビルド」を押すと、ファイル保存 → commit → push → GitHub Actionsのビルド完了待ち →
   ファームウェアダウンロード、まで自動実行される
4. ビルド完了後、右側(セントラル/トラックボール側)をブートローダーモード(リセット2回押し)にしてから
   「ボードに書き込み」を押すと、検出したUF2ドライブに書き込む
5. 「ZMK Studioを開く」ボタンで、インストール済みのZMK Studioアプリ(なければWeb版)を起動できる

## 注意

- このツールはリポジトリに実際に commit / push する
- ビルドはGitHub Actions上で行うため、push後の完了までインターネット接続とActionsの実行時間(数分程度)が必要
- 左側(ペリフェラル)の設定は変更しないため、書き込みも右側のみを対象にしている
