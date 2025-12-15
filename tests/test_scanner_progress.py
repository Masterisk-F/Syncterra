
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.core.scanner import ScannerService

class TestScannerProgress(unittest.TestCase):
    def setUp(self):
        self.scanner = ScannerService()

    @patch("backend.core.scanner.AsyncSessionLocal")
    @patch("backend.core.scanner.run_in_threadpool")
    def test_run_scan_progress_and_logs(self, mock_run_in_threadpool, mock_session_local):
        # Mock database session
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        # Mock settings
        self.scanner.load_settings = AsyncMock()
        self.scanner._get_setting = MagicMock(side_effect=lambda k, d=None: {
            "scan_paths": '["/tmp/music"]',
            "target_exts": "mp3",
            "exclude_dirs": ""
        }.get(k, d))

        # Mock existing tracks (empty to trigger added count)
        result_mock = MagicMock()
        result_mock.scalars().all.return_value = []
        mock_db.execute.return_value = result_mock

        # Mock filesystem scan results (20 files to test 5% increments easily)
        # Actually 20 files -> 5% is 1 file. Let's do 10 files -> 10% per file.
        # User requested 5% updates.
        fake_files = []
        for i in range(20):
            fake_files.append((f"/tmp/music/song{i}.mp3", f"song{i}.mp3", 1000 + i))
        
        # side_effect for run_in_threadpool to handle multiple calls
        # 1. _scan_filesystem
        # 2...N. _extract_metadata (called for each file)
        
        async def side_effect(func, *args, **kwargs):
            if func == self.scanner._scan_filesystem:
                return fake_files
            elif func == self.scanner._extract_metadata:
                return {"title": "Test Title"}
            return None
            
        mock_run_in_threadpool.side_effect = side_effect

        # Callbacks
        progress_callback = MagicMock()
        log_callback = MagicMock()

        # Mock db.add to be synchronous as SQLAlchemy's session.add is sync
        mock_db.add = MagicMock()

        # Run scan
        asyncio.run(self.scanner.run_scan(progress_callback=progress_callback, log_callback=log_callback))

        # Assertions
        
        # Verify progress callback called
        # Should be called at least for 0, 5, 10 ... 100%
        # With 20 files, every file is 5%. So it should be called 20 times + maybe initial/final?
        self.assertTrue(progress_callback.call_count >= 20)
        
        # Check if last call was 100
        progress_callback.assert_called_with(100)
        
        # Verify log callback called for added files + start/complete
        # 20 files + Start + Complete = 22
        self.assertEqual(log_callback.call_count, 22)
        log_callback.assert_any_call("New file added: /tmp/music/song0.mp3")

if __name__ == "__main__":
    unittest.main()
