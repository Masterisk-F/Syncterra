from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from ..db.database import get_db
from ..db.models import Playlist, PlaylistTrack, Track

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# Pydanticモデル定義


class TrackInPlaylist(BaseModel):
    """プレイリスト内の曲情報"""

    id: int
    track_id: int
    order: int
    title: Optional[str]
    artist: Optional[str]
    file_name: str

    # Extended metadata for UI
    album: Optional[str] = None
    album_artist: Optional[str] = None
    composer: Optional[str] = None
    track_num: Optional[str] = None
    duration: Optional[int] = None
    codec: Optional[str] = None
    added_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlaylistModel(BaseModel):
    """プレイリストモデル（レスポンス用）"""

    id: int
    name: str
    tracks: List[TrackInPlaylist] = []

    class Config:
        from_attributes = True


class PlaylistCreate(BaseModel):
    """プレイリスト作成リクエスト"""

    name: str


class PlaylistUpdate(BaseModel):
    """プレイリスト更新リクエスト"""

    name: Optional[str] = None


class PlaylistTracksUpdate(BaseModel):
    """プレイリスト内の曲の一括更新リクエスト"""

    track_ids: List[int]


# APIエンドポイント


@router.get("", response_model=List[PlaylistModel])
async def get_playlists(db: AsyncSession = Depends(get_db)):
    """プレイリスト一覧を取得"""
    result = await db.execute(
        select(Playlist).options(
            joinedload(Playlist.tracks).joinedload(PlaylistTrack.track)
        )
    )
    playlists = result.scalars().unique().all()

    # レスポンス用にデータを整形
    response = []
    for playlist in playlists:
        tracks_data = []
        # order順にソート
        sorted_tracks = sorted(playlist.tracks, key=lambda x: x.order)
        for pt in sorted_tracks:
            tracks_data.append(
                TrackInPlaylist(
                    id=pt.id,
                    track_id=pt.track_id,
                    order=pt.order,
                    title=pt.track.title,
                    artist=pt.track.artist,
                    file_name=pt.track.file_name,
                    # Extended fields
                    album=pt.track.album,
                    album_artist=pt.track.album_artist,
                    composer=pt.track.composer,
                    track_num=pt.track.track_num,
                    duration=pt.track.duration,
                    codec=pt.track.codec,
                    added_date=pt.track.added_date,
                    last_modified=pt.track.last_modified,
                )
            )
        response.append(
            PlaylistModel(id=playlist.id, name=playlist.name, tracks=tracks_data)
        )

    return response


@router.post("", response_model=PlaylistModel)
async def create_playlist(
    playlist_data: PlaylistCreate, db: AsyncSession = Depends(get_db)
):
    """プレイリストを新規作成"""
    # 重複チェック
    result = await db.execute(
        select(Playlist).where(Playlist.name == playlist_data.name)
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=400, detail="このプレイリスト名は既に使用されています"
        )

    # 新規作成
    new_playlist = Playlist(name=playlist_data.name)
    db.add(new_playlist)
    await db.commit()
    await db.refresh(new_playlist)

    return PlaylistModel(id=new_playlist.id, name=new_playlist.name, tracks=[])


@router.get("/{playlist_id}", response_model=PlaylistModel)
async def get_playlist(playlist_id: int, db: AsyncSession = Depends(get_db)):
    """プレイリスト詳細を取得"""
    result = await db.execute(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(joinedload(Playlist.tracks).joinedload(PlaylistTrack.track))
    )
    playlist = result.scalars().first()

    if not playlist:
        raise HTTPException(status_code=404, detail="プレイリストが見つかりません")

    # レスポンス用にデータを整形
    tracks_data = []
    sorted_tracks = sorted(playlist.tracks, key=lambda x: x.order)
    for pt in sorted_tracks:
        tracks_data.append(
            TrackInPlaylist(
                id=pt.id,
                track_id=pt.track_id,
                order=pt.order,
                title=pt.track.title,
                artist=pt.track.artist,
                file_name=pt.track.file_name,
                # Extended fields
                album=pt.track.album,
                album_artist=pt.track.album_artist,
                composer=pt.track.composer,
                track_num=pt.track.track_num,
                duration=pt.track.duration,
                codec=pt.track.codec,
                added_date=pt.track.added_date,
                last_modified=pt.track.last_modified,
            )
        )

    return PlaylistModel(id=playlist.id, name=playlist.name, tracks=tracks_data)


@router.put("/{playlist_id}")
async def update_playlist(
    playlist_id: int, update_data: PlaylistUpdate, db: AsyncSession = Depends(get_db)
):
    """プレイリスト名を更新"""
    result = await db.execute(select(Playlist).where(Playlist.id == playlist_id))
    playlist = result.scalars().first()

    if not playlist:
        raise HTTPException(status_code=404, detail="プレイリストが見つかりません")

    if update_data.name is not None:
        # 重複チェック（自分自身以外）
        result = await db.execute(
            select(Playlist).where(
                Playlist.name == update_data.name, Playlist.id != playlist_id
            )
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=400, detail="このプレイリスト名は既に使用されています"
            )

        playlist.name = update_data.name

    await db.commit()
    return {"status": "ok", "id": playlist_id}


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int, db: AsyncSession = Depends(get_db)):
    """プレイリストを削除"""
    result = await db.execute(select(Playlist).where(Playlist.id == playlist_id))
    playlist = result.scalars().first()

    if not playlist:
        raise HTTPException(status_code=404, detail="プレイリストが見つかりません")

    await db.delete(playlist)
    await db.commit()
    return {"status": "ok", "id": playlist_id}


@router.put("/{playlist_id}/tracks")
async def update_playlist_tracks(
    playlist_id: int,
    tracks_update: PlaylistTracksUpdate,
    db: AsyncSession = Depends(get_db),
):
    """プレイリスト内の曲を一括更新（順序変更、追加、削除）"""
    # プレイリストの存在確認
    result = await db.execute(select(Playlist).where(Playlist.id == playlist_id))
    playlist = result.scalars().first()

    if not playlist:
        raise HTTPException(status_code=404, detail="プレイリストが見つかりません")

    # 指定されたtrack_idが全て存在するか確認
    if tracks_update.track_ids:
        result = await db.execute(
            select(Track).where(Track.id.in_(tracks_update.track_ids))
        )
        existing_tracks = result.scalars().all()
        existing_track_ids = {track.id for track in existing_tracks}

        invalid_ids = set(tracks_update.track_ids) - existing_track_ids
        if invalid_ids:
            raise HTTPException(
                status_code=400, detail=f"存在しないトラックID: {list(invalid_ids)}"
            )

    # 既存のプレイリストトラックを全て削除
    result = await db.execute(
        select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
    )
    existing_playlist_tracks = result.scalars().all()
    for pt in existing_playlist_tracks:
        await db.delete(pt)

    # 新しいプレイリストトラックを追加（順序を保持）
    for order, track_id in enumerate(tracks_update.track_ids):
        new_pt = PlaylistTrack(playlist_id=playlist_id, track_id=track_id, order=order)
        db.add(new_pt)

    await db.commit()
    return {
        "status": "ok",
        "playlist_id": playlist_id,
        "track_count": len(tracks_update.track_ids),
    }
