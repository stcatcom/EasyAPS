#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyAPS - 放送局向け自動放送スケジューラー

Copyright (c) 2026 Masaya Miyazaki / Office Stray Cat
All rights reserved.

Licensed under the MIT License
See LICENSE file for more details.

NOTICE: This copyright notice must be retained in all copies or 
substantial portions of the software, including derivative works.

Author: Masaya Miyazaki
Organization: Office Stray Cat
Website: https://stcat.com/
Email: info@stcat.com
GitHub: https://github.com/stcatcom/RadioArchiver
Version: 0.0.3
"""
import csv
import os
import subprocess
import time
import threading
from datetime import datetime, timedelta

# バージョン情報
version = "free-0.03"

class MusicScheduler:
    def __init__(self, day_end_hour=4):
        """
        day_end_hour: 放送日の終了時刻（1-5時で指定、デフォルト4時）
        例：4時設定の場合、3:59:59までが当日、4:00:00が翌日開始
        """
        home_dir = os.path.expanduser("~")
        self.base_dir = os.path.join(home_dir, "easyaps")
        self.csv_dir = os.path.join(self.base_dir, "data/csv")
        self.contents_dir = os.path.join(self.base_dir, "data/contents")
        self.dummy_file = os.path.join(self.contents_dir, "dummy.m4a")
        self.current_record = None
        self.next_record = None
        self.current_start_time = None  # 現在の音源の実際の開始時刻
        self.display_running = False
        self.display_thread = None
        
        # 放送日の終了時刻（0-5時に変更）
        if not (0 <= day_end_hour <= 5):
            raise ValueError("day_end_hour は 0-5 の範囲で指定してください")
        self.day_end_hour = day_end_hour
        
        # 日替わり処理用
        self.all_records = []  # 全レコード（現在日+翌日）
        self.current_record_index = 0  # 現在処理中のレコードインデックス
        self.next_day_loaded = False  # 翌日分が読み込み済みかどうか
        self.next_day_loading = False  # 翌日分読み込み中フラグ
        self.preload_threshold = 10  # 残りレコード数がこの値以下になったら翌日分を読み込み
        self.next_day_check_started = False  # 翌日分チェック開始フラグ
        
        # JACK制御の状態管理を追加
        self.previous_studio_mode = None
        self.jack_connection_active = False
        
    def format_time_display(self, seconds):
        """秒数を MM:SS 形式にフォーマット"""
        if seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def format_broadcast_time(self, dt):
        """放送業界形式の時刻表示（24時以降対応）"""
        hour = dt.hour
        minute = dt.minute
        second = dt.second
        
        # 日替わり時刻より前の時間は前日の24時以降として表示
        if hour < self.day_end_hour:
            hour += 24
        
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    def get_broadcast_date(self, target_time=None):
        """放送日付を取得（日替わり時刻を考慮）"""
        if target_time is None:
            target_time = datetime.now()
        
        # 日替わり時刻より前なら前日の放送日
        if target_time.hour < self.day_end_hour:
            broadcast_date = target_time.date() - timedelta(days=1)
        else:
            broadcast_date = target_time.date()
        
        return broadcast_date
    
    def get_audacious_playback_position(self):
        """audaciousの現在の再生位置を取得（秒）"""
        try:
            result = subprocess.run(["audtool", "current-song-output-length-seconds"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
            pass
        return None
    
    def check_jack_connections(self):
        """修正版：JACKの接続状態をチェック"""
        try:
            result = subprocess.run(["jack_lsp", "-c"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=3)
            if result.returncode == 0:
                output = result.stdout
                lines = output.split('\n')
                
                capture1_to_playback1 = False
                capture2_to_playback2 = False
                
                current_port = None
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 出力ポートの行（インデントなし）
                    if not line.startswith(' ') and not line.startswith('\t'):
                        current_port = line
                    else:
                        # 接続先の行（インデント有り）
                        connected_to = line
                        if current_port == "system:capture_1" and connected_to == "system:playback_1":
                            capture1_to_playback1 = True
                        elif current_port == "system:capture_2" and connected_to == "system:playback_2":
                            capture2_to_playback2 = True
                
                is_connected = capture1_to_playback1 and capture2_to_playback2
                return is_connected
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            pass
        return False
    
    def connect_jack_studio(self):
        """JACKでスタジオ接続を確立（シンプル版）"""
        try:
            print("\nスタジオモード: JACK接続を確立中...")
            
            # 接続1: system:capture_1 -> system:playback_1
            subprocess.run(["jack_connect", "system:capture_1", "system:playback_1"], 
                         capture_output=True, text=True, timeout=5)
            
            # 接続2: system:capture_2 -> system:playback_2
            subprocess.run(["jack_connect", "system:capture_2", "system:playback_2"], 
                         capture_output=True, text=True, timeout=5)
            
            print("JACK接続確立完了")
            self.jack_connection_active = True
            return True
                
        except Exception as e:
            print(f"JACK接続エラー: {e}")
            return False
    
    def disconnect_jack_studio(self):
        """JACKのスタジオ接続を切断（無条件実行版）"""
        try:
            print("\nJACK接続を切断中...")
            
            # 切断1: system:capture_1 -> system:playback_1
            subprocess.run(["jack_disconnect", "system:capture_1", "system:playback_1"], 
                         capture_output=True, text=True, timeout=5)
            
            # 切断2: system:capture_2 -> system:playback_2
            subprocess.run(["jack_disconnect", "system:capture_2", "system:playback_2"], 
                         capture_output=True, text=True, timeout=5)
            
            print("JACK接続切断完了")
            self.jack_connection_active = False
            return True
                
        except Exception as e:
            print(f"JACK切断エラー: {e}")
            return False
    
    def is_studio_mode(self, record):
        """レコードがスタジオモードかどうかチェック"""
        if not record:
            return False
        filename = record.get('filename', '').strip().upper()
        source = record.get('source', '').strip().upper()
        is_st = filename == 'ST' or source == 'ST'
        return is_st
    
    def handle_jack_mode_change(self, current_record):
        """JACK接続モードの変更を処理（シンプル版）"""
        current_studio_mode = self.is_studio_mode(current_record)
        filename = current_record.get('filename', '') if current_record else 'None'
        
        # STモードの場合
        if current_studio_mode:
            # 実際のJACK接続状態をチェックして必要なら接続
            actual_connected = self.check_jack_connections()
            if not actual_connected:
                self.connect_jack_studio()
        
        # 非STモードの場合は無条件でJACK切断を実行
        else:
            #print(f"\n非STモード: 無条件でJACK切断を実行 - {filename}")
            self.disconnect_jack_studio()
        
        # 前回の状態を更新
        self.previous_studio_mode = current_studio_mode
    
    def get_audacious_status(self):
        """audaciousの再生状況を取得"""
        try:
            result = subprocess.run(["audtool", "playback-status"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=2)
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def display_status(self):
        """時間情報を連続表示するスレッド"""
        while self.display_running:
            try:
                current_time = datetime.now()
                status_line = ""
                
                # 現在演奏中の位置表示
                if self.current_record and self.current_start_time:
                    # STモードの場合は演奏位置を表示しない
                    if self.is_studio_mode(self.current_record):
                        # STモードの場合は「スタジオモード中」と表示
                        #status_line += "🎙 スタジオモード中"
                        status_line += "\033[41m\033[97m🎙 スタジオモード中\033[0m"
                    else:
                        # 通常モードの場合のみ演奏位置を表示
                        # audaciousの再生状態と位置を取得
                        audacious_status = self.get_audacious_status()
                        audacious_position = self.get_audacious_playback_position()
                        
                        # 状態インジケーター
                        status_indicator = "♪" if audacious_status == "playing" else "⏸" if audacious_status == "paused" else "○"
                        
                        # 演奏位置の計算
                        if audacious_position is not None and audacious_status == "playing":
                            # audtoolから取得した実際の再生位置を使用
                            scheduled_start = self.current_record['time']
                            
                            # 元の開始予定時刻からのオフセットを計算
                            start_offset = (self.current_start_time - scheduled_start).total_seconds()
                            if start_offset > 0:
                                # 遅延開始の場合は、その分を加算
                                total_position = audacious_position + start_offset
                            else:
                                total_position = audacious_position
                            
                            status_line += f"{status_indicator} 演奏位置: {self.format_time_display(total_position)}"
                        else:
                            # audtoolが使えない場合の処理
                            if not (self.current_record['filename'].upper() == 'SLT' or self.current_record['filename'].strip() == ''):
                                # SLTや空欄でない場合のみ推定位置を表示
                                scheduled_start = self.current_record['time']
                                total_elapsed = (current_time - scheduled_start).total_seconds()
                                status_line += f"? 推定位置: {self.format_time_display(total_elapsed)}"
                
                # 次の再生までの時間表示
                if self.next_record:
                    next_start = self.next_record['time']
                    wait_seconds = (next_start - current_time).total_seconds()
                    
                    if wait_seconds > 0:
                        if status_line:
                            status_line += " | "
                        status_line += f"次の再生まで: {self.format_time_display(wait_seconds)}"
                
                # 同一行に上書き表示
                if status_line:
                    print(f"\r{status_line}                    ", end="", flush=True)
                
                time.sleep(1)  # 1秒ごとに更新
                
            except Exception as e:
                # エラーが発生してもスレッドを継続
                time.sleep(1)
    
    def start_display_thread(self):
        """時間表示スレッドを開始"""
        if not self.display_running:
            self.display_running = True
            self.display_thread = threading.Thread(target=self.display_status, daemon=True)
            self.display_thread.start()
    
    def stop_display_thread(self):
        """時間表示スレッドを停止"""
        self.display_running = False
        if self.display_thread:
            self.display_thread.join(timeout=2)
        print()  # 改行
    
    def get_csv_path_by_date(self, target_date):
        """指定された日付のCSVファイルパスを取得"""
        csv_filename = f"{target_date.strftime('%y%m%d')}.csv"
        return os.path.join(self.csv_dir, csv_filename)
    
    def get_today_csv_path(self):
        """放送日の日付からCSVファイルパスを取得"""
        broadcast_date = self.get_broadcast_date()
        return self.get_csv_path_by_date(broadcast_date)
    
    def get_next_day_csv_path(self):
        """翌日のCSVファイルパスを取得"""
        broadcast_date = self.get_broadcast_date()
        next_day = broadcast_date + timedelta(days=1)
        return self.get_csv_path_by_date(next_day)
    
    def find_media_file(self, filename):
        """findコマンドを使ってメディアファイルのフルパスを取得（統一版・Linux/Windows対応）"""
        # SLTまたは空欄の場合は特別処理
        if filename.upper() == 'SLT' or filename.strip() == '':
            return 'SILENCE'  # 無音を示す特別な値を返す
        
        # STの場合は特別処理
        if filename.upper() == 'ST':
            return 'STUDIO'  # スタジオモードを示す特別な値を返す
        
        try:
            # -inameで大文字小文字無視の一括検索（Linux/Windows対応）
            result = subprocess.run(
                ["find", "-L", self.contents_dir, "-iname", f"{filename}.*", "-type", "f"],
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout.strip():
                # 対応拡張子のファイルを探す
                for line in result.stdout.strip().split('\n'):
                    if line.lower().endswith(('.mp3', '.m4a')):
                        #print(f"\nファイルが見つかりました: {line}")
                        return line
                        
        except subprocess.CalledProcessError as e:
            print(f"\nfindコマンドエラー ({filename}): {e}")
        
        # どの拡張子でも見つからない場合はダミーファイルのパスを返す
        #print(f"\nファイルが見つかりません: {filename} (拡張子: mp3, m4a)")
        print(f"\nファイルが見つかりません: {os.path.join(self.contents_dir, filename)}.mp3/.m4a")
        print(f"ダミーファイルで代替: {self.dummy_file}")
        return self.dummy_file
    
    def play_audio_file(self, filepath, start_position=None):
        """audaciousでオーディオファイルを再生（SLT・空欄・ST対応）"""
        # SLTまたは空欄の場合は無音処理
        if (filepath == 'SILENCE' or 
            os.path.basename(filepath).upper().startswith('SLT') or 
            os.path.basename(filepath).strip() == '' or 
            filepath.strip() == ''):
            if start_position is not None:
                print(f"\n無音開始: (位置: {start_position:.1f}秒から)")
            else:
                print(f"\n無音開始:")
            return
        
        # STの場合はスタジオモード処理
        if (filepath == 'STUDIO' or 
            os.path.basename(filepath).upper() == 'ST'):
            if start_position is not None:
                print(f"\nスタジオモード開始: (位置: {start_position:.1f}秒から)")
            else:
                print(f"\nスタジオモード開始:")
            return
        
        # ダミーファイルの場合で、ファイルが存在しない場合は無音処理
        if filepath == self.dummy_file and not os.path.exists(filepath):
            print(f"\nダミーファイルが見つかりません: {filepath}")
            print("無音で継続します")
            return
        
        try:
            if start_position is not None:
                # 指定された位置から再生開始
                # audaciousでは直接位置指定ができないため、別の方法を使用
                # まず通常再生を開始してからシークコマンドを実行
                subprocess.Popen(["audacious", filepath])
                # 少し待ってからシークコマンドを実行
                time.sleep(1)
                # audtoolを使用して指定位置にシーク
                try:
                    subprocess.run(["audtool", "playback-seek", str(start_position)], check=True)
                    print(f"\n再生開始: {filepath} (位置: {start_position:.1f}秒)")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print(f"\nシーク失敗。通常再生: {filepath}")
            else:
                subprocess.run(["audacious", filepath], check=True)
                print(f"\n再生開始: {filepath}")
        except subprocess.CalledProcessError as e:
            print(f"\n再生エラー: {e}")
        except FileNotFoundError:
            print("\naudaciousが見つかりません。インストールされているか確認してください。")
    
    def parse_time_for_date(self, time_str, base_date):
        """指定された基準日に対して時刻文字列を解析"""
        try:
            # BOM（Byte Order Mark）を除去
            time_str = time_str.strip().lstrip('\ufeff')
            
            # 時刻を解析
            parts = time_str.split(':')
            if len(parts) != 3:
                raise ValueError("時刻形式が正しくありません")
            
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2])
            
            # 24時以降の場合は翌日の時刻として計算
            if hour >= 24:
                # 24時以降は翌日
                target_date = base_date + timedelta(days=1)
                actual_hour = hour - 24
            else:
                # 通常の時刻
                if hour < self.day_end_hour:
                    # 日替わり時刻より前なら翌日
                    target_date = base_date + timedelta(days=1)
                else:
                    # 日替わり時刻以降なら当日
                    target_date = base_date
                actual_hour = hour
            
            # 時刻の妥当性チェック
            if not (0 <= actual_hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                raise ValueError("時刻の値が範囲外です")
            
            return datetime.combine(target_date, datetime.min.time().replace(
                hour=actual_hour, minute=minute, second=second
            ))
            
        except (ValueError, IndexError) as e:
            print(f"時刻解析エラー: {time_str} - {e}")
            return None
    
    def parse_time(self, time_str):
        """現在の放送日を基準にして時刻を解析"""
        broadcast_date = self.get_broadcast_date()
        return self.parse_time_for_date(time_str, broadcast_date)
    
    def wait_for_csv_file(self, csv_path, is_background=False):
        """CSVファイルが見つかるまで待機（修正版：バックグラウンド専用）"""
        attempt_count = 0
        max_attempts = 60  # 最大60回（60分）試行
        
        while not os.path.exists(csv_path) and attempt_count < max_attempts:
            attempt_count += 1
            filename = os.path.basename(csv_path)
            
            print(f"\n翌日分CSVファイルが見つかりません: {filename} (試行{attempt_count}/{max_attempts}回目)")
            print("1分後に再試行します...")
            
            # 1分間待機
            time.sleep(60)
            
        if os.path.exists(csv_path):
            if attempt_count > 0:
                print(f"\nCSVファイルが見つかりました: {os.path.basename(csv_path)}")
            return True
        else:
            print(f"\n警告: 翌日分CSVファイルが見つかりませんでした: {os.path.basename(csv_path)}")
            print(f"{max_attempts}分間待機しましたが、ファイルが配置されませんでした。")
            return False

    def load_csv_records(self, csv_path, base_date, is_background=False):
        """指定されたCSVファイルからレコードを読み込み"""
        # バックグラウンドの場合のみファイル待機
        if is_background:
            if not self.wait_for_csv_file(csv_path, is_background):
                return []
        elif not os.path.exists(csv_path):
            # フォアグラウンドでファイルが見つからない場合は即座に失敗
            print(f"CSVファイルが見つかりません: {csv_path}")
            return []
        
        records = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                
                for row in reader:
                    if len(row) < 4:  # 最低4カラム必要
                        continue
                    
                    time_str = row[0].strip()
                    source = row[1].strip()      # 使用しないが読み込み
                    mix = row[2].strip()         # 使用しないが読み込み
                    filename = row[3].strip()
                    
                    # 空行やヘッダー行をスキップ
                    if not time_str or time_str.lower() in ['time', '時刻', 'タイム']:
                        continue
                    
                    # 時刻を解析（指定された基準日で）
                    scheduled_time = self.parse_time_for_date(time_str, base_date)
                    if scheduled_time is None:
                        continue
                    
                    record = {
                        'time': scheduled_time,
                        'source': source,
                        'mix': mix,
                        'filename': filename,
                        'filepath': None,
                        'broadcast_date': base_date  # どの日のレコードかを記録
                    }
                    
                    records.append(record)
        
        except Exception as e:
            print(f"CSVファイル読み込みエラー: {e}")
            return []
        
        return records
    
    def load_next_day_csv_background(self):
        """翌日のCSVファイルをバックグラウンドで読み込む（スレッド用）"""
        next_day_csv_path = self.get_next_day_csv_path()
        broadcast_date = self.get_broadcast_date()
        next_day = broadcast_date + timedelta(days=1)
        
        print(f"\nバックグラウンドで翌日分CSVを読み込み中: {next_day_csv_path}")
        next_day_records = self.load_csv_records(next_day_csv_path, next_day, is_background=True)
        
        if next_day_records:
            # 時刻順にソートしてから追加
            next_day_records.sort(key=lambda x: x['time'])
            self.all_records.extend(next_day_records)
            print(f"\n翌日分 {len(next_day_records)} レコードを追加しました")
            self.next_day_loaded = True
        else:
            print("\n翌日分のCSVファイルが見つからないか、有効なレコードがありません")
            # ファイルが見つからない場合でもフラグは立てない（再試行のため）
        
        self.next_day_loading = False

    def load_next_day_csv(self):
        """翌日のCSVファイルを読み込んで追加（バックグラウンド対応）"""
        if self.next_day_loaded or self.next_day_loading:
            return
        
        self.next_day_loading = True
        
        # バックグラウンドスレッドで実行
        background_thread = threading.Thread(
            target=self.load_next_day_csv_background, 
            daemon=True
        )
        background_thread.start()
    
    def check_next_day_csv_availability(self):
        """翌日分CSVの読み込み状況をチェック（ノンブロッキング）"""
        if not self.next_day_check_started:
            # 残りレコード数をチェック
            remaining_count = len(self.all_records) - self.current_record_index - 1
            if remaining_count <= self.preload_threshold:
                print(f"\n残りレコード数が {remaining_count} 個になりました。翌日分CSVの読み込みを開始します。")
                self.load_next_day_csv()
                self.next_day_check_started = True
    
    def is_end_of_schedule(self):
        """スケジュール終了かどうかをチェック"""
        # 現在のレコードが最後のレコードかどうか
        if self.current_record_index >= len(self.all_records) - 1:
            # 翌日分が読み込み済みなら継続
            if self.next_day_loaded:
                return False
            # 翌日分の読み込みがまだなら、読み込み開始（既に開始済みなら何もしない）
            elif not self.next_day_loading:
                print("\n最終レコードに到達しました。翌日分CSVの読み込みを開始します。")
                self.load_next_day_csv()
            return True  # 翌日分が読み込まれるまでは終了扱い
        return False
        
    def load_and_process_csv(self):
        """CSVファイルを読み込み、レコードを処理"""
        csv_path = self.get_today_csv_path()
        broadcast_date = self.get_broadcast_date()
        
        # 今日分のCSVが存在しない場合は待機
        if not os.path.exists(csv_path):
            print(f"\n本日分のCSVファイルが見つかりません: {csv_path}")
            print("ファイルが配置されるまで待機します...")
            while not os.path.exists(csv_path):
                time.sleep(60)
                print(f"再試行中... {datetime.now().strftime('%H:%M:%S')}")
            print("CSVファイルが見つかりました。")
        
        # 今日分のレコードを読み込み
        self.all_records = self.load_csv_records(csv_path, broadcast_date)
        
        if not self.all_records:
            return []
        
        # 時刻順にソート
        self.all_records.sort(key=lambda x: x['time'])
        
        current_time = datetime.now()
        
        # 現在時刻より前のレコードをスキップし、CurrentRecordを特定
        for i, record in enumerate(self.all_records):
            if record['time'] <= current_time:
                self.current_record = record
                self.current_record_index = i
            else:
                # 次のレコードをNextRecordとして設定
                if i < len(self.all_records):
                    self.next_record = self.all_records[i]
                break
        
        return self.all_records
    
    def start_current_playback(self):
        """現在のレコードの再生を開始（修正版）"""
        if self.current_record:
            filename = self.current_record['filename']
            filepath = self.find_media_file(filename)
            self.current_record['filepath'] = filepath
            
            # JACK接続モード変更を処理（統一メソッド使用）
            self.handle_jack_mode_change(self.current_record)
            
            # 翌日分CSVのチェック（レコード演奏時）
            self.check_next_day_csv_availability()
            
            # 現在時刻と開始予定時刻の差を計算
            current_time = datetime.now()
            scheduled_time = self.current_record['time']
            elapsed_seconds = (current_time - scheduled_time).total_seconds()
            
            # 実際の再生開始時刻を記録
            self.current_start_time = current_time
            
            print()  # 改行してから情報表示
            if elapsed_seconds > 0:
                # 開始時刻を過ぎている場合、その分をスキップして再生
                minutes = int(elapsed_seconds // 60)
                seconds = int(elapsed_seconds % 60)
                print(f"現在演奏中: {self.format_broadcast_time(scheduled_time)} - {filename}")
                print(f"開始時刻から {minutes}:{seconds:02d} 経過。該当位置から再生開始")
                self.play_audio_file(filepath, elapsed_seconds)
            else:
                # 開始時刻がまだ来ていない場合（通常はここには来ない）
                print(f"現在演奏中: {self.format_broadcast_time(scheduled_time)} - {filename}")
                self.play_audio_file(filepath)
        else:
            print("現在演奏中のレコードがありません")
    
    def get_next_record_from_list(self):
        """リストから次のレコードを取得"""
        current_time = datetime.now()
        
        # 現在のインデックスから次のレコードを探す
        for i in range(self.current_record_index + 1, len(self.all_records)):
            record_time = self.all_records[i]['time']
            if record_time > current_time:
                return self.all_records[i], i
        
        return None, -1
    
    def wait_and_play_next(self):
        """次のレコードの時刻まで待機して再生"""
        # 翌日分CSVのチェック（毎回実行）
        self.check_next_day_csv_availability()
        
        # 次のレコードを取得
        next_record, next_index = self.get_next_record_from_list()
        
        if not next_record:
            # 次のレコードがない場合の処理
            if self.is_end_of_schedule():
                # 翌日分が読み込み中の場合は待機
                if self.next_day_loading and not self.next_day_loaded:
                    print("\n翌日分CSVの読み込み完了を待機中...")
                    # ノンブロッキングで待機（演奏は継続）
                    wait_count = 0
                    while self.next_day_loading and not self.next_day_loaded and wait_count < 300:  # 最大5分待機
                        time.sleep(1)
                        wait_count += 1
                    
                    if self.next_day_loaded:
                        print("翌日分CSVの読み込みが完了しました。放送を継続します。")
                        # 再度次のレコードを取得
                        next_record, next_index = self.get_next_record_from_list()
                        if not next_record:
                            print("次のレコードがありません")
                            return False
                    else:
                        print("翌日分CSVの読み込みが完了しませんでした。")
                        return False
                else:
                    print("次のレコードがありません")
                    return False
            else:
                print("次のレコードがありません")
                return False
        
        self.next_record = next_record
        current_time = datetime.now()
        scheduled_time = self.next_record['time']
        
        if scheduled_time <= current_time:
            # 既に時刻が過ぎている場合はすぐに再生
            self.play_next_record(next_index)
            return True
        
        # 待機時間を計算
        wait_seconds = (scheduled_time - current_time).total_seconds()
        print()  # 改行
        print(f"次の再生予定: {self.format_broadcast_time(scheduled_time)} - {self.next_record['filename']}")
        
        # 時間表示スレッドを開始（まだ開始していない場合）
        if not self.display_running:
            self.start_display_thread()
        
        # 待機（1秒刻みでチェック）
        while wait_seconds > 0:
            time.sleep(1)
            current_time = datetime.now()
            wait_seconds = (scheduled_time - current_time).total_seconds()
        
        # 再生
        self.play_next_record(next_index)
        return True
    
    def play_next_record(self, next_index):
        """次のレコードを再生し、CurrentとNextを更新（修正版）"""
        if self.next_record:
            filename = self.next_record['filename']
            filepath = self.find_media_file(filename)
            self.next_record['filepath'] = filepath
            
            # JACK接続モード変更を処理（統一メソッド使用）
            self.handle_jack_mode_change(self.next_record)
            
            # 翌日分CSVのチェック（レコード演奏時）
            self.check_next_day_csv_availability()
            
            # 実際の再生開始時刻を記録
            self.current_start_time = datetime.now()
            
            print()  # 改行してから情報表示
            print(f"再生開始: {self.format_broadcast_time(self.next_record['time'])} - {filename}")
            self.play_audio_file(filepath)  # 次のレコードは時刻通りなので位置指定なし
            
            # CurrentRecordとインデックスを更新
            self.current_record = self.next_record
            self.current_record_index = next_index
            self.next_record = None
    
    def run(self):
        """メインの実行ループ"""
        print("放送スケジューラーを開始します...")
        
        try:
            # CSVファイルを読み込み
            records = self.load_and_process_csv()
            
            if not records:
                print("有効なレコードがありません")
                return
            
            print(f"総レコード数: {len(records)}")
            
            # 現在の設定を表示
            print(f"放送日終了時刻: {self.day_end_hour:02d}:00:00")
            current_broadcast_time = self.format_broadcast_time(datetime.now())
            print(f"現在の放送時刻: {current_broadcast_time}")
            broadcast_date = self.get_broadcast_date()
            print(f"放送日: {broadcast_date.strftime('%Y-%m-%d')}")
            print()
            
            # 現在演奏中のファイルがある場合は再生開始
            if self.current_record:
                self.start_current_playback()
            
            # 時間表示スレッドを開始
            #self.start_display_thread()
            
            # 残りのレコードを順次処理
            while True:
                if not self.wait_and_play_next():
                    break
                
                # 全レコード終了チェック（簡略化）
                if self.current_record_index >= len(self.all_records) - 1:
                    if not self.next_day_loaded:
                        # 翌日分が読み込まれていない場合の最終確認
                        if self.next_day_loading:
                            print("\n翌日分CSVの最終読み込み完了を待機中...")
                            # 最大10分待機
                            wait_count = 0
                            while self.next_day_loading and not self.next_day_loaded and wait_count < 600:
                                time.sleep(1)
                                wait_count += 1
                            
                            if self.next_day_loaded:
                                print("翌日分CSVの読み込みが完了しました。放送を継続します。")
                                continue
                            else:
                                print("翌日分CSVの読み込みが完了しませんでした。")
                                break
                        else:
                            print()
                            print("すべてのレコードの処理が完了しました（翌日分CSVなし）")
                            break
                    else:
                        # 翌日分も含めて全て終了
                        print()
                        print("すべてのレコードの処理が完了しました")
                        break
        
        finally:
            # 時間表示スレッドを停止
            self.stop_display_thread()

def main():
    # 日替わり時刻をコマンドライン引数で設定
    import sys
    
    day_end_hour = 4  # デフォルト値（午前4時）
    
    # バージョン表示
    if len(sys.argv) > 1 and sys.argv[1] in ['-v', '--version']:
        print(f"EasyAPS version {version}")
        return
    
    # 使用方法の表示
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("使用方法: python3 easyaps.py [オプション] [日替わり時刻]")
        print("オプション:")
        print("  -v, --version    バージョン情報を表示")
        print("  -h, --help       この使用方法を表示")
        print()
        print("日替わり時刻: 0-5の数字で指定（午前0時〜5時）")
        print("例:")
        print("  python3 easyaps.py     # 午前4時で日替わり（デフォルト）")
        print("  python3 easyaps.py 3   # 午前3時で日替わり")
        print("  python3 easyaps.py 5   # 午前5時で日替わり")
        print("  python3 easyaps.py -v  # バージョン表示")
        return
    
    # コマンドライン引数で日替わり時刻を指定
    if len(sys.argv) > 1:
        try:
            day_end_hour = int(sys.argv[1])
            if not (0 <= day_end_hour <= 5):
                print("エラー: 日替わり時刻は0-5の範囲で指定してください")
                print("0=午前0時, 1=午前1時, 2=午前2時, 3=午前3時, 4=午前4時, 5=午前5時")
                return
        except ValueError:
            print("エラー: 日替わり時刻は数値で指定してください")
            print("使用方法: python3 easyaps.py [0-5]")
            return
    
    print(f"放送スケジューラー - 日替わり時刻: 午前{day_end_hour}時 (version {version})")
    print("=" * 50)
    
    scheduler = MusicScheduler(day_end_hour=day_end_hour)
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\nプログラムが中断されました")
        scheduler.stop_display_thread()
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        scheduler.stop_display_thread()

if __name__ == "__main__":
    main()