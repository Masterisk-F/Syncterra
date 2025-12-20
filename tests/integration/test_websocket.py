from backend.main import app
from fastapi.testclient import TestClient

# WebSocket testing usually needs TestClient (sync) or specific async support.
# FastAPI TestClient supports websocket.


def test_websocket():
    client = TestClient(app)
    with client.websocket_connect("/ws/status") as websocket:
        # Just connect check
        pass
