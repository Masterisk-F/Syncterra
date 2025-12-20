import pytest
import os
import json
from sqlalchemy.future import select
from backend.core.scanner import ScannerService
from backend.db.models import Track, Setting

# 日本語でのドキュメンテーションとテスト実装
# Integration Test: Scanner Flow
# 目的: ファイルシステムの状態変化がDBに正しく同期されるか検証する。

@pytest.mark.asyncio
async def test_scanner_flow_new_files(temp_db, temp_fs, create_settings, patch_db_session):
    """
    [Scanner] 新規ファイル追加検知フロー
    
    条件:
    1. 監視対象フォルダに新しい音楽ファイルが配置される
    2. スキャナーが実行される
    
    期待値:
    1. DBの tracks テーブルにファイル情報が登録されること
    2. ファイル名、パスが正しく記録されていること
    """
    # 1. 設定準備
    scan_paths = json.dumps([temp_fs])
    await create_settings(scan_paths=scan_paths, target_exts="mp3")

    # 2. スキャン実行
    scanner = ScannerService()
    await scanner.run_scan()

    # 3. 検証
    result = await temp_db.execute(select(Track))
    tracks = result.scalars().all()
    file_names = [t.file_name for t in tracks]

    # 事前準備されたファイルが含まれているか確認
    # temp_fs fixture creates: song1.mp3, song2.mp3, song3.mp3
    assert "song1" in file_names
    assert "song2" in file_names
    assert "song3" in file_names
    
    # 登録されたデータの整合性チェック
    track1 = next(t for t in tracks if t.file_name == "song1")
    assert "/Artist1/Album1/song1.mp3" in track1.relative_path
    assert track1.msg != "Missing"
    
    # メタデータ抽出の検証
    # conftest.pyで設定した値: title="Song 1", artist="Artist 1", album="Album 1"
    assert track1.title == "Song 1"
    assert track1.artist == "Artist 1"
    assert track1.album == "Album 1"

@pytest.mark.asyncio
async def test_scanner_flow_delete_files(temp_db, temp_fs, create_settings, patch_db_session):
    """
    [Scanner] ファイル削除検知フロー
    
    条件:
    1. 既存のファイルが削除される
    2. スキャナーが実行される
    
    期待値:
    1. DB上の該当レコードの msg カラムが 'Missing' に更新されること
    2. レコード自体は削除されずに残ること（履歴保持のため）
    """
    # 準備: 初回スキャン
    scan_paths = json.dumps([temp_fs])
    await create_settings(scan_paths=scan_paths, target_exts="mp3")
    scanner = ScannerService()
    await scanner.run_scan()
    
    # 削除実行
    target_file = os.path.join(temp_fs, "Artist2", "song3.mp3")
    os.remove(target_file)
    
    # 再スキャン
    await scanner.run_scan()
    
    # 検証
    result = await temp_db.execute(select(Track).where(Track.file_name == "song3"))
    track = result.scalars().first()
    
    assert track is not None
    assert track.msg == "Missing"

@pytest.mark.asyncio
async def test_scanner_flow_exclude_dirs(temp_db, temp_fs, create_settings, patch_db_session):
    """
    [Scanner] 除外設定フロー
    
    条件:
    1. 除外ディレクトリ設定 (exclude_dirs) にフォルダ名を追加
    2. そのフォルダ内にファイルが存在する
    3. スキャナーを実行
    
    期待値:
    1. 除外フォルダ内のファイルはDBに登録されないこと
    """
    # 設定: Excludedフォルダを除外
    scan_paths = json.dumps([temp_fs])
    await create_settings(
        scan_paths=scan_paths, 
        target_exts="mp3",
        exclude_dirs="Excluded"
    )
    
    # スキャン実行
    scanner = ScannerService()
    await scanner.run_scan()
    
    # 検証
    result = await temp_db.execute(select(Track))
    tracks = result.scalars().all()
    file_names = [t.file_name for t in tracks]
    
    # song1 (Artist1) は対象
    assert "song1" in file_names
    # ignored (Excluded) は対象外
    assert "ignored" not in file_names

@pytest.mark.asyncio
async def test_scanner_flow_update_files(temp_db, temp_fs, create_settings, patch_db_session):
    """
    [Scanner] ファイル更新検知フロー
    
    条件:
    1. ファイルのタイムスタンプが更新される
    2. スキャナーを実行
    
    期待値:
    1. DB上の更新日時等のメタデータが再取得・更新されること
       (※ここではエラーなくスキャンが完了し、ファイルが存在し続けることを最低限確認)
    """
    # 準備
    scan_paths = json.dumps([temp_fs])
    await create_settings(scan_paths=scan_paths, target_exts="mp3")
    scanner = ScannerService()
    await scanner.run_scan()
    
    # ファイル更新 (utime)
    target_file = os.path.join(temp_fs, "Artist1", "Album1", "song1.mp3")
    # 未来の日時に更新
    os.utime(target_file, (2000000000, 2000000000))
    
    # 再スキャン
    await scanner.run_scan()
    
    # 検証
    result = await temp_db.execute(select(Track).where(Track.file_name == "song1"))
    track = result.scalars().first()
    assert track is not None
    # msgがMissingになっていないこと
    assert track.msg != "Missing"

@pytest.mark.asyncio
async def test_scanner_flow_progress_callbacks(temp_db, temp_fs, create_settings, patch_db_session):
    """
    [Scanner] 進捗ログ・コールバックフロー
    
    条件:
    1. 複数のファイルが存在する状態でスキャンを実行
    2. progress_callback, log_callback を渡す
    
    期待値:
    1. progress_callback が 0% から 100% まで呼び出されること
    2. log_callback が新規追加ファイルの数だけ呼び出されること
    3. バックエンドの処理が非同期的に進行し、コールバックが機能すること
    """
    from unittest.mock import MagicMock
    
    # 準備: 20個のファイルを作成
    for i in range(20):
        with open(os.path.join(temp_fs, "Artist1", "Album1", f"track{i}.mp3"), "w") as f:
            f.write("dummy")
            
    scan_paths = json.dumps([temp_fs])
    await create_settings(scan_paths=scan_paths, target_exts="mp3")
    
    scanner = ScannerService()
    
    # コールバックのモック
    progress_cb = MagicMock()
    log_cb = MagicMock()
    
    # スキャン実行
    await scanner.run_scan(progress_callback=progress_cb, log_callback=log_cb)
    
    # 検証
    # 1. Progress: 終了(100)は呼ばれるべき。0は実装により各ファイル処理後なので呼ばれない場合も可。
    progress_cb.assert_any_call(100)
    # ファイル数に応じた中間の呼び出しがあるか
    # 24ファイル(fixture 4 + test 20)の場合、5%刻みで約12回前後の呼び出しになるため、
    # 余裕を持って10回以上であることを確認
    assert progress_cb.call_count >= 10
    
    # 2. Log: ファイル追加ログ
    # "New file added: ..." のようなログが出るはず
    # 少なくとも20回以上呼ばれる (開始/終了ログ含むかも)
    assert log_cb.call_count >= 20
    
    # メッセージの内容確認 (一部)
    calls = [args[0] for args, _ in log_cb.call_args_list]
    assert any("track0.mp3" in msg for msg in calls)
