import pytest
from backend.db.models import Track
from sqlalchemy import select

@pytest.mark.asyncio
async def test_batch_delete_tracks(client, temp_db):
    """
    [Integration - Tracks API] トラック一括削除の動作検証
    
    条件:
    1. DBに複数のトラックが登録されている
    2. DELETE /api/tracks/batch で特定のトラックIDを指定して削除
    
    検証項目:
    1. ステータスコード 200 が返ること
    2. 指定したトラックがDBから削除されていること
    3. 指定していないトラックは残っていること
    4. 存在しないIDを含んでいてもエラーにならず、存在するIDのものが削除されること
    """
    # 1. Setup Data
    t1 = Track(
        file_path="/music/del1.mp3",
        relative_path="del1.mp3",
        file_name="del1",
        title="Delete Me 1",
        size=1024
    )
    t2 = Track(
        file_path="/music/del2.mp3",
        relative_path="del2.mp3",
        file_name="del2",
        title="Delete Me 2",
        size=2048
    )
    t3 = Track(
        file_path="/music/keep.mp3",
        relative_path="keep.mp3",
        file_name="keep",
        title="Keep Me",
        size=4096
    )
    temp_db.add_all([t1, t2, t3])
    await temp_db.commit()
    await temp_db.refresh(t1)
    await temp_db.refresh(t2)
    await temp_db.refresh(t3)

    # 2. Execute Delete (including non-existent ID 999)
    target_ids = [t1.id, t2.id, 999]
    response = client.request("DELETE", "/api/tracks/batch", json={"ids": target_ids})
    
    # 3. Verify Response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # deleted_count might depend on implementation (usually returns rowcount of deleted rows)
    # Since 999 doesn't exist, it should be 2
    assert data["deleted_count"] == 2

    # 4. Verify DB State
    # t1 should be gone
    result = await temp_db.execute(select(Track).where(Track.id == t1.id))
    assert result.scalar() is None

    # t2 should be gone
    result = await temp_db.execute(select(Track).where(Track.id == t2.id))
    assert result.scalar() is None

    # t3 should exist
    result = await temp_db.execute(select(Track).where(Track.id == t3.id))
    existing_t3 = result.scalar()
    assert existing_t3 is not None
    assert existing_t3.title == "Keep Me"
