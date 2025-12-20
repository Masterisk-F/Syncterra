import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
import pytest_asyncio


@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_swagger_ui(client):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text


@pytest.mark.asyncio
async def test_openapi_json(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["openapi"].startswith("3.")
    assert "paths" in data
