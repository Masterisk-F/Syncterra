import pytest
import os
import json
from unittest.mock import patch
from sqlalchemy.future import select
from backend.db.models import Setting

# Integration Test: API Flow
# 目的: ユーザー操作(API)がバックエンドの状態を正しく変更するか検証する。

@pytest.mark.asyncio
async def test_api_flow_update_settings(client, temp_db):
    """
    [API] 設定変更フロー
    
    条件:
    1. PUT /api/settings エンドポイントに設定変更リクエストを送る
    
    期待値:
    1. ステータスコード 200 が返ること
    2. DBの設定値が更新されていること
    """
    # 1. リクエスト実行
    new_settings = {
        "sync_mode": "ssh",
        "target_exts": "flac"
    }
    
    # APIは1つずつ更新する仕様: PUT /api/settings Body: SettingModel
    for key, value in new_settings.items():
        payload = {"key": key, "value": value}
        response = client.put("/api/settings", json=payload)
        assert response.status_code == 200, f"Failed to update {key}"
    
    # 2. 検証
    # DB確認
    for key, val in new_settings.items():
        result = await temp_db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalars().first()
        assert setting is not None
        assert setting.value == val

@pytest.mark.asyncio
async def test_api_flow_manual_scan(client, patch_db_session):
    """
    [API] 手動スキャン実行フロー
    
    条件:
    1. POST /api/scan エンドポイントを叩く
    
    期待値:
    1. ステータスコード 202 (Accepted) または 200 が返ること
    2. バックグラウンドでスキャン処理が開始されること
    """
    from unittest.mock import AsyncMock
    with patch("backend.api.system.ScannerService") as MockScanner:
        mock_instance = MockScanner.return_value
        mock_instance.run_scan = AsyncMock()  # AsyncMockでないと await expression エラーになる
        
        # Note: BackgroundTasks wont run immediately in TestClient unless we wait or force it?
        # Actually Starlette TestClient runs background tasks after response.
        response = client.post("/api/scan")
        
        assert response.status_code == 200
        # Check calling
        mock_instance.run_scan.assert_called_once()

@pytest.mark.asyncio
async def test_api_flow_manual_sync(client, patch_db_session):
    """
    [API] 手動同期実行フロー
    
    条件:
    1. POST /api/sync エンドポイントを叩く
    
    期待値:
    1. ステータスコード 200 が返ること
    2. SyncService.run_sync() が呼び出されること
    """
    with patch("backend.api.system.SyncService.run_sync") as mock_run_sync:
        response = client.post("/api/sync")
        
        assert response.status_code == 200
        mock_run_sync.assert_called_once()
