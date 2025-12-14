import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from backend.core.syncer import SyncService
from backend.db.models import Track, Setting, Playlist
from sqlalchemy.future import select

# Helper
async def create_track(db, file_path, relative_path, sync=True, file_name="file.mp3"):
    t = Track(file_path=file_path, relative_path=relative_path, file_name=file_name, sync=sync)
    db.add(t)
    await db.commit()
    return t

@pytest.mark.asyncio
async def test_syncer_adb_integration(temp_db):
    """Test scenario 1: ADB Sync Integration (Mocked)"""
    # Setup settings
    db = temp_db
    db.add(Setting(key="sync_mode", value="adb"))
    db.add(Setting(key="sync_dest", value="/sdcard/Music"))
    await db.commit()
    
    # Setup Data
    await create_track(db, "/local/song1.mp3", "/Artist/Album/song1.mp3")
    await create_track(db, "/local/song2.mp3", "/Artist/Album/song2.mp3", sync=False) # Should skip
    
    # Mock AsyncSessionLocal to use temp_db
    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None
    
    # Mock subprocess.run for ADB calls
    # We also need to mock ls_remote first call to return empty (fresh sync)
    # The syncer runs in run_in_threadpool, so we need to bridge that.
    
    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("subprocess.run") as mock_run:
        
        # Setup mock responses
        # ls_remote returns empty -> FileNotFoundError or empty list? 
        # Code: if returncode != 0 or ... raise FileNotFoundError
        # Or returns list.
        # Let's say ls returns empty string (no files)
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        
        await SyncService.run_sync()
        
        # Verifications
        # 1. Check ls command
        # First call is ls for root
        args0 = mock_run.call_args_list[0][0][0]
        assert "adb shell ls" in args0
        
        # 2. Check push commands
        # song1 should be pushed
        push_calls = [c for c in mock_run.call_args_list if "push" in c[0][0]]
        assert len(push_calls) == 1
        cmd = push_calls[0][0][0]
        # Strict validation of command structure
        expected_cmd = ["adb", "push", "/local/song1.mp3", "/sdcard/Music/Artist/Album/song1.mp3"]
        assert cmd == expected_cmd, f"Expected {expected_cmd}, got {cmd}"
        
        # 3. Validation: song2 should NOT be pushed
        song2_pushes = [c for c in push_calls if "song2.mp3" in c[0][0][2]]
        assert len(song2_pushes) == 0

@pytest.mark.asyncio
async def test_syncer_rsync_integration(temp_db):
    """Test scenario 2: Rsync Sync Integration (Mocked)"""
    db = temp_db
    db.add(Setting(key="sync_mode", value="rsync"))
    db.add(Setting(key="sync_dest", value="/remote/music"))
    db.add(Setting(key="rsync_host", value="192.168.1.100"))
    db.add(Setting(key="rsync_user", value="user"))
    db.add(Setting(key="rsync_port", value="2222"))
    db.add(Setting(key="scan_paths", value='["/local/music"]'))
    await db.commit()
    
    await create_track(db, "/local/music/Artist/song1.mp3", "/Artist/song1.mp3")

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run") as mock_run: # for playlist cp
         
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        
        await SyncService.run_sync()
        
        # Verify Rsync Command
        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]
        
        # Order matters for rsync flags generally, though python list equality is strict order.
        # Construct expected parts strictly.
        # cmd=['rsync', '-avz', '--delete-excluded', '--include-from', '/tmp/tmp...', '--exclude=*', '/local/music', '-e', 'ssh -p 2222', 'user@192.168.1.100:/remote/music']
        
        assert cmd[0] == "rsync"
        assert cmd[1] == "-avz"
        assert cmd[2] == "--delete-excluded"
        assert cmd[3] == "--include-from"
        # cmd[4] is temp file path, verify it exists/starts with /tmp
        assert "tmp" in cmd[4] 
        assert cmd[5] == "--exclude=*"
        
        # Sources come next
        assert cmd[6] == "/local/music"
        
        # Remote shell options
        assert cmd[7] == "-e"
        assert cmd[8] == "ssh -p 2222"
        
        # Destination
        assert cmd[9] == "user@192.168.1.100:/remote/music"

