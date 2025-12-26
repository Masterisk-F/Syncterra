import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.database import init_db
from backend.db.models import Track
import pytest_asyncio
from sqlalchemy import delete

# Integration Test: Tracks API
# 目的: トラック一覧取得・更新APIが正しく動作するか検証する。


@pytest_asyncio.fixture(scope="function")
async def seed_tracks(temp_db):
    # Clear existing tracks
    await temp_db.execute(delete(Track))

    t1 = Track(
        file_path="/music/t1.mp3",
        relative_path="t1.mp3",
        file_name="t1",
        title="Title1",
        sync=False,
    )
    t2 = Track(
        file_path="/music/t2.mp3",
        relative_path="t2.mp3",
        file_name="t2",
        title="Title2",
        sync=True,
    )
    temp_db.add(t1)
    temp_db.add(t2)
    await temp_db.commit()
    # refresh to get IDs
    await temp_db.refresh(t1)
    await temp_db.refresh(t2)
    return [t1, t2]


@pytest.mark.asyncio
async def test_get_tracks(client, seed_tracks):
    """
    [Tracks API] トラック一覧取得
    
    条件:
    1. DBに2件のトラックが登録されている
    2. GET /api/tracks を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. 登録した2件のトラックが取得できること
    3. 各トラックのtitle等の情報が正しいこと
    """
    response = client.get("/api/tracks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # could be more if other tests ran? no scope function

    # Sort by ID to ensure order
    data.sort(key=lambda x: x["id"])
    assert data[0]["title"] == "Title1"
    assert data[1]["title"] == "Title2"


@pytest.mark.asyncio
async def test_update_track(client, seed_tracks):
    """
    [Tracks API] トラック個別更新
    
    条件:
    1. 特定トラック(sync=False)がDBに存在
    2. PUT /api/tracks/{id} で sync=True に更新
    
    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスに status: ok が含まれること
    3. GET で取得した該当トラックのsyncがTrueになっていること
    """
    t1 = seed_tracks[0]
    response = client.put(f"/api/tracks/{t1.id}", json={"sync": True})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify
    response = client.get("/api/tracks")
    data = response.json()
    updated = next(x for x in data if x["id"] == t1.id)
    assert updated["sync"]


@pytest.mark.asyncio
async def test_batch_update(client, seed_tracks):
    """
    [Tracks API] トラック一括更新
    
    条件:
    1. 複数トラックがDBに存在
    2. PUT /api/tracks/batch で複数IDを指定して sync=True に更新
    
    期待値:
    1. ステータスコード 200 が返ること
    2. GET で取得した指定トラック全てのsyncがTrueになっていること
    """
    ids = [t.id for t in seed_tracks]
    response = client.put("/api/tracks/batch", json={"ids": ids, "sync": True})
    assert response.status_code == 200, response.json()

    response = client.get("/api/tracks")
    data = response.json()
    for item in data:
        if item["id"] in ids:
            assert item["sync"]
