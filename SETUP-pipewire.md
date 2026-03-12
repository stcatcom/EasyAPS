# EasyAPS セットアップガイド（PipeWire環境向け）

EasyAPSはJACK APIを使用するため、PipeWire環境でも**pipewire-jack互換層**を通じて動作します。
device.confでport名を設定することで、JACK/PipeWire双方に対応します。

このドキュメントでは、PipwWireで動作する環境における、EasyAPSの詳細なセットアップ手順を説明します。

## 目次

- [前提条件の確認](#前提条件の確認)
- [リポジトリのクローン](#リポジトリのクローン)
- [PipeWire関連ツールのインストール](#pipewire関連ツールのインストール)
- [Audaciousのインストール](#audaciousのインストール)
- [Samba共有の設定](#samba共有の設定オプション)
- [EasyAPS本体のインストール](#easyaps本体のインストール)
- [自動起動の設定](#自動起動の設定)
- [トラブルシューティング](#トラブルシューティング)

## 前提条件の確認

### ユーザー確認

rootユーザーではなく、一般ユーザーで作業を行います。
```bash
# 現在のユーザーを確認
USER=$(whoami)
echo $USER

# システムの更新
sudo apt update && sudo apt upgrade -y
```

## リポジトリのクローン
```bash
cd ~
git clone https://github.com/stcatcom/easyaps.git
```

または、直接ダウンロード：
```bash
cd ~
mkdir -p easyaps
cd easyaps
wget https://raw.githubusercontent.com/stcatcom/easyaps/main/easyaps.py
```

## PipeWire関連ツールのインストール

### 1. PipeWire-JACKのインストール
```bash
sudo apt install pipewire-jack jack-tools
```

**注意**: インストール時に「リアルタイム実行優先度の設定を有効にしますか?」と聞かれたら「はい」を選択してください。

### 2. PipeWire-JACKのライブラリ設定

アプリケーション（Audaciousなど）がPipeWireのJACK互換ライブラリを使用するよう設定します。
```bash
# PipeWire-JACKのライブラリパスをシステムに登録
sudo cp /usr/share/doc/pipewire/examples/ld.so.conf.d/pipewire-jack-*.conf /etc/ld.so.conf.d/

# 設定を反映
sudo ldconfig
```

### 3. オーディオデバイスの確認と設定
```bash
# 再生デバイスの確認
aplay -l

# 録音デバイスの確認
arecord -l

# JACK互換ポートの確認
jack_lsp
```

デバイスおよびポートが表示されることを確認します。

PipeWire-JACK環境では、`jack_lsp` の出力はデバイス名を含む形式になります。

**出力例**:
```
Built-in Audio アナログステレオ:capture_FL
Built-in Audio アナログステレオ:capture_FR
AudioBox Go アナログステレオ:capture_FL
AudioBox Go アナログステレオ:capture_FR
AudioBox Go アナログステレオ:playback_FL
AudioBox Go アナログステレオ:playback_FR
...
```

使用するオーディオインターフェースのポート名を確認し、`easyaps.py` と同じディレクトリにある `device.conf` に設定します。

**device.conf の設定例**（AudioBox Go を使用する場合）:
```ini
[AUDIO_ROUTING]
capture_l  = AudioBox Go アナログステレオ:capture_FL
capture_r  = AudioBox Go アナログステレオ:capture_FR
playback_l = AudioBox Go アナログステレオ:playback_FL
playback_r = AudioBox Go アナログステレオ:playback_FR
```

## Audaciousのインストール

### 1. Audaciousのインストール
```bash
sudo apt install -y audacious
```

### 2. Audaciousの自動起動設定
```bash
# loginctlでユーザーセッションの永続化を有効化
loginctl enable-linger $USER
loginctl show-user $USER | grep Linger

# systemdユーザーサービスディレクトリを作成
mkdir -p /home/$USER/.config/systemd/user

# Audaciousサービスファイルを作成
cat << EOF > /home/$USER/.config/systemd/user/audacious.service
[Unit]
Description=Start Audacious headless
After=pipewire.service

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStart=/usr/bin/audacious
Restart=on-failure
RestartSec=5
LimitRTPRIO=95
LimitMEMLOCK=infinity
StandardOutput=journal
StandardError=journal
SyslogIdentifier=audacious

[Install]
WantedBy=default.target
EOF

# サービスの有効化と起動
systemctl --user enable --now audacious

# サービスの状態確認
systemctl --user status audacious
```

**注意**: `Environment=DISPLAY=:0` は環境によって変更が必要な場合があります。

### 3. Audaciousの設定(GUI)

起動に成功すると、GUI側にAudaciousが起動します。

1. Audaciousを起動
2. メニューから `ファイル` → `設定` を開く
3. `オーディオ` タブを選択
4. 以下を設定:
   - **バッファーサイズ**: `100 ms`
5. 設定を保存して閉じる

## Samba共有の設定(オプション)

ネットワーク経由でCSVやメディアファイルを管理できるようにします。

### 1. データディレクトリの作成
```bash
mkdir -p ~/easyaps/data/{csv,contents}
```

### 2. Sambaのインストール
```bash
sudo apt install samba -y
```

### 3. Samba設定ファイルの作成
```bash
# 既存の設定をバックアップ
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.bak

# Samba設定ファイルを作成
sudo tee /etc/samba/smb.conf > /dev/null <<'EOF'
[global]
   workgroup = WORKGROUP
   security = user
   map to guest = bad user
   usershare allow guests = no

[easyaps]
   path = /home/%U/easyaps/data
   browseable = yes
   writable = yes
   valid users = %U
   create mask = 0660
   directory mask = 0770
EOF
```

### 4. Sambaユーザーの追加
```bash
# Sambaユーザーを追加
sudo smbpasswd -a $USER
```

プロンプトに従ってパスワードを設定します(シェルログインパスワードとは別のものを推奨)。
```
New SMB password: [パスワードを入力]
Retype new SMB password: [パスワードを再入力]
Added user [ユーザー名].
```

### 5. Sambaサービスの有効化
```bash
# Sambaサービスの有効化と起動
sudo systemctl enable --now smbd

# サービスの状態確認
sudo systemctl status smbd
```

### 6. 接続確認

LAN内の別のPCから、このPCの共有フォルダ(`\\[IPアドレス]\easyaps`)にアクセスできることを確認してください。
特に、ファイルの追加・削除ができるかを確認しておくことを推奨します。

## EasyAPS本体のインストール

### 1. 実行権限の付与
```bash
chmod 755 ~/easyaps/easyaps.py
```

### 2. 起動確認
```bash
# ヘルプ表示
~/easyaps/easyaps.py --help

# バージョン確認
~/easyaps/easyaps.py --version
```

## 自動起動の設定例

システム起動時にEasyAPSを自動起動する設定の例です。
ここでは一部のシステムでの設定を例示しており、お使いのシステムによって設定方法や起動方法は変わります。

### 通常のLinux(Linux Mint, GNOME等)の場合
```bash
mkdir -p ~/.config/autostart

cat << EOF > ~/.config/autostart/easyaps.desktop
[Desktop Entry]
Type=Application
Name=EasyAPS
Exec=gnome-terminal --title=EasyAPS -- bash -lc "$HOME/easyaps/easyaps.py"
Terminal=false
EOF
```

### Kubuntuの場合
```bash
mkdir -p ~/.config/autostart

cat << EOF > ~/.config/autostart/easyaps.desktop
[Desktop Entry]
Type=Application
Name=EasyAPS
Comment=EasyAPS Automatic Broadcast Scheduler
Exec=konsole --hold -e python3 easyaps/easyaps.py
Icon=utilities-terminal
Terminal=false
Categories=AudioVideo;Audio;
EOF

chmod 755 ~/.config/autostart/easyaps.desktop
```

### 自動起動の確認

再起動して、EasyAPSが自動的に起動することを確認してください。
```bash
sudo reboot
```

## トラブルシューティング

### ファイルが見つからない
```
ファイルが見つかりません: /home/user/easyaps/data/contents/FILENAME.mp3/.m4a
ダミーファイルで代替: /home/user/easyaps/data/contents/dummy.m4a
```

**原因と対処法**:
1. **ファイル名の不一致**: CSVファイルに記載されたファイル名と実際のファイル名が一致しているか確認
2. **ファイルの不在**: `~/easyaps/data/contents/` 配下にファイルが存在するか確認
3. **拡張子の問題**: ファイルの拡張子が `.mp3` または `.m4a` であることを確認
4. **大文字小文字**: Linuxはファイル名の大文字小文字を区別します(例: `MORNING01.mp3` と `morning01.mp3` は別ファイル)
5. **シンボリックリンク**: Samba共有を使用している場合、シンボリックリンクが正しく設定されているか確認

**注意**: `dummy.m4a` が存在しない場合、自動的に無音で継続されます。

### PipeWire接続エラー

#### PipeWireサービスが起動しない
```bash
# PipeWireサービスの状態確認
systemctl --user status pipewire
systemctl --user status wireplumber

# ログの確認
journalctl --user -u pipewire -n 50

# PipeWireサービスの再起動
systemctl --user restart pipewire wireplumber
```

**よくある原因**:
- オーディオデバイスが接続されていない
- 他のアプリケーションがオーディオデバイスを排他的に使用している
- PipeWire-JACKのライブラリ設定(`ldconfig`)が反映されていない

#### JACK互換ポートの接続が確立されない
```bash
# ポート一覧と接続状態の確認
jack_lsp
jack_lsp -c

# 手動でポート接続を確立（ポート名は jack_lsp の出力に合わせる）
jack_connect "AudioBox Go アナログステレオ:capture_FL" "AudioBox Go アナログステレオ:playback_FL"
jack_connect "AudioBox Go アナログステレオ:capture_FR" "AudioBox Go アナログステレオ:playback_FR"
```

ポート名はオーディオデバイスによって異なります。`jack_lsp` の出力を確認して正確な名称を使用してください。

#### PipeWire-JACKライブラリが認識されない
```bash
# ライブラリ設定の再反映
sudo ldconfig

# 設定ファイルの確認
ls /etc/ld.so.conf.d/ | grep pipewire
```

### Audaciousが起動しない
```bash
# Audaciousサービスの状態確認
systemctl --user status audacious

# ログの確認
journalctl --user -u audacious -n 50

# 手動起動テスト
DISPLAY=:0 audacious

# サービスの再起動
systemctl --user restart audacious
```

**よくある原因**:
- `DISPLAY` 環境変数が間違っている(デフォルトは `:0`)
- PipeWireサービスが起動していない
- X11/Waylandセッションの問題

### CSVファイルが読み込まれない

**確認事項**:
1. **ファイル名**: `YYMMDD.csv` 形式になっているか(例: `260112.csv`)
2. **配置場所**: `~/easyaps/data/csv/` ディレクトリに配置されているか
3. **エンコーディング**: ファイルのエンコーディングが `UTF-8` であることを確認
4. **CSV形式**: カンマ区切りで、カラムが4つ(time, source, mix, filename)あることを確認
5. **ヘッダー行**: 1行目がヘッダーの場合、`time,source,mix,filename` になっているか確認

**CSVファイルの例**:
```csv
time,source,mix,filename
05:00:00,BGM,M,MORNING01
06:00:00,ST,ST,ST
```

### 音が出ない

#### PipeWire・ポート接続の確認
```bash
# PipeWireサービスの状態確認
systemctl --user status pipewire

# ポート接続状態を確認
jack_lsp -c

# device.conf で設定したポートが接続されているはずです（例）
# AudioBox Go アナログステレオ:capture_FL
#    AudioBox Go アナログステレオ:playback_FL
# AudioBox Go アナログステレオ:capture_FR
#    AudioBox Go アナログステレオ:playback_FR
```

#### Audaciousの出力設定確認

1. Audaciousを起動
2. `ファイル` → `設定` → `オーディオ` を開く
3. 出力プラグインが `PipeWire` になっているか確認

#### オーディオデバイスの確認
```bash
# オーディオデバイスが認識されているか確認
aplay -l
arecord -l

# PipeWireが正しいデバイスを使用しているか確認
systemctl --user status pipewire
```

### システム再起動後にPipeWireが起動しない
```bash
# loginctlの設定確認
loginctl show-user $USER | grep Linger

# Linger=yesと表示されない場合は再設定
loginctl enable-linger $USER

# サービスの状態確認
systemctl --user status pipewire
systemctl --user status audacious
```

### その他の問題

問題が解決しない場合は、以下の情報を添えてIssueを作成してください:

1. 使用しているOSとバージョン
2. オーディオインターフェースのモデル
3. エラーメッセージ全文
4. 以下のコマンドの出力結果:
```bash
   systemctl --user status pipewire
   systemctl --user status audacious
   jack_lsp -c
   ~/easyaps/easyaps.py --version
```

## 参考リンク

- [PipeWire](https://pipewire.org/)
- [Audacious](https://audacious-media-player.org/)
- [Samba](https://www.samba.org/)
