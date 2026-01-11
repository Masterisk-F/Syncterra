import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import app

# Integration Test: API Documentation
# 目的: Swagger UIとOpenAPI仕様が正しく公開されているか検証する。


@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_swagger_ui(client):
    """
    [API Documentation] Swagger UI公開確認

    条件:
    1. GET /docs を実行

    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスHTMLに "Swagger UI" が含まれること
    """
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


@pytest.mark.asyncio
async def test_openapi_json(client):
    """
    [API Documentation] OpenAPI仕様公開確認

    条件:
    1. GET /openapi.json を実行

    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスJSONに openapi 3.x バージョンが含まれること
    3. paths セクションが存在すること
    """
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["openapi"].startswith("3.")
    assert "paths" in data
