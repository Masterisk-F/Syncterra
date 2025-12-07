import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.database import init_db
import pytest_asyncio

from sqlalchemy import delete
from backend.db.models import Setting, Track
from backend.db.database import AsyncSessionLocal

@pytest_asyncio.fixture(scope="function")
async def client():
    # Initialize DB before test
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Setting))
        await session.execute(delete(Track))
        await session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_settings_empty(client):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_update_setting(client):
    response = await client.put("/api/settings", json={"key": "test_key", "value": "test_val"})
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
    # Setup initial state
    await client.put("/api/settings", json={"key": "test_key", "value": "initial_val"})

    response = await client.put("/api/settings", json={"key": "test_key", "value": "updated_val"})
    assert response.status_code == 200

    response = await client.get("/api/settings")
    data = response.json()
    assert data[0]["value"] == "updated_val"
