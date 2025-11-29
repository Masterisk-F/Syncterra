"""
Excel AudioSyncData.xlsx から SQLiteデータベースへの移行スクリプト

既存のExcelファイルのデータをSQLiteデータベースに移行します。
"""

import os
import sys
import shutil
from datetime import datetime

from audio_sync_data import AudioSyncData
from database import Database
from logger import setup_logger

logger = setup_logger(__name__)


def migrate_from_excel(excel_path: str, db_path: str = None, backup: bool = True):
    """
    ExcelファイルからSQLiteデータベースへデータを移行
    
    Args:
        excel_path: AudioSyncData.xlsxのパス
        db_path: 移行先SQLiteデータベースのパス（Noneの場合は自動設定）
        backup: True の場合、既存のDBファイルをバックアップ
    """
    
    # Excelファイルの存在確認
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found: {excel_path}")
        print(f"❌ Excelファイルが見つかりません: {excel_path}")
        return False
    
    logger.info(f"Starting migration from Excel: {excel_path}")
    print(f"📊 Excelファイルを読み込み中: {excel_path}")
    
    # Excelデータを読み込み
    try:
        excel_data = AudioSyncData(excel_path)
    except Exception as e:
        logger.error(f"Failed to load Excel file: {e}")
        print(f"❌ Excelファイルの読み込みに失敗: {e}")
        return False
    
    # データベースパスの設定
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "AudioSyncData.db")
    
    # 既存DBのバックアップ
    if backup and os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        logger.info(f"Backed up existing database to: {backup_path}")
        print(f"💾 既存のDBをバックアップ: {backup_path}")
    
    # 既存DBを削除（新規作成）
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Removed existing database: {db_path}")
    
    # 新しいデータベースを作成
    db = Database(db_path)
    logger.info(f"Created new database: {db_path}")
    print(f"🗄️  新しいデータベースを作成: {db_path}")
    
    # 設定値を移行
    print("\n📝 設定を移行中...")
    migrate_settings(excel_data, db)
    
    # 音楽ファイルを移行（Albums + Not in Albums）
    print("\n🎵 音楽ファイルを移行中...")
    albums_count = migrate_audio_files(excel_data.sheet_Albums, db, "Albums")
    not_in_albums_count = migrate_audio_files(excel_data.sheet_Not_in_Albums, db, "Not in Albums")
    
    # プレイリストを移行
    print("\n📋 プレイリストを移行中...")
    playlist_count = migrate_playlists(excel_data, db)
    
    # 移行結果のサマリー
    print("\n" + "="*60)
    print("✅ 移行完了！")
    print("="*60)
    print(f"音楽ファイル（Albums）: {albums_count}件")
    print(f"音楽ファイル（Not in Albums）: {not_in_albums_count}件")
    print(f"プレイリスト: {playlist_count}件")
    print(f"データベース: {db_path}")
    print("="*60)
    
    logger.info("Migration completed successfully")
    return True


def migrate_settings(excel_data: AudioSyncData, db: Database):
    """設定値を移行"""
    
    # 対象ディレクトリ
    include_dirs = list(excel_data.include_dir)
    if include_dirs:
        db.set_setting('sync_dir_from', ','.join(include_dirs))
        logger.info(f"Migrated sync_dir_from: {len(include_dirs)} directories")
    
    # 対象拡張子
    include_exts = list(excel_data.include_extention)
    if include_exts:
        # .を除去してカンマ区切りに
        exts = ','.join([ext.lstrip('.') for ext in include_exts])
        db.set_setting('include_ext', exts)
        logger.info(f"Migrated include_ext: {exts}")
    
    # 同期先ディレクトリ
    sync_dirs = excel_data.dir_to_synchronize
    if sync_dirs:
        db.set_setting('sync_dir_to', ','.join(sync_dirs))
        logger.info(f"Migrated sync_dir_to: {len(sync_dirs)} directories")
    
    print("   設定値の移行完了")


