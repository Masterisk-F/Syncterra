import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.scanner import ScannerService
from backend.db.models import Track


@pytest.mark.asyncio
async def test_run_scan_force_true():
    """
    [Scanner] force=True の場合のメタデータ再抽出テスト

    目的:
    force=True の場合、ファイルの mtime が DB と一致していても
    メタデータの再抽出（_extract_metadata）が実行されることを検証する。
    """
    scanner = ScannerService()

    # テストデータ
    file_path = "/music/test.mp3"
    rel_path = "/test.mp3"
    mtime = 123456789.0
    mtime_dt = datetime.datetime.fromtimestamp(mtime)

    # DB上の既存トラック（mtimeが一致している状態）
    existing_track = Track(
        file_path=file_path,
        relative_path=rel_path,
        last_modified=mtime_dt,
        missing=False
    )

    # 各種モック
    mock_db = AsyncMock()
    # 既存トラックを返す
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [existing_track]
    mock_db.execute.return_value = mock_result

    # 1. ファイルシステムスキャンのモック
    files_to_process = [(file_path, rel_path, mtime)]

    with patch("backend.core.scanner.AsyncSessionLocal", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db))), \
         patch("backend.core.scanner.run_in_threadpool") as mock_run_in_threadpool, \
         patch("backend.core.scanner.AlbumArtScanner", create=True) as mock_art_scanner_cls:

        # ScannerService.load_settings をスキップ
        scanner.load_settings = AsyncMock()
        scanner.settings = {"scan_paths": '["/music"]'}

        # run_in_threadpool の挙動を定義
        async def side_effect(func, *args):
            if func == scanner._scan_filesystem:
                return files_to_process
            if func == scanner._extract_metadata:
                return {"title": "Forced Title"}
            return func(*args) if callable(func) else None

        mock_run_in_threadpool.side_effect = side_effect

        # 実行: force=True
        await scanner.run_scan(force=True)

        # 検証: _extract_metadata が呼ばれたか
        # 呼ばれた回数を確認（既存のロジックでは mtime が一致すると呼ばれない）
        extract_calls = [call for call in mock_run_in_threadpool.call_args_list if call[0][0] == scanner._extract_metadata]
        assert len(extract_calls) == 1
        assert extract_calls[0][0][1] == file_path

@pytest.mark.asyncio
async def test_run_scan_force_false():
    """
    [Scanner] force=False の場合のメタデータスキップテスト

    目的:
    force=False の場合、ファイルの mtime が DB と一致していれば
    メタデータの再抽出（_extract_metadata）がスキップされることを検証する。
    """
    scanner = ScannerService()

    # テストデータ
    file_path = "/music/test.mp3"
    rel_path = "/test.mp3"
    mtime = 123456789.0
    mtime_dt = datetime.datetime.fromtimestamp(mtime)

    # DB上の既存トラック（mtimeが一致している状態）
    existing_track = Track(
        file_path=file_path,
        relative_path=rel_path,
        last_modified=mtime_dt,
        missing=False
    )

    # 各種モック
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [existing_track]
    mock_db.execute.return_value = mock_result

    files_to_process = [(file_path, rel_path, mtime)]

    with patch("backend.core.scanner.AsyncSessionLocal", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db))), \
         patch("backend.core.scanner.run_in_threadpool") as mock_run_in_threadpool, \
         patch("backend.core.scanner.AlbumArtScanner", create=True) as mock_art_scanner_cls:

        scanner.load_settings = AsyncMock()
        scanner.settings = {"scan_paths": '["/music"]'}

        async def side_effect(func, *args):
            if func == scanner._scan_filesystem:
                return files_to_process
            return func(*args) if callable(func) else None

        mock_run_in_threadpool.side_effect = side_effect

        # 実行: force=False (デフォルト)
        await scanner.run_scan(force=False)

        # 検証: _extract_metadata が呼ばれていないこと
        extract_calls = [call for call in mock_run_in_threadpool.call_args_list if call[0][0] == scanner._extract_metadata]
        assert len(extract_calls) == 0
