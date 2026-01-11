from unittest.mock import MagicMock, patch

import pytest

from backend.core.scanner import ScannerService

# Mock mutagen


@pytest.mark.asyncio
async def test_extract_metadata_mp3():
    # Define a Mock class that behaves like a dict and a type
    class MockEasyID3(dict):
        def __init__(self, *args, **kwargs):
            self.update(
                {
                    "title": ["Test Title"],
                    "artist": ["Test Artist"],
                    "album": ["Test Album"],
                    "albumartist": ["Test Album Artist"],
                    "composer": ["Test Composer"],
                    "tracknumber": ["1/10"],
                    "length": ["180"],
                }
            )

    # Patch EasyID3 inside scanner module usage with the Mock CLASS, not an instance
    with patch("backend.core.scanner.EasyID3", MockEasyID3):
        with patch("backend.core.scanner.os.path.getsize", return_value=12345):
            scanner = ScannerService()

            # Create a dummy file path
            dummy_path = "/tmp/test.mp3"

            # Execute
            meta = scanner._extract_metadata(dummy_path)

            # Verify
            assert meta["codec"] == "mp3"
            assert meta["title"] == "Test Title"
            assert meta["artist"] == "Test Artist"
            assert meta["album_artist"] == "Test Album Artist"
            assert meta["composer"] == "Test Composer"
            assert meta["track_num"] == "1/10"
            assert meta["duration"] == 180
            # Note: size removed from plan, so checks for size in scanner not needed if we reverted it.
            # But wait, did I remove size from scanner.py?
            # I checked scanner.py update in step 63, it only touched duration logic.
            # I did NOT remove size calculation if it was already there?
            # Actually, I never added size calculation to scanner.py because I updated the plan to remove it BEFORE implementing it.
            # So size should NOT be in meta.


@pytest.mark.asyncio
async def test_extract_metadata_mp4():
    # Setup mocks
    mock_mp4 = MagicMock()
    mock_tags = {
        "\xa9nam": ["MP4 Title"],
        "\xa9ART": ["MP4 Artist"],
        "trkn": [(2, 12)],
    }
    mock_mp4_instance = MagicMock()
    mock_mp4_instance.tags = mock_tags
    mock_mp4_instance.info.length = 200.5
    mock_mp4.return_value = mock_mp4_instance

    with patch("backend.core.scanner.MP4", mock_mp4):
        scanner = ScannerService()
        dummy_path = "/tmp/test.mp4"

        meta = scanner._extract_metadata(dummy_path)

        assert meta["codec"] == "mp4"
        assert meta["title"] == "MP4 Title"
        assert meta["artist"] == "MP4 Artist"
        assert meta["track_num"] == "2/12"
        assert meta["duration"] == 200  # int conversion
