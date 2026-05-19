import pytest
from sqlalchemy import select

from backend.db.models import Playlist, PlaylistTrack, Track


@pytest.mark.asyncio
async def test_track_deletion_cascades_to_playlist_track(temp_db):
    """
    [Integration - Database] トラック削除に伴うPlaylistTrackのカスケード削除の検証

    条件:
    1. DBにTrackとPlaylistが登録され、PlaylistTrackで紐づいている
    2. TrackをDBから直接削除する

    検証項目:
    1. PlaylistTrackテーブルから該当レコードが自動的に削除されていること（SQLiteのPRAGMA foreign_keys=ON と CASCADE設定の検証）
    """
    # 1. Setup Data
    track = Track(
        file_path="/music/cascade_test.mp3",
        relative_path="cascade_test.mp3",
        file_name="cascade_test",
        title="Cascade Test",
        size=1024,
    )
    playlist = Playlist(name="Cascade Test Playlist")

    temp_db.add_all([track, playlist])
    await temp_db.commit()
    await temp_db.refresh(track)
    await temp_db.refresh(playlist)

    # PlaylistTrackを追加
    pt = PlaylistTrack(playlist_id=playlist.id, track_id=track.id, order=0)
    temp_db.add(pt)
    await temp_db.commit()
    await temp_db.refresh(pt)

    pt_id = pt.id

    # 2. Verify setup
    result = await temp_db.execute(select(PlaylistTrack).where(PlaylistTrack.id == pt_id))
    assert result.scalar() is not None

    # 3. Delete Track
    await temp_db.delete(track)
    await temp_db.commit()

    # 4. Verify Cascade Deletion
    # PlaylistTrack should be automatically deleted
    result = await temp_db.execute(select(PlaylistTrack).where(PlaylistTrack.id == pt_id))
    assert result.scalar() is None