def migrate_audio_files(sheet, db: Database, sheet_name: str) -> int:
    """音楽ファイルを移行"""
    count = 0
    total_rows = sheet._Sheet__sheet.max_row  # 内部属性にアクセスして行数を取得
    print(f"   {sheet_name}: 全{total_rows}行を処理開始...")
    
    # プログレスバーのような表示のために
    import time
    start_time = time.time()
    
    for i, audio in enumerate(sheet):
        # 100件ごとに進捗表示
        if i > 0 and i % 100 == 0:
            elapsed = time.time() - start_time
            print(f"   ... {i}件処理中 ({elapsed:.1f}秒経過)")
            
        # Audioオブジェクトから辞書を作成
        audio_data = {
            'msg': audio.msg,
            'sync': 1 if audio.sync == "○" else 0,
            'title': audio.title,
            'artist': audio.artist,
            'album_artist': audio.album_artist,
            'composer': audio.composer,
            'album': audio.album,
            'track_num': str(audio.track_num) if audio.track_num else None,
            'length': audio.length,
            'filename': audio.filename,
            'filepath_from': audio.filepath_from,
            'filepath_to_relative': audio.filepath_to_relative,
            'codec': audio.codec,
            'update_date': audio.update_date,
            'added_date': audio.added_date
        }
        
        try:
            db.insert_audio_file(audio_data)
            count += 1
            
            # キャッシュテーブルは廃止されました
            # db.set_cache(cache_data)
            
        except Exception as e:
            logger.warning(f"Failed to migrate audio file: {audio.filepath_from}, error: {e}")
            # print(f"   ⚠️  スキップ: {audio.filename} ({e})") # エラーが多いと埋もれるのでログのみに
    
    print(f"   {sheet_name}: {count}件の音楽ファイルを移行完了")
    logger.info(f"Migrated {count} audio files from {sheet_name}")
    return count


def migrate_playlists(excel_data: AudioSyncData, db: Database) -> int:
    """プレイリストを移行"""
    count = 0
    
    playlists = excel_data.sheets_playlist
    
    for playlist_name, sheet in playlists.items():
        # プレイリストを作成
        try:
            playlist_id = db.create_playlist(playlist_name)
            
            # プレイリスト内のアイテムを収集
            audio_file_ids = []
            for audio in sheet:
                # ファイルパスからaudio_file_idを取得
                audio_file = db.get_audio_file_by_filepath(audio.filepath_from)
                if audio_file:
                    audio_file_ids.append(audio_file['id'])
                else:
                    logger.warning(f"Audio file not found for playlist item: {audio.filepath_from} in playlist {playlist_name}")
            
            # プレイリストにまとめて追加
            if audio_file_ids:
                db.add_to_playlist_many(playlist_id, audio_file_ids)
                item_count = len(audio_file_ids)
                print(f"   {playlist_name}: {item_count}曲")
                logger.info(f"Migrated playlist '{playlist_name}' with {item_count} items")
                count += 1
            else:
                print(f"   {playlist_name}: 0曲 (追加するファイルが見つかりませんでした)")
                logger.info(f"Migrated playlist '{playlist_name}' with 0 items")
            
        except Exception as e:
            logger.warning(f"Failed to migrate playlist: {playlist_name}, error: {e}")
            print(f"   ⚠️  プレイリストのスキップ: {playlist_name} ({e})")
    
    print(f"   合計 {count}個のプレイリストを移行")
    return count


def main():
    """メイン処理"""
    # デフォルトパス
    script_dir = os.path.dirname(__file__)
    default_excel_path = os.path.join(script_dir, "AudioSyncData.xlsx")
    
    # コマンドライン引数の確認
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = default_excel_path
    
    # 移行実行
    success = migrate_from_excel(excel_path, backup=True)
    
    if not success:
        sys.exit(1)
    
    print("\n💡 移行したデータベースを確認するには:")
    print("   python -c \"from database import Database; db = Database(); print(db.get_all_audio_files())\"")


if __name__ == "__main__":
    main()
