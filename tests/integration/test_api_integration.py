import pytest
from backend.db.models import Setting

@pytest.mark.asyncio
async def test_api_settings_crud(client, temp_db):
    """Test scenario 1: Settings CRUD"""
    # Create setting
    response = client.put("/api/settings", json={"key": "test_key", "value": "test_val"})
    assert response.status_code == 200
    assert response.json()["value"] == "test_val"

    # Read setting
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert any(s["key"] == "test_key" and s["value"] == "test_val" for s in data)
    
    # Update setting
    response = client.put("/api/settings", json={"key": "test_key", "value": "updated_val"})
    assert response.status_code == 200
    
    # Verify persistence
    response = client.get("/api/settings")
    data = response.json()
    assert any(s["key"] == "test_key" and s["value"] == "updated_val" for s in data)

@pytest.mark.asyncio
async def test_api_trigger_scan(client):
    """Test scenario 2: Trigger Scan Endpoint"""
    # We mock background tasks to not run actual scan in API test if speed is concern,
    # but for integration we might want to check it accepts it.
    # FastAPI BackgroundTask runs after response.
    # We just check 200/202 status.
    
    from unittest.mock import patch
    with patch("backend.api.system.scan_task") as mock_task: 
        # Note: BackgroundTasks adding is hard to patch directly in dispatch,
        # but we can patch the task function itself if it's imported in the router.
        # Ideally, we verify response is accepted.
        pass
        
    response = client.post("/api/scan")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

@pytest.mark.asyncio
async def test_api_trigger_sync(client):
    """Test scenario 3: Trigger Sync Endpoint"""
    response = client.post("/api/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
