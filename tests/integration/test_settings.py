import pytest
from backend.main import app
import pytest_asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from backend.db.models import Setting

# Integration Test: Settings API
# 目的: 設定APIエンドポイントが正しく動作するか検証する。



@pytest.mark.asyncio
async def test_get_settings_empty(client):
    """
    [Settings API] 設定が空の状態での取得
    
    条件:
    1. DBに設定が1件も存在しない
    2. GET /api/settings を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. 空のリスト [] が返ること
    """
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_update_setting(client):
    """
    [Settings API] 新規設定の追加
    
    条件:
    1. 存在しないキーで PUT /api/settings を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. レスポンスに status: ok が含まれること
    3. GET で取得したデータに追加した設定が含まれること
    """
    response = client.put(
        "/api/settings", json={"key": "test_key", "value": "test_val"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["key"] == "test_key"
    assert data[0]["value"] == "test_val"


@pytest.mark.asyncio
async def test_update_existing_setting(client):
    """
    [Settings API] 既存設定の更新
    
    条件:
    1. 一度設定を追加する
    2. 同じキーで異なる値をPUT
    
    期待値:
    1. ステータスコード 200 が返ること
    2. GET で取得した値が更新後の値になっていること
    """
    # Setup initial state
    client.put("/api/settings", json={"key": "test_key", "value": "initial_val"})
    
    response = client.put(
        "/api/settings", json={"key": "test_key", "value": "updated_val"}
    )
    assert response.status_code == 200

    response = client.get("/api/settings")
    data = response.json()
    assert data[0]["value"] == "updated_val"


@pytest.mark.asyncio
async def test_get_public_key_generate_new(client, temp_db):
    """
    [Settings API] SSH公開鍵の新規生成と取得
    
    条件:
    1. 鍵ファイルが存在しない状態
    2. rsync_user, rsync_hostの設定が存在する
    3. GET /api/settings/ssh-key/public を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. 生成された公開鍵の内容が返ること
    3. DBの設定(rsync_key_path)が更新されていること
    4. ssh-keygenコマンドに適切なコメント(-C user@host)が渡されること
    """
    
    # 事前設定の投入
    temp_db.add(Setting(key="rsync_user", value="test_user"))
    temp_db.add(Setting(key="rsync_host", value="test_host"))
    await temp_db.commit()

    # モック用の公開鍵コンテンツ
    mock_pub_key_content = "ssh-rsa MOCK_PUBLIC_KEY syncterra@localhost"
    
    # 既存の定数をパッチするための一時ディレクトリ作成
    with tempfile.TemporaryDirectory() as tmpdir:
        ssh_dir = os.path.join(tmpdir, ".ssh")
        priv_key = os.path.join(ssh_dir, "syncterra_rsa")
        pub_key = os.path.join(ssh_dir, "syncterra_rsa.pub")
        
        # モック設定
        with patch("backend.api.settings.SSH_KEY_DIR", ssh_dir), \
             patch("backend.api.settings.SSH_PRIVATE_KEY_PATH", priv_key), \
             patch("backend.api.settings.SSH_PUBLIC_KEY_PATH", pub_key), \
             patch("subprocess.run") as mock_run:
            
            # subprocess.runの副作用として鍵ファイルを生成する関数
            def side_effect(cmd, **kwargs):
                if not os.path.exists(ssh_dir):
                    os.makedirs(ssh_dir)
                    
                # コメント引数の検証
                expected_comment = "test_user@test_host"
                if "-C" in cmd:
                    idx = cmd.index("-C")
                    if idx + 1 < len(cmd):
                        actual_comment = cmd[idx+1]
                        assert actual_comment == expected_comment, f"Expected comment {expected_comment}, got {actual_comment}"

                # ファイル生成をシミュレート
                with open(priv_key, "w") as f:
                    f.write("MOCK_PRIVATE_KEY")
                with open(pub_key, "w") as f:
                    f.write(mock_pub_key_content)
                return MagicMock(returncode=0)

            mock_run.side_effect = side_effect
            
            # API実行
            response = client.get("/api/settings/ssh-key/public")
            
            # 検証
            assert response.status_code == 200
            assert response.text == mock_pub_key_content
            
            # DB更新確認
            result = await temp_db.execute(select(Setting).where(Setting.key == "rsync_key_path"))
            setting = result.scalars().first()
            assert setting is not None
            assert setting.value == priv_key

            # ssh-keygenが呼ばれたことの確認
            mock_run.assert_called()


@pytest.mark.asyncio
async def test_get_public_key_existing(client):
    """
    [Settings API] 既存のSSH公開鍵の取得
    
    条件:
    1. 鍵ファイルが既に存在する状態
    2. GET /api/settings/ssh-key/public を実行
    
    期待値:
    1. ステータスコード 200 が返ること
    2. 既存の公開鍵の内容が返ること
    3. ssh-keygenコマンドが実行されないこと
    """
    
    existing_pub_key = "ssh-rsa EXISTING_KEY syncterra@localhost"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        ssh_dir = os.path.join(tmpdir, ".ssh")
        os.makedirs(ssh_dir)
        priv_key = os.path.join(ssh_dir, "syncterra_rsa")
        pub_key = os.path.join(ssh_dir, "syncterra_rsa.pub")
        
        # 鍵ファイル作成
        with open(priv_key, "w") as f:
            f.write("EXISTING_PRIVATE_KEY")
        with open(pub_key, "w") as f:
            f.write(existing_pub_key)
            
        # モック設定
        with patch("backend.api.settings.SSH_KEY_DIR", ssh_dir), \
             patch("backend.api.settings.SSH_PRIVATE_KEY_PATH", priv_key), \
             patch("backend.api.settings.SSH_PUBLIC_KEY_PATH", pub_key), \
             patch("subprocess.run") as mock_run:
            
            # API実行
            response = client.get("/api/settings/ssh-key/public")
            
            # 検証
            assert response.status_code == 200
            assert response.text == existing_pub_key
            
            # ssh-keygenは呼ばれないはず
            mock_run.assert_not_called()

