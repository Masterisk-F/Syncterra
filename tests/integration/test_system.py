import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
import pytest_asyncio

# Integration Test: System API
# 目的: スキャン/同期のトリガーAPIが正しくレスポンスを返すか検証する。


@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_scan(client):
    """
    [System API] スキャン開始トリガー
    
    条件:
    1. POST /api/scan を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスに status: accepted が含まれること
       (バックグラウンドでスキャン処理が開始されたことを示す)
    """
    response = await client.post("/api/scan")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_sync(client):
    """
    [System API] 同期開始トリガー
    
    条件:
    1. POST /api/sync を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスに status: accepted が含まれること
       (バックグラウンドで同期処理が開始されたことを示す)
    """
    response = await client.post("/api/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
