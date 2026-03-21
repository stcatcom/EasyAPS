# EasyAPS セットアップガイド（JACK環境向け）

EasyAPSはJACK APIを使用するため、PipeWire環境でも**pipewire-jack互換層**を通じて動作します。
device.confでport名を設定することで、JACK/PipeWire双方に対応します。

このドキュメントでは、JACKで動作する環境における、EasyAPSの詳細なセットアップ手順を説明します。

## 目次

- [前提条件の確認](#前提条件の確認)
- [リポジトリのクローン](#リポジトリのクローン)
- [JACK Audioのインストール](#jack-audioのインストール)
- [mpv（メディアプレイヤー）のインストール](#mpvメディアプレイヤーのインストール)
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

## JACK Audioのインストール

### 1. JACK Audio Connection Kitのインストール
```bash
sudo apt install jackd2 -y
```

**注意**: インストール時に「リアルタイム実行優先度の設定を有効にしますか?」と聞かれたら「はい」を選択してください。

### 2. リアルタイムスケジューリング権限の設定
```bash
# 既存の設定をバックアップ
sudo cp /etc/security/limits.conf /etc/security/limits.conf.bak

# JACKにリアルタイムスケジューリングの権限を付与
grep -q "@audio.*rtprio" /etc/security/limits.conf || echo "@audio - rtprio 95" | sudo tee -a /etc/security/limits.conf
grep -q "@audio.*memlock" /etc/security/limits.conf || echo "@audio - memlock unlimited" | sudo tee -a /etc/security/limits.conf

# 設定を確認
cat /etc/security/limits.conf
```

### 3. ユーザーをオーディオグループに追加
```bash
# audio, render, videoグループにユーザーを追加
sudo usermod -a -G render,video,audio $USER

# PAM設定を更新
grep -q "session required pam_limits.so" /etc/pam.d/common-session || echo 'session required pam_limits.so' | sudo tee -a /etc/pam.d/common-session

# 設定を確認
cat /etc/pam.d/common-session
```

**重要**: ここまでの設定後、設定を有効にするために再起動してください。

### 4. オーディオデバイスの確認
```bash
# 再生デバイスの確認
aplay -l

# 録音デバイスの確認
arecord -l
```

出力結果から使用するオーディオインターフェースのデバイス名を確認します。

**例**:
```
card 2: A96 [AudioBox USB 96], device 0: USB Audio [USB Audio]
```

この場合、デバイス名は `hw:A96` または `hw:2` となります。

### 5. JACK Audioの自動起動設定
```bash
# loginctlでユーザーセッションの永続化を有効化
loginctl enable-linger $USER
loginctl show-user $USER | grep Linger

# systemdユーザーサービスディレクトリを作成
mkdir -p /home/$USER/.config/systemd/user

# JACKサービスファイルを作成(hw:A96は実際のデバイス名に変更)
cat << EOF > /home/$USER/.config/systemd/user/jackd.service
[Unit]
Description=Start JACK Server
After=sound.target

[Service]
Type=simple
ExecStart=/usr/bin/jackd -d alsa -d hw:A96 -r 48000 -p 1024 -n 2 -H
Restart=always
RestartSec=5
LimitRTPRIO=95
LimitMEMLOCK=infinity
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jackd

[Install]
WantedBy=default.target
EOF

# サービスの有効化と起動
systemctl --user enable --now jackd

# サービスの状態確認
systemctl --user status jackd
```

### 6. JACK接続の確認
```bash
# JACKポートの一覧表示
jack_lsp

# JACK接続状態の確認
jack_lsp -c
```

`system:capture_1`, `system:capture_2`, `system:playback_1`, `system:playback_2` などのポートが表示されればOKです。

## mpv（メディアプレイヤー）のインストール

### 1. mpvのインストール
```bash
sudo apt install -y mpv
```

### 2. JACK オーディオ出力の確認
mpvはインストール後、自動的にJACKオーディオ出力に対応しています。
確認するには以下のコマンドを実行：

```bash
# mpvのバージョンと対応フォーマットを確認
mpv --version

# JACKが利用可能か確認（出力に "jack" が含まれていることを確認）
mpv --ao=help | grep jack
```

`[ao jack]` と表示されればJACK出力が利用可能です。

### 3. データディレクトリの準備
```bash
# EasyAPS用データディレクトリを作成
mkdir -p ~/easyaps/data/{csv,contents}
```

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

## 自動起動の設定

システム起動時にEasyAPSを自動起動する設定です。

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

### Raspberry Piの場合
```bash
mkdir -p ~/.config/autostart

cat << EOF > ~/.config/autostart/easyaps.desktop
[Desktop Entry]
Type=Application
Name=EasyAPS
Exec=lxterminal --title=EasyAPS -e "python3 $HOME/easyaps/easyaps.py"
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

### JACK接続エラー

#### JACKサービスが起動しない
```bash
# JACKサービスの状態確認
systemctl --user status jackd

# ログの確認
journalctl --user -u jackd -n 50

# JACKサービスの再起動
systemctl --user restart jackd
```

**よくある原因**:
- オーディオデバイスが接続されていない
- デバイス名(`hw:A96`など)が間違っている
- 他のアプリケーションがオーディオデバイスを使用している

#### JACK接続が確立されない
```bash
# JACK接続の確認
jack_lsp -c

# 手動でJACK接続を確立
jack_connect system:capture_1 system:playback_1
jack_connect system:capture_2 system:playback_2
```

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

#### JACK接続の確認
```bash
# JACK接続状態を確認
jack_lsp -c

# mpvが接続されているか確認（以下のような出力が表示されるはずです）
# mpv:out_0
#    system:playback_1
# mpv:out_1
#    system:playback_2
```

mpvが接続されていない場合は、JACKサービスが正常に動作していることを確認してください。

#### オーディオデバイスの確認
```bash
# オーディオデバイスが認識されているか確認
aplay -l
arecord -l

# JACKが正しいデバイスを使用しているか確認
systemctl --user status jackd

# JACKサービスが起動していない場合は起動
systemctl --user start jackd
```

#### device.conf の設定確認
```bash
# device.confが正しく設定されているか確認
cat ~/easyaps/device.conf

# 出力例：
# [AUDIO_ROUTING]
# capture_l  = system:capture_1
# capture_r  = system:capture_2
# playback_l = system:playback_1
# playback_r = system:playback_2
```

### システム再起動後にJACKが起動しない
```bash
# loginctlの設定確認
loginctl show-user $USER | grep Linger

# Linger=yesと表示されない場合は再設定
loginctl enable-linger $USER

# サービスの状態確認
systemctl --user status jackd

# JACKサービスが起動していない場合は起動
systemctl --user start jackd
```

### パーミッションエラー
```bash
# オーディオグループに所属しているか確認
groups $USER

# audio, render, videoグループが表示されない場合は再追加
sudo usermod -a -G render,video,audio $USER

# ログアウト・再ログインして反映
```

### その他の問題

問題が解決しない場合は、以下の情報を添えてIssueを作成してください:

1. 使用しているOSとバージョン
2. オーディオインターフェースのモデル
3. エラーメッセージ全文
4. 以下のコマンドの出力結果:
```bash
   systemctl --user status jackd
   jack_lsp -c
   ~/easyaps/easyaps.py --version
```

## 参考リンク

- [JACK Audio Connection Kit](https://jackaudio.org/)
- [mpv - a free, open source, and cross-platform media player](https://mpv.io/)
- [Samba](https://www.samba.org/)
