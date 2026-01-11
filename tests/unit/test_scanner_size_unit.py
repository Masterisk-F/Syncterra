from unittest.mock import MagicMock, patch

import pytest

from backend.core.scanner import ScannerService

# Unit Test: ScannerService Size Extraction
# 目的: メタデータ抽出時にファイルサイズが正しく取得されるか検証する


@pytest.fixture
def mock_scanner():
    return ScannerService()


def test_extract_metadata_size(mock_scanner, tmp_path):
    # Setup dummy file with known size
    test_file = tmp_path / "test__size.mp3"
    content = b"0123456789" * 10  # 100 bytes
    test_file.write_bytes(content)

    file_path = str(test_file)
    expected_size = 100

    # Mock mutagen classes used in scanner.py
    # We use a dummy file content, so real parsing would fail.
    # We just want to ensure _extract_metadata gets the size from os.path.getsize logic.
    with patch("backend.core.scanner.EasyID3") as mock_easyid3:
        # Mock successful tag reading
        mock_id3_instance = MagicMock()
        mock_id3_instance.get.return_value = None  # Default for safe gets
        mock_easyid3.return_value = mock_id3_instance

        # Execute
        metadata = mock_scanner._extract_metadata(file_path)

        # Verify
        assert "size" in metadata
        assert metadata["size"] == expected_size

        # Ensure we actually called os.path.getsize via the logic (implicit by result)
        # But we can also check if metadata covers other fields as None
        assert metadata["codec"] == "mp3"
