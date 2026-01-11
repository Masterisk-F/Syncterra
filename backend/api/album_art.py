from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.albumart_database import get_albumart_db
from ..db.albumart_models import AlbumArt

router = APIRouter(prefix="/api/album-arts", tags=["album-arts"])

@router.get("/{album_name}")
async def get_album_art(
    album_name: str,
    db: AsyncSession = Depends(get_albumart_db)
):
    """
    Get album art image for the given album name.
    """
    if not album_name:
        raise HTTPException(status_code=404, detail="Album name required")

    norm_name = album_name.lower().strip()
    result = await db.execute(
        select(AlbumArt).where(AlbumArt.album_normalized == norm_name)
    )
    album_art = result.scalars().first()

    if not album_art or not album_art.image_data:
        # Return 404 so frontend can show placeholder
        raise HTTPException(status_code=404, detail="Album art not found")

    # Return image data
    return Response(content=album_art.image_data, media_type="image/jpeg")
