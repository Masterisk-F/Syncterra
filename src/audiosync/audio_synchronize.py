"""
AudioSync 同期機能

既存のaudio_synchronizer.pyとrsync_audio_synchronizer.pyを活用し、DB経由で同期を実行する
"""

from typing import Callable, Dict, Any
from database import Database
from logger import setup_logger

logger = setup_logger(__name__)


def synchronize_files(
    db: Database,
    progress_callback: Callable[[int, int, str], None] = None,
    log_callback: Callable[[str], None] = None
) -> Dict[str, Any]:
    """
    音楽ファイルを同期
    
    Args:
        db: Databaseインスタンス
        progress_callback: 進捗コールバック関数 (current, total, message)
        log_callback: ログ出力コールバック関数 (message)
    
    Returns:
        結果の辞書
    """
    # 設定を取得
    settings = db.get_all_settings()
    sync_method = settings.get('sync_method', 'ftp')
    
    if sync_method == 'ftp':
        return _synchronize_ftp(db, settings, progress_callback, log_callback)
    elif sync_method == 'rsync':
        return _synchronize_rsync(db, settings, progress_callback, log_callback)
    else:
        raise ValueError(f"Unknown sync method: {sync_method}")


def _synchronize_ftp(
    db: Database,
    settings: Dict[str, str],
    progress_callback: Callable[[int, int, str], None] = None,
    log_callback: Callable[[str], None] = None
) -> Dict[str, Any]:
    """FTP経由で同期"""
    from audio_synchronizer import FtpAudioSynchronizer
    
    # FTP設定を取得
    ftp_host = settings.get('ftp_host', '192.168.10.3')
    ftp_port = int(settings.get('ftp_port', '2221'))
    ftp_user = settings.get('ftp_user', 'francis')
    ftp_pass = settings.get('ftp_pass', 'francis')
    
    if progress_callback:
        progress_callback(0, 100, "FTP接続中...")
    
    # DB経由のラッパーオブジェクトを作成
    class DbAudioSyncDataWrapper:
        """DatabaseをAudioSyncDataのように見せるラッパー"""
        def __init__(self, database: Database):
            self.db = database
            settings = database.get_all_settings()
            self._include_dir = [d.strip() for d in settings.get('sync_dir_from', '').split(',') if d.strip()]
            # FTPの場合はftp_dirを使用
            self._sync_dir_to = [d.strip() for d in settings.get('ftp_dir', '/').split(',') if d.strip()]
            self._include_ext = [ext.strip() for ext in settings.get('include_ext', 'mp3,m4a,mp4').split(',') if ext.strip()]
        
        @property
        def include_dir(self):
            return iter(self._include_dir)
        
        @property
        def include_extention(self):
            return iter(['.' + ext for ext in self._include_ext])
        
        @property
        def dir_to_synchronize(self):
            return self._sync_dir_to
        
        @property
        def sheet_Albums(self):
            """Albums相当（同期対象のファイル）"""
            files = self.db.get_all_audio_files(sync_only=True)
            return [_file_to_audio_obj(f) for f in files]
        
        @property
        def sheet_Not_in_Albums(self):
            """Not in Albums相当（空リスト）"""
            return []
        
        @property
        def sheets_playlist(self):
            """プレイリスト（未実装）"""
            return {}
    
    def _file_to_audio_obj(file_dict):
        """DBのファイル辞書をAudioオブジェクト風に変換"""
        class AudioObj:
            def __init__(self, d):
                self.sync = "○" if d.get('sync') else ""
                self.filepath_from = d.get('filepath_from', '')
                self.filepath_to_relative = d.get('filepath_to_relative', '')
                self.title = d.get('title', '')
                self.artist = d.get('artist', '')
        return AudioObj(file_dict)
    
    # ラッパーを作成
    wrapper = DbAudioSyncDataWrapper(db)
    
    # FTP Synchronizerを作成
    try:
        synchronizer = FtpAudioSynchronizer(
            wrapper,
            ip_addr=ftp_host,
            port=ftp_port,
            user=ftp_user,
            passwd=ftp_pass
        )
        
        if progress_callback:
            progress_callback(50, 100, "同期中...")
        
        # 同期実行
        synchronizer.synchronize(log_callback=log_callback)
        
        if progress_callback:
            progress_callback(100, 100, "完了")
        
        return {'status': 'success', 'method': 'ftp'}
    
    except Exception as e:
        logger.error(f"FTP sync failed: {e}", exc_info=True)
        raise


def _synchronize_rsync(
    db: Database,
    settings: Dict[str, str],
    progress_callback: Callable[[int, int, str], None] = None,
    log_callback: Callable[[str], None] = None
) -> Dict[str, Any]:
    """Rsync経由で同期"""
    from rsync_audio_synchronizer import RsyncAudioSynchronizer
    
    # Rsync設定を取得
    rsync_host = settings.get('rsync_host', '')
    rsync_user = settings.get('rsync_user', '')
    rsync_port = int(settings.get('rsync_port', '22'))
    
    if not rsync_host:
        raise ValueError("Rsyncホストが設定されていません")
    
    if progress_callback:
        progress_callback(0, 100, "Rsync準備中...")
    
    # DB経由のラッパーオブジェクトを作成（FTPと同じ）
    class DbAudioSyncDataWrapper:
        def __init__(self, database: Database):
            self.db = database
            settings = database.get_all_settings()
            self._include_dir = [d.strip() for d in settings.get('sync_dir_from', '').split(',') if d.strip()]
            # Rsyncの場合はrsync_dirを使用
            self._sync_dir_to = [d.strip() for d in settings.get('rsync_dir', '').split(',') if d.strip()]
            self._include_ext = [ext.strip() for ext in settings.get('include_ext', 'mp3,m4a,mp4').split(',') if ext.strip()]
        
        @property
        def include_dir(self):
            return iter(self._include_dir)
        
        @property
        def include_extention(self):
            return iter(['.' + ext for ext in self._include_ext])
        
        @property
        def dir_to_synchronize(self):
            return self._sync_dir_to
        
        @property
        def sheet_Albums(self):
            files = self.db.get_all_audio_files(sync_only=True)
            return [_file_to_audio_obj(f) for f in files]
        
        @property
        def sheet_Not_in_Albums(self):
            return []
        
        @property
        def sheets_playlist(self):
            return {}
    
    def _file_to_audio_obj(file_dict):
        class AudioObj:
            def __init__(self, d):
                self.sync = "○" if d.get('sync') else ""
                self.filepath_from = d.get('filepath_from', '')
                self.filepath_to_relative = d.get('filepath_to_relative', '')
        return AudioObj(file_dict)
    
    wrapper = DbAudioSyncDataWrapper(db)
    
    # Rsync Synchronizerを作成
    try:
        synchronizer = RsyncAudioSynchronizer(
            wrapper,
            remote_os_sep='/',
            ip_addr=rsync_host,
            port=rsync_port,
            user=rsync_user if rsync_user else None
        )
        
        if progress_callback:
            progress_callback(50, 100, "同期中...")
        
        # 同期実行
        synchronizer.synchronize(log_callback=log_callback)
        
        if progress_callback:
            progress_callback(100, 100, "完了")
        
        return {'status': 'success', 'method': 'rsync'}
    
    except Exception as e:
        logger.error(f"Rsync sync failed: {e}", exc_info=True)
        raise
