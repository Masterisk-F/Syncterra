from fastapi.testclient import TestClient

from backend.main import app

# Integration Test: WebSocket
# 目的: WebSocketエンドポイント(/ws/status)への接続が正常に確立されるか検証する。


def test_websocket():
    """
    [WebSocket] 接続確立確認

    条件:
    1. WebSocket /ws/status への接続を試みる

    期待値:
    1. 接続がエラーなく確立されること
    2. 接続を正常に切断できること

    備考:
    この検証により、WebSocketエンドポイントが正しく設定されており、
    クライアントからの接続を受け付けられることを確認する。
    """
    client = TestClient(app)
    with client.websocket_connect("/ws/status") as websocket:
        # Just connect check
        pass
