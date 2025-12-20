import pytest
import os
import shutil
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest_asyncio

from backend.main import app
from backend.db.database import Base, get_db

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def temp_db():
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        # Cleanup
        await session.close()

    await engine.dispose()


@pytest_asyncio.fixture
async def override_get_db(temp_db):
    async def _get_db():
        yield temp_db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_get_db):
    return TestClient(app)


@pytest.fixture
def temp_fs():
    """Create a temporary directory with dummy audio files for scanning."""
    # Structure:
    # /ROOT
    #   /Artist1
    #     /Album1
    #       song1.mp3
    #       song2.mp3
    #   /Artist2
    #     song3.mp3
    #   /Excluded
    #     ignored.mp3

    tmp_dir = tempfile.mkdtemp()

    # Create directories
    os.makedirs(os.path.join(tmp_dir, "Artist1", "Album1"))
    os.makedirs(os.path.join(tmp_dir, "Artist2"))
    os.makedirs(os.path.join(tmp_dir, "Excluded"))

    # Create dummy files
    def create_file(path, content="dummy content"):
        with open(path, "w") as f:
            f.write(content)

    create_file(os.path.join(tmp_dir, "Artist1", "Album1", "song1.mp3"))
    create_file(os.path.join(tmp_dir, "Artist1", "Album1", "song2.mp3"))
    create_file(os.path.join(tmp_dir, "Artist2", "song3.mp3"))
    create_file(os.path.join(tmp_dir, "Excluded", "ignored.mp3"))
    create_file(os.path.join(tmp_dir, "info.txt"))  # Non-audio file

    yield tmp_dir

    shutil.rmtree(tmp_dir)
