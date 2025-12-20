"""
プレイリストAPIのインテグレーションテスト

実際のデータベースを使用してAPI全体の動作を検証
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.database import init_db
from backend.db.models import Playlist, PlaylistTrack, Track
import pytest_asyncio
from sqlalchemy import delete


@pytest_asyncio.fixture(scope="function")
async def client():
    """テスト用HTTPクライアント"""
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def seed_data():
    """テスト用のトラックとプレイリストをセットアップ"""
    from backend.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # 既存データクリア
        await session.execute(delete(PlaylistTrack))
        await session.execute(delete(Playlist))
        await session.execute(delete(Track))

        # トラック作成
        t1 = Track(
            file_path="/music/track1.mp3",
            relative_path="track1.mp3",
            file_name="track1.mp3",
            title="Track 1",
            artist="Artist 1",
            sync=True,
        )
        t2 = Track(
            file_path="/music/track2.mp3",
            relative_path="track2.mp3",
            file_name="track2.mp3",
            title="Track 2",
            artist="Artist 2",
            sync=False,
        )
        session.add(t1)
        session.add(t2)
        await session.commit()
        await session.refresh(t1)
        await session.refresh(t2)
        
        return {"tracks": [t1, t2]}


@pytest.mark.asyncio
async def test_create_playlist(client, seed_data):
    """プレイリストの作成"""
    response = await client.post("/api/playlists", json={"name": "Test Playlist"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Playlist"
    assert data["id"] is not None
    assert data["tracks"] == []


@pytest.mark.asyncio
async def test_create_duplicate_playlist(client, seed_data):
    """重複した名前でプレイリスト作成（エラー）"""
    await client.post("/api/playlists", json={"name": "Duplicate"})
    response = await client.post("/api/playlists", json={"name": "Duplicate"})
    assert response.status_code == 400
    assert "既に使用されています" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_playlists(client, seed_data):
    """プレイリスト一覧の取得"""
    # プレイリスト作成
    await client.post("/api/playlists", json={"name": "Playlist 1"})
    await client.post("/api/playlists", json={"name": "Playlist 2"})

    response = await client.get("/api/playlists")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    names = [p["name"] for p in data]
    assert "Playlist 1" in names
    assert "Playlist 2" in names


@pytest.mark.asyncio
async def test_get_playlist_by_id(client, seed_data):
    """プレイリスト詳細の取得"""
    create_response = await client.post(
        "/api/playlists", json={"name": "Detail Test"}
    )
    playlist_id = create_response.json()["id"]

    response = await client.get(f"/api/playlists/{playlist_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detail Test"
    assert data["id"] == playlist_id


@pytest.mark.asyncio
async def test_get_nonexistent_playlist(client, seed_data):
    """存在しないプレイリストの取得（エラー）"""
    response = await client.get("/api/playlists/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_playlist_name(client, seed_data):
    """プレイリスト名の更新"""
    create_response = await client.post(
        "/api/playlists", json={"name": "Old Name"}
    )
    playlist_id = create_response.json()["id"]

    response = await client.put(
        f"/api/playlists/{playlist_id}", json={"name": "New Name"}
    )
    assert response.status_code == 200

    # 確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    assert get_response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_playlist(client, seed_data):
    """プレイリストの削除"""
    create_response = await client.post(
        "/api/playlists", json={"name": "To Delete"}
    )
    playlist_id = create_response.json()["id"]

    response = await client.delete(f"/api/playlists/{playlist_id}")
    assert response.status_code == 200

    # 削除確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_add_tracks_to_playlist(client, seed_data):
    """プレイリストに曲を追加"""
    tracks = seed_data["tracks"]
    
    # プレイリスト作成
    create_response = await client.post(
        "/api/playlists", json={"name": "With Tracks"}
    )
    playlist_id = create_response.json()["id"]

    # 曲を追加
    track_ids = [t.id for t in tracks]
    response = await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": track_ids}
    )
    assert response.status_code == 200
    assert response.json()["track_count"] == 2

    # 確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    playlist_data = get_response.json()
    assert len(playlist_data["tracks"]) == 2
    assert playlist_data["tracks"][0]["order"] == 0
    assert playlist_data["tracks"][1]["order"] == 1


@pytest.mark.asyncio
async def test_reorder_playlist_tracks(client, seed_data):
    """プレイリスト内の曲の順序変更"""
    tracks = seed_data["tracks"]
    
    # プレイリスト作成と曲追加
    create_response = await client.post(
        "/api/playlists", json={"name": "Reorder Test"}
    )
    playlist_id = create_response.json()["id"]
    
    track_ids = [t.id for t in tracks]
    await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": track_ids}
    )

    # 順序を逆にする
    reversed_ids = list(reversed(track_ids))
    response = await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": reversed_ids}
    )
    assert response.status_code == 200

    # 確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    playlist_data = get_response.json()
    assert playlist_data["tracks"][0]["track_id"] == reversed_ids[0]
    assert playlist_data["tracks"][1]["track_id"] == reversed_ids[1]


@pytest.mark.asyncio
async def test_remove_tracks_from_playlist(client, seed_data):
    """プレイリストから曲を削除"""
    tracks = seed_data["tracks"]
    
    # プレイリスト作成と曲追加
    create_response = await client.post(
        "/api/playlists", json={"name": "Remove Test"}
    )
    playlist_id = create_response.json()["id"]
    
    track_ids = [t.id for t in tracks]
    await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": track_ids}
    )

    # 1つだけ残す
    response = await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": [track_ids[0]]}
    )
    assert response.status_code == 200
    assert response.json()["track_count"] == 1

    # 確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    playlist_data = get_response.json()
    assert len(playlist_data["tracks"]) == 1


@pytest.mark.asyncio
async def test_clear_playlist_tracks(client, seed_data):
    """プレイリストの全曲削除"""
    tracks = seed_data["tracks"]
    
    # プレイリスト作成と曲追加
    create_response = await client.post(
        "/api/playlists", json={"name": "Clear Test"}
    )
    playlist_id = create_response.json()["id"]
    
    track_ids = [t.id for t in tracks]
    await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": track_ids}
    )

    # 全削除
    response = await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": []}
    )
    assert response.status_code == 200
    assert response.json()["track_count"] == 0

    # 確認
    get_response = await client.get(f"/api/playlists/{playlist_id}")
    playlist_data = get_response.json()
    assert len(playlist_data["tracks"]) == 0


@pytest.mark.asyncio
async def test_add_invalid_track_ids(client, seed_data):
    """存在しないトラックIDを追加（エラー）"""
    create_response = await client.post(
        "/api/playlists", json={"name": "Invalid Tracks"}
    )
    playlist_id = create_response.json()["id"]

    response = await client.put(
        f"/api/playlists/{playlist_id}/tracks", json={"track_ids": [9999, 10000]}
    )
    assert response.status_code == 400
    assert "存在しないトラックID" in response.json()["detail"]
