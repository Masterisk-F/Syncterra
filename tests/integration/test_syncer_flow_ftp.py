import os
import shutil
import tempfile
import threading
import time
from unittest.mock import patch

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from backend.core.syncer import SyncService
from backend.db.models import Track

# Integration Test: FTP Syncer Flow
# 目的: SyncServiceを使って、実際のFTPサーバーへの転送フローを検証する。


class QuietFTPHandler(FTPHandler):
    """ログ出力を抑制するFTPハンドラ"""

    def log(self, msg, *args, **kwargs):
        pass

    def logline(self, msg, *args, **kwargs):
        pass

    def logerror(self, msg, *args, **kwargs):
        pass


@pytest.fixture
def ftp_server():
    """
    一時的なFTPサーバーを別スレッドで起動するFixture。
    戻り値として (server_root, ftp_port, ftp_user, ftp_pass) を返す。
    """
    ftp_user = "testuser"
    ftp_password = "password"

    # サーバーのルートディレクトリ
    server_root = tempfile.mkdtemp()

    authorizer = DummyAuthorizer()
    authorizer.add_user(ftp_user, ftp_password, server_root, perm="elradfmwMT")

    handler = QuietFTPHandler
    handler.authorizer = authorizer

    # ポート0で動的割り当て
    server = FTPServer(("127.0.0.1", 0), handler)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # 起動待機
    time.sleep(0.5)

    actual_port = server.socket.getsockname()[1]

    yield server_root, actual_port, ftp_user, ftp_password

    # Teardown
    server.close_all()
    # サーバーディレクトリの削除
    shutil.rmtree(server_root)
    # スレッドの終了待機
    server_thread.join(timeout=2.0)


async def create_track(db, file_path, relative_path, sync=True, file_name="file.mp3"):
    """テスト用トラック作成ヘルパー (SyncServiceで読み込まれる用)"""
    t = Track(
        file_path=file_path,
        relative_path=relative_path,  # DB上の相対パス
        file_name=file_name,
        sync=sync,
    )
    db.add(t)
    await db.commit()
    return t


@pytest.mark.asyncio
async def test_syncer_flow_ftp(
    temp_db, temp_fs, create_settings, patch_db_session, ftp_server
):
    """
    [Syncer] FTP同期フロー

    条件:
    1. 同期モードが 'ftp'
    2. ローカルにファイルが存在し、DBに登録されている
    3. FTPサーバーが稼働中

    期待値:
    1. SyncService.run_sync() がエラーなく完了すること
    2. FTPサーバーのルートディレクトリに、ディレクトリ構造が維持されてファイルが転送されること
    3. 同期対象外(sync=False)のファイルは転送されないこと
    """
    server_root, ftp_port, ftp_user, ftp_pass = ftp_server

    # 1. 設定
    await create_settings(
        sync_mode="ftp",
        sync_dest="/",  # FTPルート
        ftp_host="127.0.0.1",
        ftp_port=ftp_port,
        ftp_user=ftp_user,
        ftp_pass=ftp_pass,
        target_exts="mp3",
    )

    # 2. データ準備
    # temp_fs上に実際のファイルが存在する必要がある (FTPは open(path) するため)
    # temp_fs fixture は既にいくつかのファイルを作っている:
    # - Artist1/Album1/song1.mp3
    # - Artist2/song3.mp3

    # DBにレコードを作成 (temp_fsのパスと合わせる)
    # create_trackのパスは temp_fs ベースの絶対パスであること
    song1_path = os.path.join(temp_fs, "Artist1", "Album1", "song1.mp3")
    song2_path = os.path.join(temp_fs, "Artist1", "Album1", "song2.mp3")

    # song1: Sync=True
    await create_track(
        temp_db,
        file_path=song1_path,
        relative_path="Artist1/Album1/song1.mp3",
        sync=True,
        file_name="song1.mp3",
    )

    # song2: Sync=False
    await create_track(
        temp_db,
        file_path=song2_path,
        relative_path="Artist1/Album1/song2.mp3",
        sync=False,  # 同期しない
        file_name="song2.mp3",
    )

    # 3. 実行
    # run_in_threadpool をバイパスして同期実行させる
    with patch(
        "backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)
    ):
        await SyncService.run_sync()

    # 4. 検証
    # FTPサーバー側のファイル確認

    # 期待されるパス: <server_root>/Artist1/Album1/song1.mp3
    dest_path_song1 = os.path.join(server_root, "Artist1", "Album1", "song1.mp3")
    assert os.path.exists(dest_path_song1), (
        "song1.mp3 がFTPサーバーに転送されていること"
    )

    # Sync=False の確認
    dest_path_song2 = os.path.join(server_root, "Artist1", "Album1", "song2.mp3")
    assert not os.path.exists(dest_path_song2), (
        "song2.mp3 (sync=False) は転送されていないこと"
    )

    # プレイリストファイルの確認（空でも作成される仕様）
    # M3Uファイル名は実装依存だが、デフォルトでプレイリストオブジェクトがなければ作成されないかも？
    # 今回はトラック転送が主眼なので割愛、あるいは必要なら追加
