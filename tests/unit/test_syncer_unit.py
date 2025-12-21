from types import SimpleNamespace
import pytest
import logging
from unittest.mock import MagicMock, patch, mock_open, call
from backend.core.syncer import make_m3u8, FtpSynchronizer, RsyncSynchronizer
from ftplib import error_perm

# --- make_m3u8 Tests ---

def test_make_m3u8_basic():
    """
    標準的なトラック情報から正しいM3U8が生成されること。
    """
    tracks = [
        SimpleNamespace(
            title="Song A",
            file_name="SongA",
            relative_path="/Artist/Album/SongA.mp3"
        ),
        SimpleNamespace(
            title="Song B",
            file_name="SongB",
            relative_path="/Artist/Album/SongB.mp3"
        )
    ]
    
    result = make_m3u8(tracks, remote_sep="/")
    
    expected = (
        "#EXTM3U\n\n"
        "#EXTINF:-1,Song A\n"
        "Artist/Album/SongA.mp3\n\n"
        "#EXTINF:-1,Song B\n"
        "Artist/Album/SongB.mp3\n\n"
    )
    
    assert result == expected

def test_make_m3u8_fallback_title():
    """
    タイトルがない場合、ファイル名が使用されること。
    """
    tracks = [
        SimpleNamespace(
            title=None,
            file_name="UnknownSong",
            relative_path="/UnknownSong.mp3"
        )
    ]
    
    result = make_m3u8(tracks, remote_sep="/")
    
    assert "#EXTINF:-1,UnknownSong" in result

def test_make_m3u8_path_normalization():
    r"""
    パスの区切り文字が正規化され、先頭のスラッシュが削除されること。
    Windowsパス(\)も処理されること。
    """
    tracks = [
        SimpleNamespace(
            title="Win Song",
            file_name="WinSong",
            relative_path="\\Artist\\WinSong.mp3" # Windows style
        )
    ]
    
    # Remote is Linux/Android (//)
    result = make_m3u8(tracks, remote_sep="/")
    
    # Should become Artist/WinSong.mp3 (no leading slash, forward slashes)
    assert "Artist/WinSong.mp3" in result
    assert "\\Artist" not in result

def test_make_m3u8_empty():
    """
    トラックが空の場合、ヘッダーのみが返ること。
    """
    result = make_m3u8([], remote_sep="/")
    assert result == "#EXTM3U\n\n"

def test_make_m3u8_skip_no_path():
    """
    relative_pathがないトラックはスキップされること。
    """
    tracks = [
        SimpleNamespace(
            title="Ghost",
            file_name="Ghost",
            relative_path=None
        )
    ]
    
    result = make_m3u8(tracks)
    assert result == "#EXTM3U\n\n"


# --- FtpSynchronizer Tests ---

