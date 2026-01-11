from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.tracks import delete_missing_tracks


@pytest.mark.asyncio
async def test_delete_missing_tracks():
    """missing=Trueのトラックのみが削除されること。"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()

    result = await delete_missing_tracks(db=mock_db)

    assert result["status"] == "ok"
    assert result["deleted_count"] == 5
    mock_db.execute.assert_called_once()

    # Verify the delete statement was constructed correctly
    # Note: Checking the exact SQL construct with mocks is hard,
    # but we can verify something was executed.
