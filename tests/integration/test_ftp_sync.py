import os
import shutil
import tempfile
import threading
import time
import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from backend.core.syncer import FtpSynchronizer
from backend.db.models import Track

# テスト中のログ出力を抑制するためのカスタムハンドラ
class QuietFTPHandler(FTPHandler):
    def log(self, msg, *args, **kwargs):
        pass
    def logline(self, msg, *args, **kwargs):
        pass
    def logerror(self, msg, *args, **kwargs):
        pass

class TestFtpSynchronizer:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # セットアップ
        self.ftp_user = "user"
        self.ftp_password = "password"
        self.ftp_port = 0 # 0を指定して動的ポート割り当て
        
        # サーバーのルートディレクトリとクライアントファイル用のディレクトリ作成
        self.server_root = tempfile.mkdtemp()
        self.client_root = tempfile.mkdtemp()
        
        # 別スレッドでFTPサーバーを起動
        authorizer = DummyAuthorizer()
        authorizer.add_user(self.ftp_user, self.ftp_password, self.server_root, perm="elradfmwMT")
        
        handler = QuietFTPHandler
        handler.authorizer = authorizer
        
        self.server = FTPServer(("127.0.0.1", self.ftp_port), handler)
        
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # サーバー起動待機
        time.sleep(0.5)
        
        # 実際に割り当てられたポートを取得
        self.actual_port = self.server.socket.getsockname()[1]
        
        # FtpSynchronizerの初期化
        self.settings = {
            "ftp_host": "127.0.0.1",
            "ftp_port": self.actual_port,
            "ftp_user": self.ftp_user,
            "ftp_pass": self.ftp_password,
            "sync_dest": "/",  # FTPサーバルート
            "target_exts": "mp3",
            "sync_mode": "ftp"
        }
        
        # ダミーのトラックとプレイリスト
        self.tracks = []
        self.playlists = []
        
        self.synchronizer = FtpSynchronizer(
            tracks=self.tracks,
            playlists=self.playlists,
            settings=self.settings,
            log_callback=lambda msg: None # print(f"LOG: {msg}")
        )
        
        yield
        
        # ティアダウン
        try:
            self.synchronizer.ftp.quit()
        except:
            pass
            
        self.server.close_all()
        # サーバーが綺麗に停止しない場合のハング防止のためjoinは省略する場合がありますが、
        # close_allで基本的には停止します。
        # self.server_thread.join(timeout=2)
        
        shutil.rmtree(self.server_root)
        shutil.rmtree(self.client_root)

    def create_dummy_file(self, filename, content="test content"):
        filepath = os.path.join(self.client_root, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return filepath

    def test_cp_upload(self):
        """
        ローカルファイルがFTPサーバーへ正しくアップロードされることを検証する。
        """
        # ローカルファイル作成
        filename = "test_song.mp3"
        local_path = self.create_dummy_file(filename)
        
        # アップロード実行
        self.synchronizer.cp(local_path, filename)
        
        # サーバー側でファイル確認
        server_path = os.path.join(self.server_root, filename)
        assert os.path.exists(server_path)
        with open(server_path, "r") as f:
            assert f.read() == "test content"

    def test_mkdir_p_remote(self):
        """
        リモートサーバー上で再帰的にディレクトリが作成されることを検証する。
        """
        # ディレクトリ構造作成
        dir_path = "music/artist/album"
        self.synchronizer.mkdir_p_remote(dir_path)
        
        # サーバー側でディレクトリ確認
        assert os.path.exists(os.path.join(self.server_root, "music"))
        assert os.path.exists(os.path.join(self.server_root, "music", "artist"))
        assert os.path.exists(os.path.join(self.server_root, "music", "artist", "album"))

    def test_rm_remote(self):
        """
        リモートサーバー上のファイルが削除されることを検証する。
        """
        # サーバー上に手動でファイル作成
        filename = "to_delete.mp3"
        server_path = os.path.join(self.server_root, filename)
        with open(server_path, "w") as f:
            f.write("content")
            
        # 削除実行
        self.synchronizer.rm_remote(filename)
        
        # ファイルが存在しないことを確認
        assert not os.path.exists(server_path)

    def test_ls_remote(self):
        """
        リモートサーバー上のファイル一覧が正しく取得できることを検証する。
        """
        # サーバー上にファイル作成
        os.makedirs(os.path.join(self.server_root, "subdir"))
        with open(os.path.join(self.server_root, "file1.mp3"), "w") as f: f.write("1")
        with open(os.path.join(self.server_root, "subdir", "file2.mp3"), "w") as f: f.write("2")
        
        # ルートディレクトリの一覧
        items_root = self.synchronizer.ls_remote("/")
        # 結果は (name, is_dir) のリスト
        names_root = [i[0] for i in items_root]
        assert "file1.mp3" in names_root
        assert "subdir" in names_root
        
        # サブディレクトリの一覧
        items_sub = self.synchronizer.ls_remote("subdir")
        names_sub = [i[0] for i in items_sub]
        assert "file2.mp3" in names_sub

    def test_synchronize_flow(self):
        """
        synchronizeメソッド全体のフロー（差分検出、転送、プレイリスト作成）を検証する。
        """
        # 1. データセットアップ
        # 同期対象のローカルファイル
        filename = "My Song.mp3"
        relative_path = "Music/My Song.mp3"
        local_path = self.create_dummy_file(filename)
        
        track = Track(
            file_path=local_path,
            relative_path=relative_path, # DBは通常、相対パスを保持
            file_name=filename,
            title="My Song",
            sync=True
        )
        self.synchronizer.tracks = [track]
        
        # 2. 同期実行
        # ls_remote -> 差分チェック -> cp の順で実行される
        self.synchronizer.synchronize()
        
        # 3. サーバー上のファイル確認
        server_path = os.path.join(self.server_root, relative_path)
        assert os.path.exists(server_path)
        
        # 4. プレイリスト作成確認
        # プレイリストを追加して再度同期
        self.synchronizer.playlists = [
            {"name": "MyPlaylist", "content": "#EXTM3U\n..."}
        ]
        self.synchronizer.synchronize()
        
        playlist_path = os.path.join(self.server_root, "MyPlaylist.m3u")
        assert os.path.exists(playlist_path)
