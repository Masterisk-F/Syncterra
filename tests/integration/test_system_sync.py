from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch
from fastapi.concurrency import run_in_threadpool
import time

# Integration Test: System Sync WebSocket Streaming
# 目的: 同期処理中のログがWebSocket経由でリアルタイムに配信されるか検証する。

# Use TestClient for WebSocket support
client = TestClient(app)


def test_sync_log_streaming():
    """
    [System API] 同期ログのWebSocketストリーミング
    
    条件:
    1. WebSocket /ws/status に接続
    2. POST /api/sync で同期処理を開始
    3. 同期処理中にログコールバックが呼ばれる
    
    期待値:
    1. WebSocket経由でログメッセージを受信できること
    2. "Test log message" (モックが発行) を受信すること
    3. "Sync complete" を受信すること
    
    備考:
    この検証により、バックグラウンド処理のログがリアルタイムに
    フロントエンドへ配信される仕組みが正常に動作することを確認する。
    """
    # Mock SyncService.run_sync to simulate log callbacks FROM A THREAD
    with patch("backend.api.system.SyncService.run_sync") as mock_run_sync:

        async def mock_implementation(log_callback=None):
            def threaded_action():
                if log_callback:
                    # properly simulate logging from thread
                    try:
                        log_callback("Test log message")
                    except Exception as e:
                        print(f"Callback failed in thread: {e}")

            # Run in threadpool to simulate real behavior
            await run_in_threadpool(threaded_action)

        mock_run_sync.side_effect = mock_implementation

        # Connect to WebSocket
        with client.websocket_connect("/ws/status") as websocket:
            # Trigger sync via POST
            response = client.post("/api/sync")
            assert response.status_code == 200

            # Check for messages
            messages = []

            # Since TestClient is sync, we might need to loop to receive messages
            # But the app processes the request in background task.
            # Background tasks in TestClient might run after response?
            # TestClient context manager handles lifespan.

            # Received messages
            start_time = time.time()
            while time.time() - start_time < 2.0:
                try:
                    # receive_text might block? TestClient WebSocket receive_text is blocking?
                    # No, it checks if message available.
                    # We assume implementation sends it reasonably fast.
                    # But we need to be careful not to block forever if no message.
                    # TestClient.websocket_connect returns a WebSocketTestSession.
                    # receive_text raises generic exception if closed?
                    # Let's try simple receive.
                    msg = websocket.receive_text()
                    messages.append(msg)
                    if msg == "Sync complete":
                        break
                except Exception:
                    # Maybe no message yet? sleep a bit
                    time.sleep(0.1)

            print("Received messages:", messages)

            # Fails if "Test log message" is missing (which happens if RuntimeError occurred in thread)
            assert "Test log message" in messages
            assert "Sync complete" in messages
