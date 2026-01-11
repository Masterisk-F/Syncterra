
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException
from backend.api.album_art import get_album_art
from backend.db.albumart_models import AlbumArt

@pytest.mark.asyncio
async def test_get_album_art_found():
    """
    [API] アルバムアート取得 (正常系)
    
    条件:
    指定されたアルバム名のアートがDBに存在する。
    
    期待値:
    200 OK と画像データが返されること。
    """
    mock_db = AsyncMock()
    
    existing = AlbumArt(
        id=1,
        album_normalized="testalbum",
        image_data=b"fake_image",
        source_path="path",
        source_type="file"
    )
    
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = existing
    mock_db.execute.return_value = mock_result
    
    response = await get_album_art("TestAlbum", db=mock_db)
    
    assert response.body == b"fake_image"
    assert response.media_type == "image/jpeg"

@pytest.mark.asyncio
async def test_get_album_art_not_found():
    """
    [API] アルバムアート取得 (404)
    
    条件:
    指定されたアルバム名のアートが存在しない。
    
    期待値:
    404 Not Found エラーが発生すること。
    """
    mock_db = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc:
        await get_album_art("TestAlbum", db=mock_db)
    
    assert exc.value.status_code == 404
