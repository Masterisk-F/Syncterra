import pytest
from unittest.mock import MagicMock, patch, mock_open, call
from backend.core.syncer import SyncService, AdbSynchronizer, RsyncSynchronizer, FtpSynchronizer, make_m3u8
from backend.db.models import Track, Setting, Playlist, PlaylistTrack
from backend.db.database import init_db, AsyncSessionLocal
import pytest_asyncio
from sqlalchemy import delete
import os

# Helper to clear DB
@pytest_asyncio.fixture
async def db_session():
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PlaylistTrack))
        await session.execute(delete(Playlist))
        await session.execute(delete(Setting))
        await session.execute(delete(Track))
        await session.commit()
        yield session

def test_make_m3u8():
    t1 = Track(file_name="song1.mp3", title="Song 1", relative_path="/Album/song1.mp3")
    t2 = Track(file_name="song2.mp3", title=None, relative_path="/Album/song2.mp3") # No title
    
    # Test with default settings
    content = make_m3u8([t1, t2], remote_sep="/")
    assert "#EXTM3U" in content
    assert "#EXTINF:-1,Song 1" in content
    assert "Album/song1.mp3" in content # Leading slash removed
    assert "#EXTINF:-1,song2.mp3" in content # Fallback to filename
    assert "Album/song2.mp3" in content

    # Test with Windows separator replacement
    t3 = Track(file_name="win.mp3", title="Win", relative_path=r"\Music\win.mp3")
    content = make_m3u8([t3], remote_sep="/")
    assert "Music/win.mp3" in content

@pytest.mark.asyncio
async def test_sync_service_run_adb(db_session):
    # Setup DB
    db_session.add(Setting(key="sync_mode", value="adb"))
    db_session.add(Setting(key="sync_dest", value="/sdcard/Music"))
    t1 = Track(file_path="/local/song1.mp3", relative_path="/song1.mp3", file_name="song1.mp3", sync=True)
    db_session.add(t1)
    await db_session.commit()

    # Mock running in threadpool to execute immediately
    with patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f: f()) as mock_thread, \
         patch("backend.core.syncer.AdbSynchronizer") as MockAdb:
        
        mock_instance = MockAdb.return_value
        
        await SyncService.run_sync()
        
        MockAdb.assert_called_once()
        mock_instance.synchronize.assert_called_once()
        
        # Verify args passed to constructor
        args, _ = MockAdb.call_args
        tracks = args[0]
        assert len(tracks) == 1
        assert tracks[0].file_name == "song1.mp3"

@pytest.mark.asyncio
async def test_sync_service_playlists(db_session):
    # Setup DB with Playlists
    p1 = Playlist(name="MyPlaylist", id=1)
    db_session.add(p1)
    t1 = Track(file_path="/l/s1.mp3", relative_path="/s1.mp3", file_name="s1.mp3", id=1, sync=True)
    t2 = Track(file_path="/l/s2.mp3", relative_path="/s2.mp3", file_name="s2.mp3", id=2, sync=True)
    db_session.add(t1)
    db_session.add(t2)
    db_session.add(PlaylistTrack(playlist_id=1, track_id=1, order=2))
    db_session.add(PlaylistTrack(playlist_id=1, track_id=2, order=1))
    await db_session.commit()

    with patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f: f()) as mock_thread, \
         patch("backend.core.syncer.AdbSynchronizer") as MockAdb:
        
        await SyncService.run_sync()
        
        args, _ = MockAdb.call_args
        playlists = args[1] # 2nd arg
        
        assert len(playlists) == 1
        assert playlists[0]["name"] == "MyPlaylist"
        content = playlists[0]["content"]
        # Verify order: s2 (order 1) then s1 (order 2)
        pos_s1 = content.find("s1.mp3")
        pos_s2 = content.find("s2.mp3")
        assert pos_s2 < pos_s1

# Synchronizer Logic Tests
@patch("subprocess.run")
def test_adb_synchronizer(mock_run):
    settings = {"sync_dest": "/data/music"}
    # Mock return for ls_remote
    # Remove directory to avoid infinite recursion in traverse_remote (since mock returns same thing for all calls)
    mock_run.return_value.stdout = "existing.mp3\n"
    mock_run.return_value.returncode = 0
    
    t1 = Track(file_path="/local/new.mp3", relative_path="/new.mp3", file_name="new.mp3", sync=True)
    t2 = Track(file_path="/local/existing.mp3", relative_path="/existing.mp3", file_name="existing.mp3", sync=True)
    
    sync = AdbSynchronizer([t1, t2], [], settings)
    sync.synchronize()
    
    # Verify push commands
    # t1 should be pushed
    # t2 should NOT be pushed (exists in ls_remote)
    
    # We expect push for new.mp3
    push_calls = [c for c in mock_run.call_args_list if "push" in c[0][0]]
    assert len(push_calls) == 1
    cmd = push_calls[0][0][0]
    assert cmd[2] == "/local/new.mp3"
    assert cmd[3] == "/data/music/new.mp3"

