import io
import logging
import os
from typing import Optional, Tuple

from fastapi.concurrency import run_in_threadpool
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.albumart_database import AsyncSessionLocal as ArtSessionLocal
from ..db.albumart_models import AlbumArt
from ..db.database import AsyncSessionLocal as MainSessionLocal
from ..db.models import Track

logger = logging.getLogger(__name__)


class AlbumArtScanner:
    def __init__(self):
        self.IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]
        # Priority filenames
        self.ALBUM_ART_FILENAMES = [
            "folder",
            "cover",
            "front",
            "albumart",
            "albumartsmall",
        ]

    async def scan_all(self):
        """
        Scans all albums in the main DB and updates album art in the art DB.
        """
        logger.info("Album Art Scan started")
        
        # 1. Get all albums and their tracks from main DB
        # To avoid huge query, we can query distinct albums or iterate.
        # Collecting all tracks might be heavy for huge libraries, 
        # but for simplicity we fetch meaningful tracks to determine album folders.
        
        # We need to group tracks by album. 
        # Strategy: Select distinct album, album_artist from tracks? 
        # Identifying "Album" identity is tricky if names collide.
        
        # Let's fetch all tracks and group in memory. 
        # If library is massive (100k+), this might need optimization.
        
        async with MainSessionLocal() as session:
            # Fetch minimal data needed
            result = await session.execute(
                select(Track.id, Track.album, Track.file_path, Track.track_num)
                .where(Track.album.isnot(None))
                .where(Track.album != "")
            )
            # We also need file_path to find folder
            tracks = result.all()
            
        # Group by album name (normalized?)
        # Current app logic groups by "Album Name" string. 
        # Collision risk: Two albums named "Greatest Hits" by different artists.
        # Frontend logic: groups by album name. 
        # WE SHOULD FOLLOW FRONTEND LOGIC for consistency.
        # But frontend logic (`AudioListPage.tsx`) groups by `albumName`. 
        # And if collision occurs, they are merged. 
        
        albums_map = {}
        for t in tracks:
            album_name = t.album
            if not album_name:
                continue
                
            norm_name = album_name.lower().strip()
            if norm_name not in albums_map:
                albums_map[norm_name] = {
                    "display_name": album_name,
                    "tracks": []
                }
            albums_map[norm_name]["tracks"].append(t)
            
        logger.info(f"Found {len(albums_map)} albums to process")
            
        async with ArtSessionLocal() as art_session:
            # Verify/Update each album
            for norm_name, data in albums_map.items():
                await self._process_album(art_session, norm_name, data["display_name"], data["tracks"])
            
            await art_session.commit()
            
        logger.info("Album Art Scan finished")

    async def _process_album(self, session: AsyncSession, album_norm: str, album_display: str, tracks: list):
        # 1. Determine best source
        # Sort tracks to find "lowest track number" or "alphabetical"
        # track_num is string "1/12", "1", "01" etc.
        
        def track_sort_key(t):
            # Parse track num
            num = 10000 # default high
            if t.track_num:
                try:
                    # Handle "1/10"
                    n = t.track_num.split("/")[0]
                    num = int(n)
                except ValueError:
                    pass
            return (num, t.file_path)
            
        sorted_tracks = sorted(tracks, key=track_sort_key)
        if not sorted_tracks:
            return

        representative_track = sorted_tracks[0]
        track_dir = os.path.dirname(representative_track.file_path)
        
        # Find local image file first? 
        # Spec says:
        # 1. Metadata of representative track
        # 2. Local file (ALBUM.jpg, etc.)
        
        # Re-reading spec: "上の方から順に探し、なければ下へ探す"
        # 1. Metadata
        # 2. Files
        
        source = await run_in_threadpool(self._find_source, sorted_tracks[0].file_path, album_display)
        
        if not source:
            # No art found
            return

        source_type, source_path, source_mtime = source
        
        # Check DB
        stmt = select(AlbumArt).where(AlbumArt.album_normalized == album_norm)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        
        if existing:
            # Check if update needed
            # Valid source replacement? Or same source updated?
            if existing.source_path == source_path and existing.source_mtime == source_mtime:
                # No change
                return
            
            # Update existing
            logger.info(f"Updating art for {album_display} from {source_path}")
            image_data = await run_in_threadpool(self._process_image, source_path, source_type)
            if image_data:
                existing.image_data = image_data
                existing.source_path = source_path
                existing.source_type = source_type
                existing.source_mtime = source_mtime
                existing.album_display = album_display # Update display name strictly
        else:
            # Create new
            logger.info(f"Creating art for {album_display} from {source_path}")
            image_data = await run_in_threadpool(self._process_image, source_path, source_type)
            if image_data:
                new_art = AlbumArt(
                    album_normalized=album_norm,
                    album_display=album_display,
                    image_data=image_data,
                    source_path=source_path,
                    source_type=source_type,
                    source_mtime=source_mtime
                )
                session.add(new_art)

    def _find_source(self, track_path: str, album_name: str) -> Optional[Tuple[str, str, float]]:
        """
        Returns (type, path, mtime)
        type: 'meta' or 'file'
        """
        # 1. Check Metadata
        try:
            from mutagen import File
            f = File(track_path)
            if f:
                # Check for embedded art
                has_art = False
                # ID3 (MP3)
                if hasattr(f, "tags") and f.tags:
                    if "APIC:" in f.tags: # Mutagen generic ID3 key? No. 
                        # Iterate tags to find APIC
                        for key in f.tags.keys():
                            if key.startswith("APIC"):
                                has_art = True
                                break
                # MP4
                if hasattr(f, "tags") and "covr" in f.tags:
                    has_art = True
                # FLAC
                if hasattr(f, "pictures") and f.pictures:
                    has_art = True
                    
                if has_art:
                    mtime = os.path.getmtime(track_path)
                    return ("meta", track_path, mtime)
        except Exception:
            pass
            
        # 2. Check File System
        # album_name.jpg/png ...
        # albumart ...
        
        track_dir = os.path.dirname(track_path)
        candidates = []
        
        # Priority 1: ALBUM_NAME.(jpg|png)
        # Try exact album name, case insensitive?
        # Spec: "楽曲ファイルのアルバム名をALBUMとしたとき、その楽曲ファイルと同じフォルダの”ALBUM.jpg”..."
        
        # Clean album name for filename?
        # Just assume simple string match for now.
        
        # Patterns to search
        search_patterns = [
            album_name, # ALBUM
            "albumart",
            "AlbumArt",
            "AlbumArtSmall"
        ]
        
        try:
            files_in_dir = os.listdir(track_dir)
        except OSError:
            return None
            
        for pattern in search_patterns:
            for ext in self.IMAGE_EXTENSIONS:
                # Try exact case first? Spec says "拡張子は大文字も探す".
                # But also filenames? "ALBUM.jpg", "ALBUM.png", "albumart.jpg"...
                
                # Check case-insensitive match against files_in_dir
                target = f"{pattern}{ext}"
                
                for f in files_in_dir:
                    if f.lower() == target.lower():
                        # Found match
                        full_path = os.path.join(track_dir, f)
                        mtime = os.path.getmtime(full_path)
                        return ("file", full_path, mtime)
                        
        return None

    def _process_image(self, path: str, source_type: str) -> Optional[bytes]:
        """
        Reads image from file or metadata, resizes it, returns bytes.
        """
        img_data = None
        
        try:
            if source_type == "file":
                with open(path, "rb") as f:
                    img_data = f.read()
            elif source_type == "meta":
                from mutagen import File
                f = File(path)
                if f:
                    # Extract data
                    # MP3 ID3
                    if hasattr(f, "tags"):
                        # MP3
                        for key in f.tags.keys():
                            if key.startswith("APIC"):
                                img_data = f.tags[key].data
                                break
                        # MP4
                        if not img_data and "covr" in f.tags:
                            # MP4 covr is list of data
                            if len(f.tags["covr"]) > 0:
                                img_data = f.tags["covr"][0]
                                
                    # FLAC
                    if not img_data and hasattr(f, "pictures") and f.pictures:
                        img_data = f.pictures[0].data
            
            if not img_data:
                return None
                
            # Resize using Pillow
            with Image.open(io.BytesIO(img_data)) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                    
                w, h = img.size
                if w > 500 or h > 500:
                    img.thumbnail((500, 500), Image.Resampling.LANCZOS)
                    
                out_io = io.BytesIO()
                img.save(out_io, format="JPEG", quality=85)
                return out_io.getvalue()
                
        except Exception as e:
            logger.error(f"Failed to process image {path} ({source_type}): {e}")
            return None
