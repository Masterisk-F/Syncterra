import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.database import init_db
import pytest_asyncio

from sqlalchemy import delete
from backend.db.models import Setting, Track
from backend.db.database import AsyncSessionLocal

# Integration Test: Settings API
# 目的: 設定APIエンドポイントが正しく動作するか検証する。


@pytest_asyncio.fixture(scope="function")
async def client():
    # Initialize DB before test
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Setting))
        await session.execute(delete(Track))
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_settings_empty(client):
    """
    [Settings API] 設定が空の状態での取得
    
    条件:
    1. DBに設定が1件も存在しない
    2. GET /api/settings を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. 空のリスト [] が返ること
    """
    response = await client.get("/api/settings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_update_setting(client):
    """
    [Settings API] 新規設定の追加
    
    条件:
    1. 存在しないキーで PUT /api/settings を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスに status: ok が含まれること
    3. GET で取得したデータに追加した設定が含まれること
    """
    response = await client.put(
        "/api/settings", json={"key": "test_key", "value": "test_val"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = await client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["key"] == "test_key"
    assert data[0]["value"] == "test_val"


@pytest.mark.asyncio
async def test_update_existing_setting(client):
    """
    [Settings API] 既存設定の更新
    
    条件:
    1. 一度設定を追加する
    2. 同じキーで異なる値をPUT
    
    期待値:
    1. ステータスコード 200 が返ること
    2. GET で取得した値が更新後の値になっていること
    """
    # Setup initial state
    await client.put("/api/settings", json={"key": "test_key", "value": "initial_val"})

    response = await client.put(
        "/api/settings", json={"key": "test_key", "value": "updated_val"}
    )
    assert response.status_code == 200

    response = await client.get("/api/settings")
    data = response.json()
    assert data[0]["value"] == "updated_val"
