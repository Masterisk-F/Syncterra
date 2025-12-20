"""
プレイリストAPIのユニットテスト

各APIエンドポイントの基本動作、バリデーション、境界値をテスト
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from backend.api.playlists import (
    get_playlists,
    create_playlist,
    get_playlist,
    update_playlist,
    delete_playlist,
    update_playlist_tracks,
    PlaylistCreate,
    PlaylistUpdate,
    PlaylistTracksUpdate,
)


class TestGetPlaylists:
    """プレイリスト一覧取得のテスト"""

    @pytest.mark.asyncio
    async def test_get_playlists_empty(self):
        """空のプレイリスト一覧を取得"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await get_playlists(db=mock_db)

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_playlists_with_data(self):
        """プレイリストが存在する場合"""
        mock_db = AsyncMock()

        # モックプレイリストを作成
        mock_playlist = MagicMock()
        mock_playlist.id = 1
        mock_playlist.name = "Test Playlist"
        mock_playlist.tracks = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [
            mock_playlist
        ]
        mock_db.execute.return_value = mock_result

        result = await get_playlists(db=mock_db)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "Test Playlist"
        assert result[0].tracks == []


class TestCreatePlaylist:
    """プレイリスト作成のテスト"""

    @pytest.mark.asyncio
    async def test_create_playlist_success(self):
        """正常なプレイリスト作成"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None  # 重複なし
        mock_db.execute.return_value = mock_result

        # refresh後のnew_playlist.idが設定されるようにモック
        async def mock_refresh(obj):
            obj.id = 1

        mock_db.refresh.side_effect = mock_refresh

        playlist_data = PlaylistCreate(name="New Playlist")
        result = await create_playlist(playlist_data=playlist_data, db=mock_db)

        assert result.name == "New Playlist"
        assert result.id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_playlist_duplicate_name(self):
        """重複した名前でプレイリスト作成（エラー）"""
        mock_db = AsyncMock()

        # 既存のプレイリストが存在
        mock_existing = MagicMock()
        mock_existing.name = "Existing Playlist"
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_existing
        mock_db.execute.return_value = mock_result

        playlist_data = PlaylistCreate(name="Existing Playlist")

        with pytest.raises(HTTPException) as exc_info:
            await create_playlist(playlist_data=playlist_data, db=mock_db)

        assert exc_info.value.status_code == 400
        assert "既に使用されています" in exc_info.value.detail


class TestGetPlaylist:
    """プレイリスト詳細取得のテスト"""

    @pytest.mark.asyncio
    async def test_get_playlist_success(self):
        """正常なプレイリスト詳細取得"""
        mock_db = AsyncMock()

        mock_track = MagicMock()
        mock_track.id = 1
        mock_track.track_id = 10
        mock_track.order = 0
        mock_track.track.title = "Track 1"
        mock_track.track.artist = "Artist 1"
        mock_track.track.file_name = "track1.mp3"

        mock_playlist = MagicMock()
        mock_playlist.id = 1
        mock_playlist.name = "Test Playlist"
        mock_playlist.tracks = [mock_track]

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_playlist
        mock_db.execute.return_value = mock_result

        result = await get_playlist(playlist_id=1, db=mock_db)

        assert result.id == 1
        assert result.name == "Test Playlist"
        assert len(result.tracks) == 1

    @pytest.mark.asyncio
    async def test_get_playlist_not_found(self):
        """存在しないプレイリストを取得（エラー）"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_playlist(playlist_id=999, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "見つかりません" in exc_info.value.detail


class TestUpdatePlaylist:
    """プレイリスト更新のテスト"""

    @pytest.mark.asyncio
    async def test_update_playlist_name_success(self):
        """プレイリスト名の正常な更新"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1
        mock_playlist.name = "Old Name"

        # 対象プレイリスト取得
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.first.return_value = mock_playlist

        # 重複チェック（なし）
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.first.return_value = None

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        update_data = PlaylistUpdate(name="New Name")
        result = await update_playlist(
            playlist_id=1, update_data=update_data, db=mock_db
        )

        assert result["status"] == "ok"
        assert mock_playlist.name == "New Name"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_playlist_duplicate_name(self):
        """重複した名前に更新（エラー）"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1
        mock_playlist.name = "Playlist 1"

        mock_existing = MagicMock()
        mock_existing.id = 2
        mock_existing.name = "Playlist 2"

        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.first.return_value = mock_playlist

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.first.return_value = mock_existing

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        update_data = PlaylistUpdate(name="Playlist 2")

        with pytest.raises(HTTPException) as exc_info:
            await update_playlist(playlist_id=1, update_data=update_data, db=mock_db)

        assert exc_info.value.status_code == 400


class TestDeletePlaylist:
    """プレイリスト削除のテスト"""

    @pytest.mark.asyncio
    async def test_delete_playlist_success(self):
        """プレイリストの正常な削除"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_playlist
        mock_db.execute.return_value = mock_result

        result = await delete_playlist(playlist_id=1, db=mock_db)

        assert result["status"] == "ok"
        assert result["id"] == 1
        mock_db.delete.assert_called_once_with(mock_playlist)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_playlist_not_found(self):
        """存在しないプレイリストを削除（エラー）"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_playlist(playlist_id=999, db=mock_db)

        assert exc_info.value.status_code == 404


class TestUpdatePlaylistTracks:
    """プレイリスト内の曲更新のテスト"""

    @pytest.mark.asyncio
    async def test_update_playlist_tracks_success(self):
        """曲リストの正常な更新"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1

        mock_track1 = MagicMock()
        mock_track1.id = 10

        mock_track2 = MagicMock()
        mock_track2.id = 20

        # プレイリスト取得
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.first.return_value = mock_playlist

        # トラック存在確認
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_track1, mock_track2]

        # 既存のプレイリストトラック取得
        mock_result3 = MagicMock()
        mock_result3.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        tracks_update = PlaylistTracksUpdate(track_ids=[10, 20])
        result = await update_playlist_tracks(
            playlist_id=1, tracks_update=tracks_update, db=mock_db
        )

        assert result["status"] == "ok"
        assert result["track_count"] == 2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_playlist_tracks_empty(self):
        """空の曲リストで更新（全削除）"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1

        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.first.return_value = mock_playlist

        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        tracks_update = PlaylistTracksUpdate(track_ids=[])
        result = await update_playlist_tracks(
            playlist_id=1, tracks_update=tracks_update, db=mock_db
        )

        assert result["status"] == "ok"
        assert result["track_count"] == 0

    @pytest.mark.asyncio
    async def test_update_playlist_tracks_invalid_track_ids(self):
        """存在しないトラックIDを指定（エラー）"""
        mock_db = AsyncMock()

        mock_playlist = MagicMock()
        mock_playlist.id = 1

        mock_track = MagicMock()
        mock_track.id = 10

        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.first.return_value = mock_playlist

        # トラック10のみ存在、20は存在しない
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_track]

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        tracks_update = PlaylistTracksUpdate(track_ids=[10, 20])

        with pytest.raises(HTTPException) as exc_info:
            await update_playlist_tracks(
                playlist_id=1, tracks_update=tracks_update, db=mock_db
            )

        assert exc_info.value.status_code == 400
        assert "存在しないトラックID" in exc_info.value.detail
