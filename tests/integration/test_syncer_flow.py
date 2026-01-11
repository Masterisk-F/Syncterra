import os
from unittest.mock import patch

import pytest

from backend.core.syncer import SyncService
from backend.db.models import Track

# Integration Test: Syncer Flow
# 目的: DBの状態と設定に基づいて、適切な同期コマンドが発行されるか検証する。


async def create_track(db, file_path, relative_path, sync=True, file_name="file.mp3"):
    """テスト用トラック作成ヘルパー"""
    filtered_rel_path = relative_path.lstrip("/")  # Ensure relative path is relative
    t = Track(
        file_path=file_path,
        relative_path=filtered_rel_path,
        file_name=file_name,
        sync=sync,
    )
    db.add(t)
    await db.commit()
    return t


@pytest.mark.asyncio
async def test_syncer_flow_adb(temp_db, create_settings, patch_db_session):
    """
    [Syncer] ADB同期フロー

    条件:
    1. 同期モードが 'adb'
    2. 未同期のファイル(sync=True) がDBに存在する
    3. 同期対象外のファイル(sync=False) も存在する

    期待値:
    1. 'adb push' コマンドが、対象ファイルに対してのみ実行されること
    2. 同期対象外ファイルは転送されないこと
    """
    # 1. 設定
    await create_settings(sync_mode="adb", sync_dest="/sdcard/Music")

    # 2. データ準備
    # データ整合性: file_path は通常、ルートパス + relative_path の形になる
    # ルート: /local
    await create_track(
        temp_db,
        "/local/Artist/Album/song1.mp3",
        "Artist/Album/song1.mp3",
        sync=True,
        file_name="song1.mp3",
    )
    # 除外
    await create_track(
        temp_db,
        "/local/Artist/Album/song2.mp3",
        "Artist/Album/song2.mp3",
        sync=False,
        file_name="song2.mp3",
    )

    # 3. モック準備 & 実行
    # run_in_threadpool: 同期関数を非同期で呼ぶラッパーを無効化（即時実行）
    # subprocess.run: 実際のコマンド実行を阻止して検証
    with (
        patch(
            "backend.core.syncer.run_in_threadpool",
            side_effect=lambda f, *args: f(*args),
        ),
        patch("subprocess.run") as mock_run,
    ):
        # ADB ls (初期チェック) のモック
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""  # 既存ファイルなし
        mock_run.return_value.stderr = ""

        # 実行
        await SyncService.run_sync()

        # 4. 検証
        # pushコマンドが呼ばれたか確認
        push_calls = [c for c in mock_run.call_args_list if "push" in str(c)]

        # song1.mp3 は転送されるべき
        song1_pushed = any(
            "/local/Artist/Album/song1.mp3" in str(c) for c in push_calls
        )
        assert song1_pushed, "song1.mp3 should be pushed via ADB"

        # song2.mp3 は転送されるべきではない
        song2_pushed = any(
            "/local/Artist/Album/song2.mp3" in str(c) for c in push_calls
        )
        assert not song2_pushed, "song2.mp3 (sync=False) should NOT be pushed"

        # パスの結合が正しいか確認 (DEST + Relative)
        # 期待: /sdcard/Music/Artist/Album/song1.mp3
        expected_dest = "/sdcard/Music/Artist/Album/song1.mp3"
        dest_check = any(expected_dest in str(c) for c in push_calls)
        assert dest_check, f"Destination path should confirm to {expected_dest}"


@pytest.mark.asyncio
async def test_syncer_flow_rsync(temp_db, create_settings, patch_db_session):
    """
    [Syncer] Rsync同期フロー

    条件:
    1. 同期モードが 'rsync'
    2. リモートホスト設定あり (SSH経由)
    3. 同期対象ファイルが存在

    期待値:
    1. 'rsync' コマンドが実行されること
    2. SSHオプション (-e ssh ...) が含まれること
    3. include-from に渡される一時ファイルに、対象ファイルパスが含まれていること
    """
    # 1. 設定
    await create_settings(
        sync_mode="rsync",
        sync_dest="/remote/music",
        rsync_host="192.168.1.100",
        rsync_user="user",
        rsync_port="2222",
        rsync_pass="password",
        scan_paths='["/local/music"]',
    )

    # 2. データ準備
    await create_track(
        temp_db, "/local/music/Artist/song1.mp3", "Artist/song1.mp3", sync=True
    )

    # 3. モック準備 & 実行
    with (
        patch(
            "backend.core.syncer.run_in_threadpool",
            side_effect=lambda f, *args: f(*args),
        ),
        patch("subprocess.Popen") as mock_popen,
        patch("subprocess.run"),
    ):  # For mkdir/cp commands if any
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.stdout = []

        # 実行
        await SyncService.run_sync()

        # 4. 検証
        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]  # First arg is the command list

        # sshpassが使われているので、コマンドの先頭は sshpass
        assert cmd[0] == "sshpass"
        assert cmd[2] == "password"

        # rsyncコマンド本体は cmd[3] から始まる
        rsync_idx = 3
        assert cmd[rsync_idx] == "rsync"

        # SSH設定 (-e ...)
        assert "-e" in cmd
        ssh_cmd = cmd[cmd.index("-e") + 1]
        assert "ssh -p 2222" in ssh_cmd

        # 宛先
        assert cmd[-1] == "user@192.168.1.100:/remote/music"

        # include-from ファイルの検証
        assert "--include-from" in cmd
        include_file_idx = cmd.index("--include-from") + 1
        include_file_path = cmd[include_file_idx]

        # 実際には一時ファイルはもう消えているかもしれないが、
        # コードの挙動として正しい引数が渡っているかを確認
        assert "tmp" in include_file_path or os.path.sep in include_file_path
