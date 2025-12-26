from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..db.database import get_db
from ..db.models import Track

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


class TrackModel(BaseModel):
    id: int
    file_path: str
    file_name: str
    title: Optional[str]
    artist: Optional[str]
    album: Optional[str]
    sync: bool
    relative_path: Optional[str]
    msg: Optional[str]
    missing: bool = False

    # Missing fields
    duration: Optional[int] = None
    codec: Optional[str] = None
    track_num: Optional[str] = None
    album_artist: Optional[str] = None
    composer: Optional[str] = None
    added_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrackUpdate(BaseModel):
    sync: Optional[bool] = None


class BatchTrackUpdate(BaseModel):
    ids: List[int]
    sync: bool


@router.get("", response_model=List[TrackModel])
async def get_tracks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Track))
    return result.scalars().all()


@router.put("/batch")
async def batch_update_tracks(
    batch: BatchTrackUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Track).where(Track.id.in_(batch.ids)))
    tracks = result.scalars().all()
    for track in tracks:
        track.sync = batch.sync
    await db.commit()
    return {"status": "ok", "updated_count": len(tracks)}


@router.put("/{id}")
async def update_track(
    id: int, update: TrackUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Track).where(Track.id == id))
    track = result.scalars().first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if update.sync is not None:
        track.sync = update.sync

    await db.commit()
    return {"status": "ok", "id": id}


@router.delete("/missing")
async def delete_missing_tracks(db: AsyncSession = Depends(get_db)):
    # missing=True のレコードを削除する
    result = await db.execute(delete(Track).where(Track.missing == True))
    await db.commit()
    return {"status": "ok", "deleted_count": result.rowcount}