@patch("subprocess.run")
def test_rsync_synchronizer(mock_run):
    settings = {
        "rsync_user": "u", "rsync_host": "h", "rsync_port": "2222", "sync_dest": "/remote/path",
        "scan_paths": '["/source/root"]'
    }
    t1 = Track(file_path="/source/root/s1.mp3", relative_path="/s1.mp3", file_name="s1.mp3", sync=True)
    
    # プレイリストを追加
    playlists = [{"name": "TestPlaylist", "content": "#EXTM3U\n\ns1.mp3\n"}]
    
    sync = RsyncSynchronizer([t1], playlists, settings)
    
    # Mock mkstemp for include file
    with patch("tempfile.mkstemp", return_value=(1, "/tmp/tmpxxx")), \
         patch("os.close"), \
         patch("os.remove"), \
         patch("builtins.open", mock_open()) as mock_file, \
         patch("subprocess.Popen") as mock_popen:
        
        mock_popen.return_value.stdout = []
        mock_popen.return_value.returncode = 0
        
        sync.synchronize()
        
        # Verify rsync call for main sync
        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "rsync" in cmd
        assert "-e" in cmd
        assert "ssh -p 2222" in cmd
        assert "u@h:/remote/path" in cmd
        
        # Verify playlist file transfer (cp method via subprocess.run)
        # プレイリスト転送は put_playlist_file -> cp -> subprocess.run
        playlist_calls = [c for c in mock_run.call_args_list if len(c[0]) > 0 and "rsync" in c[0][0]]
        assert len(playlist_calls) >= 1, "プレイリストファイルがrsyncで転送されていません"
        # 最後の呼び出しにTestPlaylist.m3uが含まれているか確認
        last_call_cmd = playlist_calls[-1][0][0]
        assert "TestPlaylist.m3u" in " ".join(last_call_cmd), "プレイリスト名がコマンドに含まれていません"

@patch("ftplib.FTP")
def test_ftp_synchronizer(MockFTP):
    settings = {"ftp_host": "1.2.3.4", "target_exts": "mp3"}
    mock_ftp = MockFTP.return_value
    
    # Mock ls_remote (mlsd)
    # リモートに2つのファイルが存在: "existing.mp3" (同期リストにある), "old.mp3" (削除対象)
    mock_ftp.mlsd.return_value = [
        ("existing.mp3", {"type": "file"}),
        ("old.mp3", {"type": "file"})
    ]
    mock_ftp.cwd.return_value = None  # cwd成功を模擬
    
    t1 = Track(file_path="/local/new.mp3", relative_path="/new.mp3", file_name="new.mp3", sync=True)
    t2 = Track(file_path="/local/existing.mp3", relative_path="/existing.mp3", file_name="existing.mp3", sync=True)
    
    # プレイリストを追加
    playlists = [{"name": "MyPlaylist", "content": "#EXTM3U\n\nnew.mp3\nexisting.mp3\n"}]
    
    sync = FtpSynchronizer([t1, t2], playlists, settings)
    
    with patch("builtins.open", mock_open(read_data=b"data")) as m_open:
        sync.synchronize()
        
        # 接続確認
        mock_ftp.connect.assert_called_with(host="1.2.3.4", port=2221)
        
        # 新規ファイル転送確認 (new.mp3)
        storbinary_calls = [c for c in mock_ftp.storbinary.call_args_list]
        file_calls = [c for c in storbinary_calls if "new.mp3" in c[0][0]]
        assert len(file_calls) >= 1, "new.mp3が転送されていません"
        
        # リモートファイル削除確認 (old.mp3)
        mock_ftp.delete.assert_called()
        delete_calls = [c[0][0] for c in mock_ftp.delete.call_args_list]
        assert "old.mp3" in delete_calls, "old.mp3が削除されていません"
        
        # プレイリスト転送確認 (MyPlaylist.m3u)
        playlist_calls = [c for c in storbinary_calls if "MyPlaylist.m3u" in c[0][0]]
        assert len(playlist_calls) >= 1, "プレイリストファイルが転送されていません"
