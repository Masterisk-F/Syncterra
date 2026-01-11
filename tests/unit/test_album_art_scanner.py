import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from backend.core.album_art_scanner import AlbumArtScanner
from backend.db.models import Track
from backend.db.albumart_models import AlbumArt

@pytest.mark.asyncio
async def test_album_scanner_priority():
    """
    [Scanner] 優先順位のテスト
    
    目的:
    スキャナーがトラック番号の若いファイルを優先してソースとして選択するか検証する。
    """
    scanner = AlbumArtScanner()
    
    # Mock data
    track1 = Track(id=1, album="TestAlbum", file_path="/music/TestAlbum/track1.mp3", track_num="1")
    track2 = Track(id=2, album="TestAlbum", file_path="/music/TestAlbum/track2.mp3", track_num="2")
    tracks = [track2, track1]
    
    # _find_sourceのモック: ファイルパスに基づいて結果を返す
    async def mock_find_source(path, album):
        if path == "/music/TestAlbum/track1.mp3":
            return ("meta", path, 100.0)
        return ("file", "/music/TestAlbum/art.jpg", 200.0)
        
    scanner._find_source = AsyncMock(side_effect=mock_find_source) 
    
    # run_in_threadpoolのモック
    with patch("backend.core.album_art_scanner.run_in_threadpool", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = lambda func, *args: func(*args) if callable(func) else None

        # _find_sourceと_process_imageのモック設定
        scanner._find_source = MagicMock(return_value=("meta", "/music/TestAlbum/track1.mp3", 100.0))
        scanner._process_image = MagicMock(return_value=b"fake_image_data")
        
        session = AsyncMock()
        session.add = MagicMock() # .add is sync
        existing_result = MagicMock()
        existing_result.scalars().first.return_value = None
        session.execute.return_value = existing_result
        
        await scanner._process_album(session, "testalbum", "TestAlbum", tracks)
        
        # 検証: track1 (track_num="1") が選択されたか
        scanner._find_source.assert_called_with("/music/TestAlbum/track1.mp3", "TestAlbum")
        
        # 検証: DBへの追加
        assert session.add.called
        args, _ = session.add.call_args
        added_art = args[0]
        assert added_art.album_display == "TestAlbum"
        assert added_art.source_path == "/music/TestAlbum/track1.mp3"


@pytest.mark.asyncio
async def test_album_scanner_update_logic():
    """
    [Scanner] 更新ロジックのテスト
    
    目的:
    ソースファイルのmtimeが変更された場合のみ更新されるか検証する。
    """
    scanner = AlbumArtScanner()
    track = Track(id=1, album="TestAlbum", file_path="/music/TestAlbum/track.mp3", track_num="1")
    
    # ソース発見のモック
    scanner._find_source = MagicMock(return_value=("file", "/music/TestAlbum/cover.jpg", 200.0))
    scanner._process_image = MagicMock(return_value=b"new_data")
    
    with patch("backend.core.album_art_scanner.run_in_threadpool", new_callable=AsyncMock) as mock_run:
        # run_in_threadpoolのモック: 同期関数実行
        async def run_sync_mock(func, *args):
            return func(*args)
        mock_run.side_effect = run_sync_mock

        session = AsyncMock()
        
        # ケース1: 既存のアートが古い場合
        existing_art = AlbumArt(
            album_normalized="testalbum",
            source_path="/music/TestAlbum/cover.jpg",
            source_mtime=100.0,
            image_data=b"old_data"
        )
        
        mock_result = MagicMock()
        mock_result.scalars().first.return_value = existing_art
        session.execute.return_value = mock_result
        
        await scanner._process_album(session, "testalbum", "TestAlbum", [track])
        
        assert existing_art.image_data == b"new_data"
        assert existing_art.source_mtime == 200.0
        
        # ケース2: 既存のアートが最新の場合
        existing_art.source_mtime = 200.0
        # モックリセット
        scanner._process_image.reset_mock()
        
        await scanner._process_album(session, "testalbum", "TestAlbum", [track])
        
        scanner._process_image.assert_not_called()
