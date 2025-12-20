import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.database import init_db
from backend.db.models import Track
import pytest_asyncio


@pytest_asyncio.fixture(scope="function")
async def client():
    # Initialize DB before test
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


from sqlalchemy import delete


@pytest_asyncio.fixture(scope="function")
async def seed_tracks():
    # We need a session to seed
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Hack: use app dependency injection or just direct DB access?
        # Direct DB access is cleaner but requires creating session.
        from backend.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Clear existing tracks
            await session.execute(delete(Track))

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
            session.add(t1)
            session.add(t2)
            await session.commit()
            # refresh to get IDs
            await session.refresh(t1)
            await session.refresh(t2)
            return [t1, t2]


@pytest.mark.asyncio
async def test_get_tracks(client, seed_tracks):
    response = await client.get("/api/tracks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # could be more if other tests ran? no scope function

    # Sort by ID to ensure order
    data.sort(key=lambda x: x["id"])
    assert data[0]["title"] == "Title1"
    assert data[1]["title"] == "Title2"


@pytest.mark.asyncio
async def test_update_track(client, seed_tracks):
    t1 = seed_tracks[0]
    response = await client.put(f"/api/tracks/{t1.id}", json={"sync": True})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify
    response = await client.get("/api/tracks")
    data = response.json()
    updated = next(x for x in data if x["id"] == t1.id)
    assert updated["sync"]


@pytest.mark.asyncio
async def test_batch_update(client, seed_tracks):
    ids = [t.id for t in seed_tracks]
    response = await client.put("/api/tracks/batch", json={"ids": ids, "sync": True})
    assert response.status_code == 200, response.json()

    response = await client.get("/api/tracks")
    data = response.json()
    for item in data:
        if item["id"] in ids:
            assert item["sync"]
