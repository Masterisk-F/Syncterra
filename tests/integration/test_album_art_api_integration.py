import pytest
from backend.db.albumart_models import AlbumArt

@pytest.mark.asyncio
async def test_api_get_album_art(client, temp_art_db):
    """
    [API] アルバムアートAPI統合テスト
    
    条件:
    DBにアルバムアートが存在する状態で API GET リクエストを送る。
    
    期待値:
    正常系: 200 OK と画像データが返されること。
    異常系: 存在しないアルバム名の場合は 404 Not Found が返されること。
    """
    # Create art
    art = AlbumArt(
        album_normalized="testalbum",
        album_display="TestAlbum",
        image_data=b"real_image_bytes",
        source_path="path",
        source_type="file",
        source_mtime=100.0,
    )
    temp_art_db.add(art)
    await temp_art_db.commit()
    
    # Test valid
    response = client.get("/api/album-arts/TestAlbum")
    assert response.status_code == 200
    assert response.content == b"real_image_bytes"
    
    # Test not found
    response = client.get("/api/album-arts/Unknown")
    assert response.status_code == 404