@pytest.mark.asyncio
async def test_syncer_ftp_integration(temp_db):
    """Test scenario 3: FTP Sync Integration (Mocked)"""
    db = temp_db
    db.add(Setting(key="sync_mode", value="ftp"))
    db.add(Setting(key="ftp_host", value="localhost"))
    db.add(Setting(key="ftp_port", value="21"))
    db.add(Setting(key="sync_dest", value="/")) # FTP root
    await db.commit()
    
    await create_track(db, "/local/song1.mp3", "/song1.mp3")

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("ftplib.FTP") as MockFTP, \
         patch("builtins.open", mock_open(read_data=b"data")):
         
         ftp_instance = MockFTP.return_value
         # Mock mlsd to return empty (no existing files), so it triggers upload
         ftp_instance.mlsd.return_value = []
         
         await SyncService.run_sync()
         
         # Verify connect
         ftp_instance.connect.assert_called_with(host="localhost", port=21)
         
         # Verify upload
         # storbinary call
         args_list = ftp_instance.storbinary.call_args_list
         assert len(args_list) >= 1
         # Ensure expected command is exact
         cmd = args_list[0][0][0] 
         assert cmd == "STOR song1.mp3"

@pytest.mark.asyncio
async def test_syncer_rsync_host_only(temp_db):
    """Test scenario 2-A: Rsync Remote (Host only)"""
    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    db = temp_db
    db.add(Setting(key="sync_mode", value="rsync"))
    db.add(Setting(key="sync_dest", value="/remote/music"))
    db.add(Setting(key="rsync_host", value="10.0.0.1"))
    db.add(Setting(key="rsync_port", value="22"))
    db.add(Setting(key="scan_paths", value='["/source"]'))
    await db.commit()
    
    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run"):
         
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        
        await SyncService.run_sync()
        
        cmd = mock_popen.call_args[0][0]
        # Validations strict
        # cmd should look like: [rsync, -avz, ..., /source, -e, ssh -p 22, 10.0.0.1:/remote/music]
        # So last 3 elements are fixed structure
        assert cmd[-3] == "-e"
        assert cmd[-2] == "ssh -p 22"
        assert cmd[-1] == "10.0.0.1:/remote/music"

@pytest.mark.asyncio
async def test_syncer_rsync_local(temp_db):
    """Test scenario 2-B: Rsync Local (No Host)"""
    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    db = temp_db
    db.add(Setting(key="sync_mode", value="rsync"))
    db.add(Setting(key="sync_dest", value="/local/backup"))
    # No rsync_host
    db.add(Setting(key="scan_paths", value='["/source"]'))
    await db.commit()
    
    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run"):
         
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        
        await SyncService.run_sync()
        
        cmd = mock_popen.call_args[0][0]
        
        # Validations
        # Should NOT have ssh
        assert "-e" not in cmd
        assert not any("ssh" in c for c in cmd)
        # Dest is just path and is last argument
        assert cmd[-1] == "/local/backup"

@pytest.mark.asyncio
async def test_syncer_rsync_multi_path(temp_db):
    """Test scenario 2-C: Rsync Multiple Sources"""
    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = temp_db
    mock_session_cls.__aexit__.return_value = None

    db = temp_db
    db.add(Setting(key="sync_mode", value="rsync"))
    db.add(Setting(key="sync_dest", value="/remote"))
    db.add(Setting(key="rsync_host", value="host"))
    # Multiple paths
    db.add(Setting(key="scan_paths", value='["/src1", "/src2"]'))
    await db.commit()
    
    with patch("backend.core.syncer.AsyncSessionLocal", return_value=mock_session_cls), \
         patch("backend.core.syncer.run_in_threadpool", side_effect=lambda f, *args: f(*args)), \
         patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run"):
         
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.stdout = []
        
        await SyncService.run_sync()
        
        cmd = mock_popen.call_args[0][0]
        
        # Validations
        assert "/src1" in cmd
        assert "/src2" in cmd