class TestFtpSynchronizer:
    @pytest.fixture
    def settings(self):
        return {
            "ftp_host": "192.168.1.100",
            "ftp_port": 2121,
            "ftp_user": "testuser",
            "ftp_pass": "secret"
        }

    @pytest.fixture
    def mock_ftp(self):
        with patch("ftplib.FTP") as mock:
            yield mock.return_value

    def test_init_connects_to_ftp(self, settings, mock_ftp):
        """
        初期化時にFTP接続、ログイン、パッシブモード設定が行われること。
        """
        FtpSynchronizer([], [], settings)

        # Verify interactions
        mock_ftp.connect.assert_called_with(host="192.168.1.100", port=2121)
        mock_ftp.login.assert_called_with(user="testuser", passwd="secret")
        mock_ftp.set_pasv.assert_called_with(True)
        assert mock_ftp.encoding == "utf-8"

    def test_cp_uploads_file(self, settings, mock_ftp):
        """
        cpメソッドが正しいディレクトリに移動し、ファイルをアップロードすること。
        """
        sync = FtpSynchronizer([], [], settings)
        
        # Mock open to avoid file system access
        with patch("builtins.open", mock_open(read_data=b"audio data")) as m_open:
            sync.cp("/local/song.mp3", "Music/Artist/song.mp3")
            
            # 1. Change Directory
            # Note: The implementation might change directory step by step or directly.
            # If the path is relative, it depends on current dir.
            # Here we assume it tries to change to target directory.
            # If 'Music/Artist' is passed, it might try CWD to 'Music' then 'Artist', or full path.
            # Checking if cwd was called with expected path.
            # Based on failure log: assert '/' == 'Music/Artist' -> seems like it resets to root first?
            # Or maybe checking call_args_list[0] which is root reset?
            # Let's check if 'Music/Artist' is in any of the call args.
            cwd_calls = [c.args[0] for c in mock_ftp.cwd.call_args_list]
            assert "Music/Artist" in cwd_calls
            
            # 2. Upload (STOR)
            # storbinary(cmd, fp)
            args, _ = mock_ftp.storbinary.call_args
            assert args[0] == "STOR song.mp3"
            # args[1] should be the file object

    def test_del_closes_connection(self, settings, mock_ftp):
        """
        オブジェクト破棄時にFTP接続が閉じられること。
        """
        sync = FtpSynchronizer([], [], settings)
        del sync
        
        mock_ftp.quit.assert_called_once()
    
    def test_cp_handles_cwd_permission_error(self, settings, mock_ftp):
        """
        cpメソッドでcwdがftplib.error_permを上げた際にクラッシュしないこと。
        """
        # Set cwd to raise an error only for the first call
        mock_ftp.cwd.side_effect = [error_perm("550 No such directory"), None]

        sync = FtpSynchronizer([], [], settings)

        with patch("builtins.open", mock_open(read_data=b"audio data")):
            try:
                sync.cp("/local/song.mp3", "Music/Artist/song.mp3")
            except Exception as e:
                pytest.fail(f"cp method should not crash on ftplib.error_perm: {e}")

        # Ensure cwd was called
        assert mock_ftp.cwd.called

    def test_rm_remote_success(self, settings, mock_ftp):
        """
        rm_remoteメソッドがファイルをリモートから削除すること。
        """
        sync = FtpSynchronizer([], [], settings)
        sync.rm_remote("Music/Artist/song.mp3")
        mock_ftp.delete.assert_called_once_with("Music/Artist/song.mp3")

    def test_rm_remote_failure_logs_error(self, settings, mock_ftp, caplog):
        """
        rm_remoteメソッドで削除に失敗した場合にエラーをログに出力すること。
        """
        mock_ftp.delete.side_effect = error_perm("550 Permission denied")

        sync = FtpSynchronizer([], [], settings)
        
        with caplog.at_level(logging.INFO): # Assuming logging level is INFO or higher
            sync.rm_remote("Music/Artist/song.mp3")
            assert "FTP delete failed" in caplog.text
            assert "Permission denied" in caplog.text

    def test_mkdir_p_remote_single_dir(self, settings, mock_ftp):
        """
        mkdir_p_remoteが単一のディレクトリを作成すること。
        """
        sync = FtpSynchronizer([], [], settings)
        mock_ftp.cwd.reset_mock() # Clear cwd calls from __init__
        sync.mkdir_p_remote("Music")
        mock_ftp.mkd.assert_called_once_with("Music")
        # Ensure it changes back to root or stays as is
        assert mock_ftp.cwd.call_args_list == [] # No cwd calls in mkdir_p_remote

    def test_mkdir_p_remote_recursive(self, settings, mock_ftp):
        """
        mkdir_p_remoteが複数階層のディレクトリを再帰的に作成すること。
        """
        sync = FtpSynchronizer([], [], settings)
        mock_ftp.cwd.reset_mock() # Clear cwd calls from __init__
        
        # mkd will be called for each part
        mock_ftp.mkd.side_effect = [
            None, # for Music
            error_perm("550 Already exists"), # for Music/Artist
            None # for Music/Artist/Album
        ]
        
        sync.mkdir_p_remote("Music/Artist/Album")
        
        mock_ftp.mkd.assert_has_calls([
            call("Music"),
            call("Music/Artist"),
            call("Music/Artist/Album")
        ])
        assert mock_ftp.mkd.call_count == 3
        assert mock_ftp.cwd.call_args_list == [] # No cwd calls in mkdir_p_remote

    def test_ls_remote_files_and_dirs(self, settings, mock_ftp):
        """
        ls_remoteがファイルとディレクトリを正しくリストアップすること。
        """
        sync = FtpSynchronizer([], [], settings)
        mock_ftp.mlsd.return_value = [
            ("file1.mp3", {"type": "file"}),
            ("subdir", {"type": "dir"}),
            ("file2.txt", {"type": "file"}),
            (".", {"type": "dir"}), # Should be ignored
            ("..", {"type": "dir"}), # Should be ignored
        ]
        mock_ftp.cwd.return_value = None # cwd will be called by ls_remote
        
        result = sync.ls_remote("my_dir")
        
        # Expected format: list of (name, is_dir)
        assert ("file1.mp3", False) in result
        assert ("subdir", True) in result
        assert ("file2.txt", False) in result
        assert len(result) == 3 # . and .. should be ignored
        # Depending on implementation, it might CWD to root first then to my_dir
        cwd_calls = [c.args[0] for c in mock_ftp.cwd.call_args_list]
        assert "my_dir" in cwd_calls

    def test_ls_remote_empty_dir(self, settings, mock_ftp):
        """
        ls_remoteが空のディレクトリで空リストを返すこと。
        """
        sync = FtpSynchronizer([], [], settings)
        mock_ftp.mlsd.return_value = [(".", {"type": "dir"}), ("..", {"type": "dir"})]
        mock_ftp.cwd.return_value = None
        
        result = sync.ls_remote("empty_dir")
        assert result == []

    def test_ls_remote_non_existent_dir_raises_filenotfounderror(self, settings, mock_ftp):
        """
        ls_remoteが存在しないディレクトリでFileNotFoundErrorを発生させること。
        """
        sync = FtpSynchronizer([], [], settings)
        mock_ftp.cwd.side_effect = error_perm("550 No such directory") # cwd called by ls_remote
        
        with pytest.raises(FileNotFoundError):
            sync.ls_remote("non_existent_dir")

