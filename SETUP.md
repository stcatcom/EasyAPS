# EasyAPS セットアップガイド

このドキュメントでは、EasyAPSの詳細なセットアップ手順を説明します。

## 目次

- [前提条件の確認](#前提条件の確認)
- [JACK Audioのインストール](#jack-audioのインストール)
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

表示されるテキストの最後に
@audio - rtprio 95
@audio - memlock unlimited
の表示があることを確認して下さい。

```

### 3. ユーザーをオーディオグループに追加

```bash
# audio, render, videoグループにユーザーを追加
sudo usermod -a -G render,video,audio $USER

# PAM設定を更新
grep -q "session required pam_limits.so" /etc/pam.d/common-session || echo 'session required pam_limits.so' | sudo tee -a /etc/pam.d/common-session

# 設定を確認
cat /etc/pam.d/common-session

表示されるテキストの最後に
session required pam_limits.so
の表示があることを確認して下さい。
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

# JACKサービスファイルを作成（hw:A96は実際のデバイス名に変更）
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

## Audaciousのインストール

### 1. Audaciousのインストール

```bash
sudo apt install -y audacious
```

### 2. Audaciousの自動起動設定

```bash
# Audaciousサービスファイルを作成
cat << EOF > /home/$USER/.config/systemd/user/audacious.service
[Unit]
Description=Start Audacious headless
After=jackd.service

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

### 3. Audaciousの設定（GUI）

起動に成功すると、GUI側にAudaciousが起動します。

1. Audaciousを起動
2. メニューから `ファイル` → `設定` を開く
3. `オーディオ` タブを選択
4. 以下を設定:
   - **出力プラグイン**: `JACK Output Plugin`
   - **サンプルレート**: `48000 Hz`
5. 設定を保存して閉じる

## Samba共有の設定（オプション）

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

プロンプトに従ってパスワードを設定します（シェルログインパスワードとは別のものを推奨）。

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

LAN内の別のPCから、このPCの共有フォルダ（`\\[IPアドレス]\easyaps`）にアクセスできることを確認してください。
特に、ファイルの追加・削除ができるかを確認しておくことを推奨します。

## EasyAPS本体のインストール

### 1. リポジトリのクローン

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

### 2. 実行権限の付与

```bash
chmod 755 ~/easyaps/easyaps.py
```

### 3. 起動確認

```bash
# ヘルプ表示
~/easyaps/easyaps.py --help

# バージョン確認
~/easyaps/easyaps.py --version
```

## 自動起動の設定

システム起動時にEasyAPSを自動起動する設定です。

### 通常のLinux（Linux Mint, GNOME等）の場合

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
4. **大文字小文字**: Linuxはファイル名の大文字小文字を区別します（例: `MORNING01.mp3` と `morning01.mp3` は別ファイル）
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
- デバイス名（`hw:A96`など）が間違っている
- 他のアプリケーションがオーディオデバイスを使用している

#### JACK接続が確立されない

```bash
# JACK接続の確認
jack_lsp -c

# 手動でJACK接続を確立
jack_connect system:capture_1 system:playback_1
jack_connect system:capture_2 system:playback_2
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
- `DISPLAY` 環境変数が間違っている（デフォルトは `:0`）
- JACKサービスが起動していない
- X11/Waylandセッションの問題

### CSVファイルが読み込まれない

**確認事項**:
1. **ファイル名**: `YYMMDD.csv` 形式になっているか（例: `260112.csv`）
2. **配置場所**: `~/easyaps/data/csv/` ディレクトリに配置されているか
3. **エンコーディング**: ファイルのエンコーディングが `UTF-8` であることを確認
4. **CSV形式**: カンマ区切りで、カラムが4つ（time, source, mix, filename）あることを確認
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

# 以下のような接続が表示されるはずです
# system:capture_1
#    system:playback_1
# system:capture_2
#    system:playback_2
```

#### Audaciousの出力設定確認

1. Audaciousを起動
2. `ファイル` → `設定` → `オーディオ` を開く
3. 出力プラグインが `JACK Output Plugin` になっているか確認

#### オーディオデバイスの確認

```bash
# オーディオデバイスが認識されているか確認
aplay -l
arecord -l

# JACKが正しいデバイスを使用しているか確認
systemctl --user status jackd
```

### システム再起動後にJACKが起動しない

```bash
# loginctlの設定確認
loginctl show-user $USER | grep Linger

# Linger=yesと表示されない場合は再設定
loginctl enable-linger $USER

# サービスの状態確認
systemctl --user status jackd
systemctl --user status audacious
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

問題が解決しない場合は、以下の情報を添えてIssueを作成してください：

1. 使用しているOSとバージョン
2. オーディオインターフェースのモデル
3. エラーメッセージ全文
4. 以下のコマンドの出力結果:
   ```bash
   systemctl --user status jackd
   systemctl --user status audacious
   jack_lsp -c
   ~/easyaps/easyaps.py --version
   ```

## 参考リンク

- [JACK Audio Connection Kit](https://jackaudio.org/)
- [Audacious](https://audacious-media-player.org/)
- [Samba](https://www.samba.org/)
