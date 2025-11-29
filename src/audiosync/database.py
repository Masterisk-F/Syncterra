"""
AudioSync データベースアクセス層

SQLiteデータベースへのアクセスを提供するモジュール
"""

import sqlite3
import os
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

from logger import setup_logger
logger = setup_logger(__name__)


class Database:
    """SQLiteデータベース接続とCRUD操作を提供するクラス"""
    
    def __init__(self, db_path: str = None):
        """
        データベース接続を初期化
        
        Args:
            db_path: データベースファイルのパス。Noneの場合はデフォルトパスを使用
        """
        if db_path is None:
            # デフォルトパス: このファイルと同じディレクトリ
            db_path = os.path.join(os.path.dirname(__file__), "AudioSyncData.db")
        
        self.db_path = db_path
        self._ensure_database_exists()
        logger.info(f"Database initialized: {self.db_path}")
    
    def _ensure_database_exists(self):
        """データベースファイルが存在しない場合は作成し、スキーマを初期化"""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new database: {self.db_path}")
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            
            logger.info("Database schema created successfully")
    
    @contextmanager
    def get_connection(self):
        """
        データベース接続をコンテキストマネージャとして取得
        
        Yields:
            sqlite3.Connection: データベース接続
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能にする
        try:
            yield conn
        finally:
            conn.close()
    
    # ==================== 音楽ファイル操作 ====================
    
    def get_all_audio_files(self, sync_only: bool = False) -> List[Dict[str, Any]]:
        """
        全ての音楽ファイルを取得
        
        Args:
            sync_only: Trueの場合、sync=1のファイルのみを取得
        
        Returns:
            音楽ファイル情報の辞書リスト
        """
        with self.get_connection() as conn:
            if sync_only:
                cursor = conn.execute(
                    "SELECT * FROM audio_files WHERE sync = 1 ORDER BY album, track_num"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audio_files ORDER BY album, track_num"
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_audio_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """
        IDで音楽ファイルを取得
        
        Args:
            file_id: ファイルID
        
        Returns:
            音楽ファイル情報の辞書、見つからない場合はNone
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM audio_files WHERE id = ?", (file_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_audio_file_by_filepath(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        ファイルパスで音楽ファイルを取得
        
        Args:
            filepath: ファイルパス
        
        Returns:
            音楽ファイル情報の辞書、見つからない場合はNone
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM audio_files WHERE filepath_from = ?", (filepath,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def insert_audio_file(self, audio_data: Dict[str, Any]) -> int:
        """
        音楽ファイルを挿入
        
        Args:
            audio_data: 音楽ファイル情報の辞書
        
        Returns:
            挿入されたレコードのID
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO audio_files (
                    msg, sync, title, artist, album_artist, composer, album,
                    track_num, length, filename, filepath_from, filepath_to_relative,
                    codec, update_date, added_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audio_data.get('msg'),
                audio_data.get('sync', 0),
                audio_data.get('title'),
                audio_data.get('artist'),
                audio_data.get('album_artist'),
                audio_data.get('composer'),
                audio_data.get('album'),
                audio_data.get('track_num'),
                audio_data.get('length'),
                audio_data.get('filename'),
                audio_data.get('filepath_from'),
                audio_data.get('filepath_to_relative'),
                audio_data.get('codec'),
                audio_data.get('update_date'),
                audio_data.get('added_date')
            ))
            conn.commit()
            logger.info(f"Inserted audio file: {audio_data.get('filepath_from')}")
            return cursor.lastrowid
    
    def update_audio_file(self, file_id: int, audio_data: Dict[str, Any]):
        """
        音楽ファイル情報を更新
        
        Args:
            file_id: ファイルID
            audio_data: 更新する音楽ファイル情報の辞書
        """
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE audio_files SET
                    msg = ?, sync = ?, title = ?, artist = ?, album_artist = ?,
                    composer = ?, album = ?, track_num = ?, length = ?, filename = ?,
                    filepath_from = ?, filepath_to_relative = ?, codec = ?,
                    update_date = ?, added_date = ?
                WHERE id = ?
            """, (
                audio_data.get('msg'),
                audio_data.get('sync'),
                audio_data.get('title'),
                audio_data.get('artist'),
                audio_data.get('album_artist'),
                audio_data.get('composer'),
                audio_data.get('album'),
                audio_data.get('track_num'),
                audio_data.get('length'),
                audio_data.get('filename'),
                audio_data.get('filepath_from'),
                audio_data.get('filepath_to_relative'),
                audio_data.get('codec'),
                audio_data.get('update_date'),
                audio_data.get('added_date'),
                file_id
            ))
            conn.commit()
            logger.info(f"Updated audio file ID: {file_id}")
    
    def update_sync_status(self, file_id: int, sync: bool):
        """
        sync状態のみを更新
        
        Args:
            file_id: ファイルID
            sync: sync状態（True/False）
        """
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE audio_files SET sync = ? WHERE id = ?",
                (1 if sync else 0, file_id)
            )
            conn.commit()
            logger.debug(f"Updated sync status for ID {file_id}: {sync}")

    def update_sync_status_many(self, file_ids: List[int], sync: bool):
        """
        複数のファイルのsync状態を一括更新
        
        Args:
            file_ids: ファイルIDのリスト
            sync: sync状態（True/False）
        """
        if not file_ids:
            return
            
        with self.get_connection() as conn:
            # プレースホルダを作成 (?, ?, ...)
            placeholders = ','.join(['?'] * len(file_ids))
            sql = f"UPDATE audio_files SET sync = ? WHERE id IN ({placeholders})"
            
            # パラメータ結合: [sync_val, id1, id2, ...]
            params = [1 if sync else 0] + file_ids
            
            conn.execute(sql, params)
            conn.commit()
            logger.info(f"Updated sync status for {len(file_ids)} files to {sync}")
    
    def delete_audio_file(self, file_id: int):
        """
        音楽ファイルを削除
        
        Args:
            file_id: ファイルID
        """
        with self.get_connection() as conn:
            # プレイリストからも削除
            conn.execute("DELETE FROM playlist_items WHERE audio_file_id = ?", (file_id,))
            # 本体削除
            conn.execute("DELETE FROM audio_files WHERE id = ?", (file_id,))
            conn.commit()
            logger.info(f"Deleted audio file ID: {file_id}")

    def delete_audio_files(self, file_ids: List[int]):
        """
        複数の音楽ファイルを一括削除
        
        Args:
            file_ids: ファイルIDのリスト
        """
        if not file_ids:
            return
            
        with self.get_connection() as conn:
            placeholders = ','.join(['?'] * len(file_ids))
            
            # プレイリストからも削除
            conn.execute(f"DELETE FROM playlist_items WHERE audio_file_id IN ({placeholders})", file_ids)
            
            # 本体削除
            conn.execute(f"DELETE FROM audio_files WHERE id IN ({placeholders})", file_ids)
            
            conn.commit()
            logger.info(f"Deleted {len(file_ids)} audio files")
    
    # ==================== 設定操作 ====================
    
    def get_setting(self, key: str) -> Optional[str]:
        """
        設定値を取得
        
        Args:
            key: 設定キー
        
        Returns:
            設定値、存在しない場合はNone
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else None
    
    def get_all_settings(self) -> Dict[str, str]:
        """
        全ての設定を取得
        
        Returns:
            設定の辞書
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            return {row['key']: row['value'] for row in cursor.fetchall()}
    
    def set_setting(self, key: str, value: str):
        """
        設定値を更新または挿入
        
        Args:
            key: 設定キー
            value: 設定値
        """
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
            logger.debug(f"Set setting: {key} = {value}")
    
    # ==================== プレイリスト操作 ====================
    
    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """
        全てのプレイリストを取得
        
        Returns:
            プレイリスト情報の辞書リスト
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM playlists ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_playlist_items(self, playlist_id: int) -> List[Dict[str, Any]]:
        """
        プレイリスト内のアイテムを取得
        
        Args:
            playlist_id: プレイリストID
        
        Returns:
            音楽ファイル情報の辞書リスト（positionを含む）
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT af.*, pi.position, pi.audio_file_id FROM audio_files af
                JOIN playlist_items pi ON af.id = pi.audio_file_id
                WHERE pi.playlist_id = ?
                ORDER BY pi.position
            """, (playlist_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def create_playlist(self, name: str) -> int:
        """
        プレイリストを作成
        
        Args:
            name: プレイリスト名
        
        Returns:
            作成されたプレイリストのID
        """
        from datetime import datetime
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO playlists (name, created_date, updated_date) VALUES (?, ?, ?)",
                (name, now, now)
            )
            conn.commit()
            logger.info(f"Created playlist: {name}")
            return cursor.lastrowid
    
    def add_to_playlist(self, playlist_id: int, audio_file_id: int):
        """
        プレイリストにアイテムを追加
        
        Args:
            playlist_id: プレイリストID
            audio_file_id: 音楽ファイルID
        """
        with self.get_connection() as conn:
            # 現在の最大positionを取得
            cursor = conn.execute(
                "SELECT MAX(position) as max_pos FROM playlist_items WHERE playlist_id = ?",
                (playlist_id,)
            )
            row = cursor.fetchone()
            next_position = (row['max_pos'] or 0) + 1
            
            conn.execute(
                "INSERT OR IGNORE INTO playlist_items (playlist_id, audio_file_id, position) VALUES (?, ?, ?)",
                (playlist_id, audio_file_id, next_position)
            )
            conn.commit()
            logger.debug(f"Added audio {audio_file_id} to playlist {playlist_id}")

    def add_to_playlist_many(self, playlist_id: int, audio_file_ids: List[int]):
        """
        プレイリストに複数のアイテムを一括追加
        
        Args:
            playlist_id: プレイリストID
            audio_file_ids: 音楽ファイルIDのリスト
        """
        if not audio_file_ids:
            return
            
        with self.get_connection() as conn:
            # 現在の最大positionを取得
            cursor = conn.execute(
                "SELECT MAX(position) as max_pos FROM playlist_items WHERE playlist_id = ?",
                (playlist_id,)
            )
            row = cursor.fetchone()
            start_position = (row['max_pos'] or 0) + 1
            
            # データ作成
            data = []
            for i, file_id in enumerate(audio_file_ids):
                data.append((playlist_id, file_id, start_position + i))
            
            conn.executemany(
                "INSERT OR IGNORE INTO playlist_items (playlist_id, audio_file_id, position) VALUES (?, ?, ?)",
                data
            )
            conn.commit()
            logger.info(f"Added {len(audio_file_ids)} items to playlist {playlist_id}")

    def remove_from_playlist(self, playlist_id: int, audio_file_id: int):
        """
        プレイリストからアイテムを削除
        
        Args:
            playlist_id: プレイリストID
            audio_file_id: 音楽ファイルID
        """
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM playlist_items WHERE playlist_id = ? AND audio_file_id = ?",
                (playlist_id, audio_file_id)
            )
            conn.commit()
            logger.info(f"Removed audio {audio_file_id} from playlist {playlist_id}")

    def update_playlist_item_position(self, playlist_id: int, audio_file_id: int, new_position: int):
        """
        プレイリスト内のアイテム順序を更新
        
        Args:
            playlist_id: プレイリストID
            audio_file_id: 音楽ファイルID
            new_position: 新しい順序
        """
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND audio_file_id = ?",
                (new_position, playlist_id, audio_file_id)
            )
            conn.commit()
            logger.debug(f"Updated position for audio {audio_file_id} in playlist {playlist_id} to {new_position}")
    
    # ==================== キャッシュ操作（廃止） ====================
    # キャッシュテーブルは廃止されました。
    # 互換性のためにメソッドを残す場合はここに記述しますが、
    # 今回は完全に削除します。