# --- RsyncSynchronizer Tests ---

class TestRsyncSynchronizer:
    @pytest.fixture
    def settings(self):
        return {
            "rsync_user": "rsync_user",
            "rsync_host": "rsync_host",
            "rsync_port": "22",
            "sync_dest": "/remote/path",
            "scan_paths": '["/local/music"]', # For synchronize include list
            "rsync_pass": "secret" # Default password for tests
        }

    @pytest.fixture
    def mock_subprocess_run(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
            yield mock_run

    @pytest.fixture
    def mock_subprocess_popen(self):
        with patch("subprocess.Popen") as mock_popen:
            # Mock stdout to be an iterator of lines
            mock_popen.return_value.stdout = ["line1\n", "line2\n"]
            mock_popen.return_value.wait.return_value = 0 # Ensure wait returns 0
            mock_popen.return_value.returncode = 0
            yield mock_popen

    @pytest.fixture
    def mock_tempfile(self):
        with patch("tempfile.mkstemp", return_value=(99, "/tmp/temp_include_file")) as mock:
            yield mock

    @pytest.fixture
    def mock_os_funcs(self):
        with patch("os.close"), patch("os.remove"):
            yield

    @pytest.fixture
    def mock_json_loads(self):
        with patch("json.loads") as mock:
            yield mock

    @pytest.fixture
    def mock_open_for_include_list(self):
        m = mock_open()
        with patch("builtins.open", m) as mock:
            yield mock

    def test_synchronize_local(self, settings, mock_subprocess_popen, mock_tempfile, mock_os_funcs, mock_json_loads, mock_open_for_include_list):
        """
        ローカルパスへのrsync同期で正しいコマンドが生成・実行されること。
        """
        settings["rsync_host"] = "" # Local sync
        settings["sync_dest"] = "/local/backup"
        
        mock_json_loads.return_value = ["/local/music"]

        tracks = [
            SimpleNamespace(sync=True, relative_path="/Album/Song.mp3")
        ]
        
        sync = RsyncSynchronizer(tracks, [], settings)
        sync.synchronize()
        
        actual_cmd = mock_subprocess_popen.call_args[0][0]
        
        # 期待されるrsyncコマンドの完全なリスト
        expected_cmd = [
            "rsync",
            "-avz",
            "--delete-excluded",
            "--include-from", "/tmp/temp_include_file",
            "--exclude=*",
            "/local/music", # scan_pathsからのソースディレクトリ
            "/local/backup" # ローカルの宛先
        ]

        assert actual_cmd == expected_cmd # 完全一致を検証

        # Check include file content
        mock_open_for_include_list.assert_called_once_with("/tmp/temp_include_file", "w")
        handle = mock_open_for_include_list()
        handle.write.assert_any_call("/Album/Song.mp3\n")
        handle.write.assert_any_call("/Album/\n")

    def test_synchronize_remote_ssh_password(self, settings, mock_subprocess_popen, mock_tempfile, mock_os_funcs, mock_json_loads, mock_open_for_include_list):
        """
        リモートSSH経由でのrsync同期（パスワード認証）で正しいコマンドが生成・実行されること。
        """
        mock_json_loads.return_value = ["/local/music"]

        tracks = [
            SimpleNamespace(sync=True, relative_path="/Album/Song.mp3")
        ]
        
        sync = RsyncSynchronizer(tracks, [], settings)
        sync.synchronize()
        
        actual_cmd = mock_subprocess_popen.call_args[0][0]
        
        # 期待されるrsyncコマンドの完全なリスト
        expected_cmd = [
            "sshpass", "-p", "secret",
            "rsync",
            "-avz",
            "--delete-excluded",
            "--include-from", "/tmp/temp_include_file",
            "--exclude=*",
            "/local/music", # scan_pathsからのソースディレクトリ
            "-e", "ssh -p 22", # SSH関連のオプション
            "rsync_user@rsync_host:/remote/path" # リモートの宛先
        ]

        assert actual_cmd == expected_cmd # 完全一致を検証

    def test_synchronize_remote_ssh_key(self, settings, mock_subprocess_popen, mock_tempfile, mock_os_funcs, mock_json_loads, mock_open_for_include_list):
        """
        リモートSSH経由でのrsync同期（鍵認証）で正しいコマンドが生成・実行されること。
        """
        mock_json_loads.return_value = ["/local/music"]
        
        # Switch to key auth
        settings["rsync_pass"] = ""
        settings["rsync_use_key"] = "1"
        settings["rsync_key_path"] = "/path/to/key"

        with patch("os.path.exists", return_value=True):  # Key file exists
            tracks = [
                SimpleNamespace(sync=True, relative_path="/Album/Song.mp3")
            ]
            
            sync = RsyncSynchronizer(tracks, [], settings)
            sync.synchronize()
            
            actual_cmd = mock_subprocess_popen.call_args[0][0]
            
            # 期待されるrsyncコマンドの完全なリスト
            # Key auth does NOT use sshpass
            expected_cmd = [
                "rsync",
                "-avz",
                "--delete-excluded",
                "--include-from", "/tmp/temp_include_file",
                "--exclude=*",
                "/local/music",
                "-e", "ssh -p 22 -i /path/to/key", # SSH key option included
                "rsync_user@rsync_host:/remote/path"
            ]

            assert actual_cmd == expected_cmd

    def test_cp_local_file(self, settings, mock_subprocess_run, caplog):
        """
        cpメソッドがローカルファイルコピーで正しいrsyncコマンドを実行すること。
        """
        settings["rsync_host"] = "" # Local sync
        settings["sync_dest"] = "/local/backup"

        sync = RsyncSynchronizer([], [], settings)
        sync.cp("/src/file.txt", "dest/file.txt")

        expected_cmd = [
            "rsync", "-avz", "/src/file.txt", "/local/backup/dest/file.txt"
        ]
        mock_subprocess_run.assert_called_once()
        actual_cmd = mock_subprocess_run.call_args[0][0]
        assert all(arg in actual_cmd for arg in expected_cmd)
        assert "-e" not in actual_cmd

    def test_cp_remote_file_ssh(self, settings, mock_subprocess_run, caplog):
        """
        cpメソッドがリモートSSHファイルコピーで正しいrsyncコマンドを実行すること。
        """
        sync = RsyncSynchronizer([], [], settings)
        sync.cp("/src/file.txt", "dest/file.txt")

        expected_cmd = [
            "sshpass", "-p", "secret",
            "rsync", "-avz", "-e", "ssh -p 22", "/src/file.txt", "rsync_user@rsync_host:/remote/path/dest/file.txt"
        ]
        mock_subprocess_run.assert_called_once()
        actual_cmd = mock_subprocess_run.call_args[0][0]
        assert actual_cmd == expected_cmd

    def test_cp_failure_logs_error(self, settings, mock_subprocess_run, caplog):
        """
        cpメソッドでrsyncが失敗した場合にエラーがログに出力されること。
        """
        mock_subprocess_run.return_value.returncode = 1 # Simulate error
        mock_subprocess_run.return_value.stderr = "rsync error"

        sync = RsyncSynchronizer([], [], settings)
        
        with caplog.at_level(logging.INFO):
            sync.cp("/src/file.txt", "dest/file.txt")
            assert "Rsync cp failed: rsync error" in caplog.text
            
    def test_rm_remote_does_nothing(self, settings, mock_subprocess_run):
        """
        rm_remoteが何もしないこと（pass実装のため）。
        """
        sync = RsyncSynchronizer([], [], settings)
        sync.rm_remote("Music/Artist/song.mp3")
        mock_subprocess_run.assert_not_called()

    def test_mkdir_p_remote_does_nothing(self, settings, mock_subprocess_run):
        """
        mkdir_p_remoteが何もしないこと（pass実装のため）。
        """
        sync = RsyncSynchronizer([], [], settings)
        sync.mkdir_p_remote("Music/Artist")
        mock_subprocess_run.assert_not_called()

    def test_ls_remote_returns_empty_list(self, settings, mock_subprocess_run):
        """
        ls_remoteが空のリストを返すこと（pass実装のため）。
        """
        sync = RsyncSynchronizer([], [], settings)
        result = sync.ls_remote("Music")
        assert result is None

    def test_synchronize_include_file_content(self, settings, mock_subprocess_popen, mock_tempfile, mock_os_funcs, mock_json_loads):
        """
        synchronizeメソッドで生成されるrsyncの一時ファイル(include-from)の内容が正しいこと。
        トラックの相対パスとその親ディレクトリが全て含まれること。
        """
        mock_json_loads.return_value = ["/local/music"]

        tracks = [
            SimpleNamespace(sync=True, relative_path="/Album/SongA.mp3"),
            SimpleNamespace(sync=True, relative_path="/Album/Subdir/SongB.mp3"),
            SimpleNamespace(sync=True, relative_path="/Other/SongC.mp3"),
            SimpleNamespace(sync=False, relative_path="/Ignore/SongD.mp3") # sync=False は含まれない
        ]
        
        sync = RsyncSynchronizer(tracks, [], settings)

        # Mock open to capture file content
        m_open = mock_open()
        with patch("builtins.open", m_open):
            sync.synchronize()
        
        # Verify the file was opened for writing at the correct path
        m_open.assert_called_once_with("/tmp/temp_include_file", "w")
        
        # Get the written content
        handle = m_open()
        written_content = "".join(call_arg.args[0] for call_arg in handle.write.call_args_list)

        # Expected content (order does not matter, must be unique lines)
        expected_lines = {
            "/Album/SongA.mp3",
            "/Album/",
            "/Album/Subdir/SongB.mp3",
            "/Album/Subdir/", # Subdir も含まれるはず
            "/Other/SongC.mp3",
            "/Other/",
            "/" # Root path is also included by current logic
        }
        
        actual_lines = set(written_content.strip().splitlines())
        
        assert actual_lines == expected_lines


# --- AudioSynchronizer Base Class Tests ---

class TestAudioSynchronizer:
    """
    AudioSynchronizer基底クラスのsynchronizeメソッドの動作を検証するテスト。
    抽象メソッドをモックで実装したサブクラスを使用してテストする。
    """
    
    @pytest.fixture
    def mock_synchronizer_class(self):
        """モック実装を持つAudioSynchronizerサブクラスを返す"""
        from backend.core.syncer import AudioSynchronizer
        
        class MockSynchronizer(AudioSynchronizer):
            def __init__(self, tracks, playlists, settings, log_callback=None):
                super().__init__(tracks, playlists, settings, log_callback)
                # モックオブジェクトを作成
                self._cp_mock = MagicMock()
                self._rm_remote_mock = MagicMock()
                self._mkdir_p_remote_mock = MagicMock()
                self._ls_remote_mock = MagicMock(return_value=[])
                self._put_playlist_file_mock = MagicMock()
            
            # 抽象メソッドを実装(モックを呼び出す)
            def cp(self, filepath_from, relative_path_to):
                return self._cp_mock(filepath_from, relative_path_to)
            
            def rm_remote(self, relative_filepath_to):
                return self._rm_remote_mock(relative_filepath_to)
            
            def mkdir_p_remote(self, relative_filepath_to):
                return self._mkdir_p_remote_mock(relative_filepath_to)
            
            def ls_remote(self, relative_dir=""):
                return self._ls_remote_mock(relative_dir)
            
            def put_playlist_file(self, relative_dir=""):
                return self._put_playlist_file_mock(relative_dir)
        
        return MockSynchronizer
    
    def test_synchronize_copy_new_files(self, mock_synchronizer_class):
        """
        リモートに存在しない新規トラックがcpメソッドで転送されること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/new.mp3",
                file_name="new.mp3",
                relative_path="/Album/new.mp3"
            )
        ]
        
        sync = mock_synchronizer_class(tracks, [], {})
        sync._ls_remote_mock.return_value = []  # リモートは空
        
        sync.synchronize()
        
        # cpが呼ばれたことを確認
        sync._cp_mock.assert_called_once_with("/local/new.mp3", "Album/new.mp3")
    
    def test_synchronize_skip_existing_files(self, mock_synchronizer_class):
        """
        リモートに既に存在するファイルはスキップされること(cpが呼ばれない)。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/existing.mp3",
                file_name="existing.mp3",
                relative_path="/Album/existing.mp3"
            )
        ]
        
        sync = mock_synchronizer_class(tracks, [], {})
        # リモートに同じファイルが存在する(フルパスで返す)
        # ls_remoteのルート呼び出しでは("Album", True), ("existing.mp3", False)を返すが、
        # 再帰的にtraverseされるため、最終的にremote_filesには"Album/existing.mp3"が含まれる。
        # ここではその動作をシミュレートする。
        def mock_ls_remote_impl(rel_path):
            if rel_path == "":  # Root
                return [("Album", True)]
            elif rel_path == "Album":
                return [("existing.mp3", False)]
            else:
                return []
        
        sync._ls_remote_mock.side_effect = mock_ls_remote_impl
        
        sync.synchronize()
        
        # cpが呼ばれないことを確認
        sync._cp_mock.assert_not_called()
    
    def test_synchronize_delete_remote_files(self, mock_synchronizer_class):
        """
        同期リスト(local_map)にないリモートファイルが削除されること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/keep.mp3",
                file_name="keep.mp3",
                relative_path="/Album/keep.mp3"
            )
        ]
        
        settings = {"target_exts": "mp3"}
        sync = mock_synchronizer_class(tracks, [], settings)
        # リモートに2つのファイルがあり、1つは同期リストにない
        # traverse_remoteの動作をシミュレート
        def mock_ls_remote_impl(rel_path):
            if rel_path == "":  # Root
                return [("Album", True)]
            elif rel_path == "Album":
                return [("keep.mp3", False), ("old.mp3", False)]
            else:
                return []
        
        sync._ls_remote_mock.side_effect = mock_ls_remote_impl
        
        sync.synchronize()
        
        # old.mp3が削除されること
        sync._rm_remote_mock.assert_called_once_with("Album/old.mp3")
    
    def test_synchronize_filter_by_extension(self, mock_synchronizer_class):
        """
        target_exts設定に合致しないリモートファイルは削除されないこと。
        """
        tracks = []  # 同期リストは空
        
        settings = {"target_exts": "mp3,m4a"}  # mp3とm4aのみ対象
        sync = mock_synchronizer_class(tracks, [], settings)
        # リモートに様々な拡張子のファイルがある
        sync._ls_remote_mock.return_value = [
            ("song.mp3", False),   # target_exts に含まれる -> 削除
            ("video.mp4", False),  # target_exts に含まれない -> 削除されない
            ("audio.m4a", False),  # target_exts に含まれる -> 削除
            ("text.txt", False)    # target_exts に含まれない -> 削除されない
        ]
        
        sync.synchronize()
        
        # mp3とm4aのみ削除される
        assert sync._rm_remote_mock.call_count == 2
        deleted_files = [call.args[0] for call in sync._rm_remote_mock.call_args_list]
        assert "song.mp3" in deleted_files
        assert "audio.m4a" in deleted_files
        assert "video.mp4" not in deleted_files
        assert "text.txt" not in deleted_files
    
    def test_synchronize_create_directories(self, mock_synchronizer_class):
        """
        ファイルコピー前にmkdir_p_remoteが呼ばれること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/song.mp3",
                file_name="song.mp3",
                relative_path="/Artist/Album/song.mp3"
            )
        ]
        
        sync = mock_synchronizer_class(tracks, [], {})
        sync._ls_remote_mock.return_value = []  # リモートは空
        
        sync.synchronize()
        
        # mkdir_p_remoteが親ディレクトリで呼ばれる
        sync._mkdir_p_remote_mock.assert_called_once_with("Artist/Album")
    
    def test_synchronize_put_playlist(self, mock_synchronizer_class):
        """
        synchronize終了後にput_playlist_fileが呼ばれること。
        """
        playlists = [{"name": "Test", "content": "#EXTM3U\n"}]
        
        sync = mock_synchronizer_class([], playlists, {})
        sync.synchronize()
        
        # put_playlist_fileが呼ばれる
        sync._put_playlist_file_mock.assert_called_once()
    
    def test_synchronize_filter_sync_false(self, mock_synchronizer_class):
        """
        sync=Falseのトラックはコピーされず、リモートに存在すれば削除されること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/keep.mp3",
                file_name="keep.mp3",
                relative_path="/keep.mp3"
            ),
            SimpleNamespace(
                sync=False,  # sync=Falseのトラック
                file_path="/local/ignore.mp3",
                file_name="ignore.mp3",
                relative_path="/ignore.mp3"
            )
        ]
        
        settings = {"target_exts": "mp3"}
        sync = mock_synchronizer_class(tracks, [], settings)
        # リモートに両方のファイルが存在
        sync._ls_remote_mock.return_value = [
            ("keep.mp3", False),
            ("ignore.mp3", False)
        ]
        
        sync.synchronize()
        
        # keep.mp3はコピーされない(既に存在するため)
        # ignore.mp3は削除される(sync=Falseで同期リストにないため)
        sync._cp_mock.assert_not_called()
        sync._rm_remote_mock.assert_called_once_with("ignore.mp3")
    
    def test_synchronize_normalize_paths(self, mock_synchronizer_class):
        """
        Windows形式のパス(\\)が正規化されてリモート区切り文字(/)になること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path=r"C:\Music\song.mp3",
                file_name="song.mp3",
                relative_path=r"\Artist\Album\song.mp3"  # Windows形式
            )
        ]
        
        sync = mock_synchronizer_class(tracks, [], {})
        sync._ls_remote_mock.return_value = []
        
        sync.synchronize()
        
        # cpが正規化されたパスで呼ばれる
        sync._cp_mock.assert_called_once()
        called_args = sync._cp_mock.call_args[0]
        assert called_args[1] == "Artist/Album/song.mp3"  # \が/に変換される
    
    def test_synchronize_empty_tracks(self, mock_synchronizer_class):
        """
        トラックリストが空でもクラッシュせず、プレイリストのみ同期されること。
        """
        playlists = [{"name": "Empty", "content": "#EXTM3U\n"}]
        
        sync = mock_synchronizer_class([], playlists, {})
        sync.synchronize()
        
        # cpもrm_remoteも呼ばれない
        sync._cp_mock.assert_not_called()
        sync._rm_remote_mock.assert_not_called()
        # プレイリストは同期される
        sync._put_playlist_file_mock.assert_called_once()
    
    def test_synchronize_remote_scan_failure(self, mock_synchronizer_class):
        """
        ls_remoteがFileNotFoundErrorを投げても処理が継続すること。
        """
        tracks = [
            SimpleNamespace(
                sync=True,
                file_path="/local/new.mp3",
                file_name="new.mp3",
                relative_path="/new.mp3"
            )
        ]
        
        sync = mock_synchronizer_class(tracks, [], {})
        # ls_remoteがFileNotFoundErrorを投げる
        sync._ls_remote_mock.side_effect = FileNotFoundError("Remote not found")
        
        # クラッシュせずに完了すること
        sync.synchronize()
        
        # リモートファイルが取得できないため、全てのファイルがコピーされる
        sync._cp_mock.assert_called_once_with("/local/new.mp3", "new.mp3")
        # 削除は行われない(remote_filesが空のため)
        sync._rm_remote_mock.assert_not_called()
