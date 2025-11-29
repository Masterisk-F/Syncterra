"""
AudioSync スキャン機能

既存のaudio_sync_data.pyのロジックを活用し、DB経由でファイルスキャンを実行する
"""

import os
from typing import List, Dict, Any, Callable
from audio_sync_data import AudioSyncData
from database import Database
from logger import setup_logger

logger = setup_logger(__name__)


def scan_audio_files(
    db: Database,
    progress_callback: Callable[[int, int, str], None] = None,
    update_all: bool = False
) -> Dict[str, int]:
    """
    音楽ファイルをスキャンしてDBに保存
    AudioSyncData.update()のロジックを移植
    
    Args:
        db: Databaseインスタンス
        progress_callback: 進捗コールバック関数 (current, total, message)
        update_all: Trueの場合、変更がないファイルも強制的に再スキャンする
    
    Returns:
        結果の辞書 {'added': 追加件数, 'updated': 更新件数, 'total': 総件数}
    """
    import datetime
    
    # 設定を取得
    settings = db.get_all_settings()
    sync_dir_from = settings.get('sync_dir_from', '').split(',')
    sync_dir_from = [d.strip() for d in sync_dir_from if d.strip()]
    include_ext = settings.get('include_ext', 'mp3,m4a,mp4').split(',')
    include_ext = ['.' + ext.strip() for ext in include_ext if ext.strip()]
    
    if not sync_dir_from:
        raise ValueError("対象ディレクトリが設定されていません")
    
    # DBから既存のファイル情報を取得（キャッシュとして使用）
    existing_files = db.get_all_audio_files()
    existing_files_map = {f['filepath_from']: f for f in existing_files}
    found_flags = {f['id']: False for f in existing_files}
    
    # ファイルパスリストを取得
    if progress_callback:
        progress_callback(0, 100, "ファイルパスを収集中...")
    
    filepath_list = []
    for dir_path in sync_dir_from:
        if not os.path.exists(dir_path):
            logger.warning(f"Directory not found: {dir_path}")
            continue
        filepath_list.extend(_get_audio_filepath_list(dir_path, include_ext))
    
    total_files = len(filepath_list)
    if progress_callback:
        progress_callback(0, total_files, f"{total_files}個のファイルをスキャン中...")
    
    added_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i, filepath in enumerate(filepath_list):
        try:
            # ディスク上のファイルの更新日時を取得
            stat = os.stat(filepath)
            current_mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(sep=" ", timespec="seconds")
            
            # DBにあるか確認
            existing_record = existing_files_map.get(filepath)
            
            use_cache = False
            if existing_record and not update_all:
                # DBの更新日時と比較
                if existing_record.get('update_date') == current_mtime:
                    use_cache = True
            
            if use_cache:
                # 変更なし：スキップ（DBの情報をそのまま使う）
                found_flags[existing_record['id']] = True
                
                # msgが"-"（削除扱い）だった場合は、ファイルが復活したのでクリアする
                if existing_record.get('msg') == "-":
                    # msgをクリアして更新
                    # update_audio_fileは全カラム更新なので、既存の値をベースにmsgだけ変更する
                    existing_record['msg'] = ""
                    db.update_audio_file(existing_record['id'], existing_record)
                    updated_count += 1
                    logger.debug(f"Recovered file (cleared msg): {filepath}")
                else:
                    skipped_count += 1
                    logger.debug(f"Skip (Use cache): {filepath}")
                
            else:
                # ディスクから読み込み（新規 or 更新 or 強制更新）
                # ファイルの相対パスを計算（ベースディレクトリ名を含める）
                relative_path = None
                for base_dir in sync_dir_from:
                    if filepath.startswith(base_dir):
                        # ベースディレクトリの親ディレクトリからの相対パスを計算
                        parent_dir = os.path.dirname(base_dir.rstrip(os.sep))
                        relative_path = "/" + os.path.relpath(filepath, parent_dir)
                        break
                if not relative_path:
                    relative_path = os.path.basename(filepath)
                
                # Audioオブジェクトを作成してメタデータ取得
                audio = AudioSyncData.Audio(filepath=filepath, relative_filepath=relative_path)
                
                # 辞書に変換
                audio_data = {
                    'msg': audio.msg,
                    'sync': 1 if audio.sync == "○" else 0, # デフォルト値（新規の場合）
                    'title': audio.title,
                    'artist': audio.artist,
                    'album_artist': audio.album_artist,
                    'composer': audio.composer,
                    'album': audio.album,
                    'track_num': audio.track_num,
                    'length': audio.length,
                    'filename': audio.filename,
                    'filepath_from': audio.filepath_from,
                    'filepath_to_relative': audio.filepath_to_relative,
                    'codec': audio.codec,
                    'update_date': audio.update_date, # ここにはcurrent_mtimeが入っているはず
                    'added_date': audio.added_date
                }
                
                if existing_record:
                    # 既存レコードの更新
                    file_id = existing_record['id']
                    found_flags[file_id] = True
                    
                    # syncとadded_dateは既存の値を保持
                    audio_data['sync'] = existing_record['sync']
                    audio_data['added_date'] = existing_record['added_date']
                    
                    db.update_audio_file(file_id, audio_data)
                    updated_count += 1
                else:
                    # 新規追加
                    # added_dateはAudioクラスで現在時刻が設定されている
                    db.insert_audio_file(audio_data)
                    added_count += 1
            
            if progress_callback and (i + 1) % 10 == 0:
                progress_callback(i + 1, total_files, f"{i + 1}/{total_files} スキャン中...")
                
        except Exception as e:
            logger.error(f"Failed to scan {filepath}: {e}")
            continue

    # 存在しないファイルの処理（msgに"-"を入れる）
    deleted_count = 0
    for file_id, found in found_flags.items():
        if not found:
            # DBにはあるがディスクに見つからなかったファイル
            # msgを"-"に更新
            # 既存のレコードを取得してmsgだけ書き換えるのが安全だが、SQLで直接更新も可
            # ここではupdate_audio_fileを使うためにデータを取得したいが、
            # 部分更新メソッドがないので、SQL直接実行するメソッドを追加するか、既存メソッドを使う。
            # 今回は簡易的にSQLを実行するメソッドがないので、getしてupdateする。
            
            record = db.get_audio_file_by_id(file_id)
            if record and record.get('msg') != "-":
                record['msg'] = "-"
                db.update_audio_file(file_id, record)
                deleted_count += 1

    if progress_callback:
        progress_callback(total_files, total_files, "完了")
    
    return {
        'added': added_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'deleted': deleted_count,
        'total': total_files
    }


def _get_audio_filepath_list(dir_path: str, include_ext: List[str]) -> List[str]:
    """
    ディレクトリから音楽ファイルパスを再帰的に収集
    
    Args:
        dir_path: 検索ディレクトリ
        include_ext: 対象拡張子のリスト（例: ['.mp3', '.m4a']）
    
    Returns:
        ファイルパスのリスト
    """
    filepath_list = []
    
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            # 拡張子チェック
            if any(file.lower().endswith(ext.lower()) for ext in include_ext):
                filepath_list.append(os.path.join(root, file))
    
    return filepath_list
