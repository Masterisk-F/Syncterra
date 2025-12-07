import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
import pytest_asyncio

@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_scan(client):
    response = await client.post("/api/scan")
    assert response.status_code == 200 # or 202 if I changed it. Code says return dict defaults to 200.
    assert response.json()["status"] == "accepted"

@pytest.mark.asyncio
async def test_sync(client):
    response = await client.post("/api/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
