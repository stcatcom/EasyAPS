[README.md](https://github.com/user-attachments/files/24559515/README.md)
# EasyAPS (Easy Automatic Program Scheduler)

EasyAPS は、ラジオ放送局向けの自動番組スケジューラーです。CSV形式のタイムテーブルに基づいて音源を自動再生し、スタジオモード（生放送）との切り替えもサポートします。

## 特徴

- 📅 **CSV形式のスケジュール管理** - シンプルなCSV形式でタイムテーブルを管理
- 🔄 **日替わり自動対応** - 放送業界標準の日替わり時刻（0-5時設定可能）に対応
- 🎙️ **スタジオモード対応** - JACK Audio接続を使用した生放送モードの自動切替
- 🔊 **JACK Audio統合** - プロフェッショナルなオーディオルーティング
- 📡 **翌日分自動読込** - 日跨ぎでシームレスに放送継続

## 動作環境

### 動作確認済み環境

**オペレーティングシステム:**
- **Linux Mint 22.2** (Cinnamon Edition)
- **Lubuntu 24.04.4 LTS** (LXQt)
- **Kubuntu 24.04 LTS** (Plasma 5)
- **Raspberry Pi OS** (64bit - Raspberry Pi 5)

**オーディオインターフェース:**
- **PreSonus AudioBox USB 96**
- **ARTURIA MiniFuse 2**
- **ESI U24XL**


### 必須要件

- **OS**: Linux (Ubuntu, Raspberry Pi OS等)
- **Python**: 3.7以上
- **必須パッケージ**:
  - `jackd2` - JACK Audio Connection Kit(PipeWire環境では`pipewire-jack`を使用)
  - `mpv` - メディアプレイヤー（JACK オーディオ出力対応）
  - `samba` - ネットワーク共有（オプション）

## クイックスタート

### インストール

詳細なインストール手順は [SETUP.md](SETUP.md) を参照してください。

```bash
# リポジトリをクローン
cd ~
git clone https://github.com/stcatcom/easyaps.git

# 実行権限を付与
chmod 755 ~/easyaps/easyaps.py

# データディレクトリを作成
mkdir -p ~/easyaps/data/{csv,contents}
```

### 起動方法

#### 方法1: 手動起動（推奨・全環境対応）

ターミナルを開いて以下のコマンドを実行します：

```bash
~/easyaps/easyaps.py
```

この方法は以下の利点があります：
- **環境非依存**: どのLinuxディストリビューションでも動作
- **デバッグが容易**: エラーメッセージが直接確認できる
- **起動タイミングの制御**: 必要なタイミングで起動可能

**システム起動時に自動起動したい場合**は、デスクトップ環境の「スタートアップアプリケーション」設定で、上記コマンドを登録するだけでOKです。

#### 方法2: 自動起動（.desktop使用）

自動起動の詳細な設定方法は [SETUP.md](SETUP.md) を参照してください。なお、すべての環境で自動起動できることを保証していません。書く環境において適切に設定してください。

### コマンドラインオプション

```bash
# デフォルト起動（日替わり時刻: 午前4時）
~/easyaps/easyaps.py

# 日替わり時刻を指定（午前3時）
~/easyaps/easyaps.py 3

# デバッグモード有効（mpv実行時間などを表示）
~/easyaps/easyaps.py --debug

# デバッグモード + 日替わり時刻指定
~/easyaps/easyaps.py --debug 3

# バージョン確認
~/easyaps/easyaps.py --version

# ヘルプ表示
~/easyaps/easyaps.py --help
```

## 使い方

### CSVファイル形式

`~/easyaps/data/csv/YYMMDD.csv` 形式でタイムテーブルを作成します。

**例: 260112.csv (2026年1月12日)**

```csv
time,source,mix,filename
05:00:00,BGM,M,MORNING01
06:00:00,ST,ST,ST
07:00:00,PRG,M,NEWS_HEADLINES
07:15:00,BGM,M,EASY_LISTENING
12:00:00,ST,ST,ST
13:00:00,PRG,F,AFTERNOON_SHOW
18:00:00,CM,F,CM_SPOT_001
```

**カラム説明**:
- `time`: 再生開始時刻（HH:MM:SS形式、24時以降も対応）
- `source`: ソース種別（参考情報、現在未使用）
- `mix`: ミキシング設定（参考情報、現在未使用）
- `filename`: ファイル名（拡張子不要）

**特殊なファイル名**:
- `ST`: スタジオモード（オーディオインターフェースの入力端子の音声をそのまま出力）
- `SLT` または空欄: 無音

### メディアファイルの配置

音源ファイルは `~/easyaps/data/contents/` 配下に配置します。
CMや番組の完パケをサブディレクトリに分けることも可能です。
ファイル名は半角英数推奨。スペースを含まないようにしてください。

```
~/easyaps/data/contents/
├── bgm/
│   ├── MORNING01.mp3
│   └── EASY_LISTENING.m4a
├── prg/
│   ├── NEWS_HEADLINES.mp3
│   └── AFTERNOON_SHOW.mp3
└── cm/
    └── CM_SPOT_001.mp3
```

**対応フォーマット**: `.mp3`, `.m4a`

### 動作確認

起動すると以下のような表示が出ます：

```
放送スケジューラー - 日替わり時刻: 午前4時 (version free-0.10)
==================================================
放送スケジューラーを開始します...
総レコード数: 129
放送日終了時刻: 04:00:00
現在の放送時刻: 15:18:06
放送日: 2026-01-12

現在演奏中: 15:00:00 - AFTERNOON_SHOW
開始時刻から 18:06 経過。該当位置から再生開始
再生開始: /home/user/easyaps/data/contents/prg/AFTERNOON_SHOW.mp3 (位置: 1086.9秒)

[AFTERNOON_SHOW] 15:36:44 00:38:45
```

画面下部にはリアルタイムで以下の情報が表示されます：
- `[ファイル名]` - 再生中のファイル（緑色表示）または `生放送中`（赤背景白文字）
- 現在時刻（HH:MM:SS形式）
- 次のイベントまでの残り時間（HH:MM:SS形式）

## トラブルシューティング

詳細なトラブルシューティングは [SETUP.md](SETUP.md) を参照してください。

### よくある問題

**ファイルが見つからない**
```
ファイルが見つかりません: /home/user/easyaps/data/contents/FILENAME.mp3/.m4a
```
- ファイル名がCSVと一致しているか確認
- ファイルが `~/easyaps/data/contents/` 配下に存在するか確認
- ファイルの拡張子が `.mp3` または `.m4a` か確認

**JACK接続エラー**
```bash
# JACKサービスの状態確認
systemctl --user status jackd

# サービスの再起動
systemctl --user restart jackd
```

## 更新履歴
 - 2026/01/12 初版公開
 - 2026/02/03 ver.0.03　軽微な修正を実施
 - 2026/03/12 ver.0.04　PipeWireに対応
 - 2026/03/20 ver.0.10　日替わり処理の不具合を修正、オーディオ再生をmpd → mpvに変更
 - 2026/03/22 ver.0.11　ドキュメント更新、mpv実装の最適化完了

## ライセンス

MIT License

Copyright (c) 2026 Masaya Miyazaki / Office Stray Cat

詳細は [LICENSE](LICENSE) ファイルを参照してください。

**注意**: このソフトウェアを改変・派生する際は、著作権表示を削除しないでください。

## 作者

- **Masaya Miyazaki** / Office Stray Cat
- Website: https://stcat.com/
- Email: info@stcat.com
- GitHub: [@stcatcom](https://github.com/stcatcom)

## 免責事項

本ソフトウェアは「現状のまま」提供されます。
作者は、本ソフトウェアの使用によって生じた一切の損害について責任を負いません。
放送業務での使用については、必ず十分なテストを行った上で運用してください。

## 貢献

バグ報告や機能要望は [GitHub Issues](https://github.com/stcatcom/EasyAPS/issues) までお願いします。
プルリクエストも歓迎します。

このプロジェクトが役に立った場合は、開発費の支援をご検討ください：

[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue.svg)](https://paypal.me/stcatcom?locale.x=ja_JP&country.x=JP)

## 謝辞

このプロジェクトは複数のコミュニティ放送局様の協力により開発されています。貢献に感謝します。
