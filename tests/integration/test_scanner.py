import pytest
from unittest.mock import patch
from backend.core.scanner import ScannerService
from backend.db.models import Track, Setting
from backend.db.database import init_db, AsyncSessionLocal
import datetime
import pytest_asyncio
from sqlalchemy import delete


@pytest_asyncio.fixture
async def db_session():
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Setting))
        await session.execute(delete(Track))
        await session.commit()
        yield session


@pytest.fixture
def scanner():
    return ScannerService()


@pytest.mark.asyncio
async def test_scanner_load_settings(scanner, db_session):
    # Seed settings
    db_session.add(Setting(key="scan_paths", value='["/music"]'))
    db_session.add(Setting(key="target_exts", value="mp3,m4a"))
    await db_session.commit()

    await scanner.load_settings(db_session)

    assert scanner._get_setting("scan_paths") == '["/music"]'
    assert scanner._get_setting("target_exts") == "mp3,m4a"


@pytest.mark.asyncio
async def test_scanner_run_scan(scanner, db_session):
    # Mock settings
    db_session.add(Setting(key="scan_paths", value='["/tmp/music"]'))
    await db_session.commit()

    # Mock filesystem scan result with EXPECTED leading slash
    mock_files = [
        ("/tmp/music/song1.mp3", "/music/song1.mp3", 1000.0),
        ("/tmp/music/song2.mp4", "/music/song2.mp4", 2000.0),
    ]

    # Mock metadata extraction
    mock_meta_1 = {
        "file_name": "song1",
        "title": "Song 1",
        "artist": "Artist 1",
        "duration": 180,
        "codec": "mp3",
    }
    mock_meta_2 = {
        "file_name": "song2",
        "title": "Song 2",
        "artist": "Artist 2",
        "duration": 200,
        "codec": "mp4",
    }

    with (
        patch.object(
            scanner, "_scan_filesystem", return_value=mock_files
        ) as mock_scan_fs,
        patch.object(
            scanner, "_extract_metadata", side_effect=[mock_meta_1, mock_meta_2]
        ) as mock_extract,
    ):
        await scanner.run_scan()

        # Verify DB
        from sqlalchemy.future import select

        result = await db_session.execute(select(Track))
        tracks = result.scalars().all()
        assert len(tracks) == 2

        t1 = next(t for t in tracks if t.file_name == "song1")
        assert t1.title == "Song 1"
        assert t1.relative_path == "/music/song1.mp3"  # Must have slash

        t2 = next(t for t in tracks if t.file_name == "song2")
        assert t2.relative_path == "/music/song2.mp4"  # Must have slash


def test_scan_filesystem_logic(scanner):
    # Test the actual path calculation logic without mocking the method itself, but mocking os.walk

    # Structure:
    # /tmp/media/Album1/song.mp3
    # Scan path: /tmp/media/Album1
    # Expected relative: /Album1/song.mp3

    with (
        patch("os.path.exists", return_value=True),
        patch("os.walk") as mock_walk,
        patch("os.stat") as mock_stat,
    ):
        # Mocking os.walk return for /tmp/media/Album1
        # yields (root, dirs, files)
        mock_walk.return_value = [("/tmp/media/Album1", [], ["song.mp3"])]

        mock_stat.return_value.st_mtime = 12345.0

        results = scanner._scan_filesystem(["/tmp/media/Album1"], [".mp3"], [])

        assert len(results) == 1
        full_path, rel_path, mtime = results[0]
        assert full_path == "/tmp/media/Album1/song.mp3"
        assert rel_path == "/Album1/song.mp3"  # Confirm leading slash

    # Test Case 2: Scan path is parent
    # Structure: /tmp/media/Album1/song.mp3
    # Scan path: /tmp/media
    # Expected relative: /media/Album1/song.mp3

    with (
        patch("os.path.exists", return_value=True),
        patch("os.walk") as mock_walk,
        patch("os.stat") as mock_stat,
    ):
        mock_walk.return_value = [("/tmp/media/Album1", [], ["song.mp3"])]
        mock_stat.return_value.st_mtime = 12345.0

        results = scanner._scan_filesystem(["/tmp/media"], [".mp3"], [])

        assert len(results) == 1
        _, rel_path, _ = results[0]
        assert rel_path == "/media/Album1/song.mp3"


@pytest.mark.asyncio
async def test_scanner_missing_file_logic(scanner, db_session):
    # Seed DB with a track
    t1 = Track(
        file_path="/tmp/music/existing.mp3",
        relative_path="/music/existing.mp3",
        last_modified=datetime.datetime.now(),
        file_name="existing",
    )
    db_session.add(t1)
    db_session.add(Setting(key="scan_paths", value='["/tmp/music"]'))
    await db_session.commit()

    # Scan result returns NOTHING (file removed)
    with patch.object(scanner, "_scan_filesystem", return_value=[]):
        await scanner.run_scan()

        await db_session.refresh(t1)
        assert t1.msg == "Missing"
