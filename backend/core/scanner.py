
import os
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, or_
from typing import List, Optional
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4
from mutagen.id3 import ID3NoHeaderError
from fastapi.concurrency import run_in_threadpool

from ..db.models import Track, Setting
from ..db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ScannerService:
    def __init__(self):
        self.settings = {}

    async def load_settings(self, db: AsyncSession):
        result = await db.execute(select(Setting))
        settings_list = result.scalars().all()
        for s in settings_list:
            self.settings[s.key] = s.value
    
    def _get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    async def run_scan(self):
        logger.info("Scan started")
        async with AsyncSessionLocal() as db:
            await self.load_settings(db)
            
            scan_paths_str = self._get_setting("scan_paths", "[]")
            import json
            try:
                scan_paths = json.loads(scan_paths_str)
            except json.JSONDecodeError:
                scan_paths = []

            # Fallback if simple string
            if isinstance(scan_paths_str, str) and not scan_paths:
                 if scan_paths_str.startswith("["): # Try to parse again if it looks like list but failed? No, just validation.
                     pass
                 else:
                     scan_paths = [scan_paths_str]

            target_exts_str = self._get_setting("target_exts", "mp3,mp4,m4a")
            target_exts = [f".{ext.strip()}" for ext in target_exts_str.split(",")]
            
            exclude_dirs_str = self._get_setting("exclude_dirs", "")
            exclude_dirs = [d.strip() for d in exclude_dirs_str.split(",") if d.strip()]

            if not scan_paths:
                logger.warning("No scan paths configured.")
                return

            found_files = []
            
            # 1. Scan File System (CPU/IO bound -> ThreadPool)
            files_to_process = await run_in_threadpool(
                self._scan_filesystem, scan_paths, target_exts, exclude_dirs
            )
            
            # 2. Process Files (Extract Metadata) & Update DB
            # We process in batches or one by one? 
            # Ideally verify against DB cache.
            
            # Fetch all existing tracks path/mtime to minimize updates
            # For large library, this might be heavy. fetch id, file_path, last_modified
            result = await db.execute(select(Track))
            existing_tracks = {t.file_path: t for t in result.scalars().all()}
            
            updated_count = 0
            added_count = 0
            
            files_scanned_set = set()

            for file_path, rel_path, mtime in files_to_process:
                files_scanned_set.add(file_path)
                mtime_dt = datetime.datetime.fromtimestamp(mtime)
                
                track_in_db = existing_tracks.get(file_path)
                
                if track_in_db:
                    # Check if modified
                    # Note: SQLite stores datetime, ensure comparison works
                    # track_in_db.last_modified might be naïve or aware.
                    # Let's verify if mtime changed.
                    if track_in_db.last_modified != mtime_dt:
                        # Update
                        meta = await run_in_threadpool(self._extract_metadata, file_path)
                        if meta:
                            for key, value in meta.items():
                                setattr(track_in_db, key, value)
                            track_in_db.last_modified = mtime_dt
                            track_in_db.msg = None # Clear error msg if any
                            updated_count += 1
                            logger.info(f"File updated: {file_path}")
                else:
                    # New file
                    meta = await run_in_threadpool(self._extract_metadata, file_path)
                    if meta:
                        new_track = Track(
                            file_path=file_path,
                            relative_path=rel_path,
                            last_modified=mtime_dt,
                            added_date=datetime.datetime.now(),
                            sync=False, # Default
                            **meta
                        )
                        db.add(new_track)
                        added_count += 1
                        logger.info(f"New file added: {file_path}")
            
            # 3. Mark missing files
            missing_count = 0
            for file_path, track in existing_tracks.items():
                if file_path not in files_scanned_set:
                    # File removed
                    # Option A: Delete
                    # Option B: Mark as missing (msg="Missing")
                    # Original logic used msg="-".
                    if track.msg != "Missing":
                        track.msg = "Missing"
                        missing_count += 1
                        logger.info(f"File missing: {file_path}")
            
            await db.commit()
            logger.info(f"Scan complete. Added: {added_count}, Updated: {updated_count}, Missing: {missing_count}")

    def _scan_filesystem(self, paths: List[str], exts: List[str], excludes: List[str]):
        results = [] # (full_path, relative_path, mtime)
        for root_path in paths:
            if not os.path.exists(root_path):
                continue
            for root, dirs, files in os.walk(root_path):
                # Filter excludes
                dirs[:] = [d for d in dirs if d not in excludes]
                
                for file in files:
                    if any(file.lower().endswith(ext) for ext in exts):
                        full_path = os.path.join(root, file)
                        # Relative path calculation depends on business logic.
                        # AudioSyncData uses root directory as base?
                        # "rt[len(os.path.dirname(dir)):]" line 378 of audio_sync_data.py
                        # It seems relative from the scan root parent? or scan root?
                        # AudioSyncData: rt[len(os.path.dirname(dir)):] -> includes the folder name of the scanned dir?
                        # Example: scan /music/Album1
                        # file: /music/Album1/song.mp3
                        # dirname(/music/Album1) -> /music/
                        # rel -> Album1/song.mp3
                        # Let's replicate this.
                        # Strip trailing slash to ensure dirname gives parent
                        root_clean = root_path.rstrip(os.sep)
                        base_dir = os.path.dirname(root_clean)
                        rel_path = full_path[len(base_dir):] if full_path.startswith(base_dir) else full_path
                        if not rel_path.startswith(os.sep):
                            rel_path = os.sep + rel_path
                        # Ensure leading slash is removed if specific requirement, or standardized.
                        # AudioSyncData line 378: returns (rt, rt[...])
                        
                        try:
                            mtime = os.stat(full_path).st_mtime
                            results.append((full_path, rel_path, mtime))
                        except OSError:
                            continue
        return results

    def _extract_metadata(self, filepath: str) -> Optional[dict]:
        data = {
            "file_name": os.path.splitext(os.path.basename(filepath))[0],
            "title": None,
            "artist": None,
            "album_artist": None,
            "composer": None,
            "album": None,
            "track_num": None,
            "duration": None, # length
            "codec": None,
            "msg": None
        }
        
        ext = os.path.splitext(filepath)[1].lower()
        
        def if_key_error(tags, key):
            try:
                if isinstance(tags, EasyID3):
                    return tags[key][0]
                elif hasattr(tags, 'get'):
                    val = tags.get(key)
                    if isinstance(val, list): return val[0]
                    return val
                return None
            except (KeyError, IndexError):
                return None

        try:
            if ext == ".mp3":
                data["codec"] = "mp3"
                try:
                    eid3 = EasyID3(filepath)
                    data["title"] = if_key_error(eid3, "title")
                    data["album"] = if_key_error(eid3, "album")
                    data["artist"] = if_key_error(eid3, "artist")
                    data["album_artist"] = if_key_error(eid3, "albumartist")
                    data["composer"] = if_key_error(eid3, "composer")
                    data["track_num"] = if_key_error(eid3, "tracknumber")
                    data["duration"] = if_key_error(eid3, "length") # EasyID3 might not have length, Mutagen File usually does
                except ID3NoHeaderError:
                    data["msg"] = "!"
            
            elif ext in [".mp4", ".m4a"]:
                data["codec"] = "mp4"
                mp4 = MP4(filepath)
                tags = mp4.tags
                data["title"] = if_key_error(tags, "\xa9nam")
                data["album"] = if_key_error(tags, "\xa9alb")
                data["artist"] = if_key_error(tags, "\xa9ART")
                data["album_artist"] = if_key_error(tags, "aART")
                data["composer"] = if_key_error(tags, "\xa9wrt")
                trkn = if_key_error(tags, "trkn") # (track_num, total)
                if trkn:
                     if isinstance(trkn, (list, tuple)) and len(trkn) > 0:
                         data["track_num"] = str(trkn[0])
                         if len(trkn) > 1 and trkn[1] > 0:
                             data["track_num"] += f"/{trkn[1]}"
                
                if mp4.info:
                    data["duration"] = int(mp4.info.length)
            
            # Fallback for duration if not set (MP3 often needs MP3() class not just ID3)
            if data["duration"] is None and ext == ".mp3":
                 from mutagen.mp3 import MP3
                 try:
                     f = MP3(filepath)
                     data["duration"] = int(f.info.length)
                 except: pass

            return data
        except Exception as e:
            logger.error(f"Error parsing metadata for {filepath}: {e}")
            data["msg"] = "Error"
            return data


# --- __main__ entry for standalone debug ---
if __name__ == "__main__":
    import asyncio
    import sys
    # 標準出力にログを出す設定
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger.info("ScannerService standalone mode start")
    scanner = ScannerService()
    # run_scanはasyncなのでasyncioで実行
    try:
        asyncio.run(scanner.run_scan())
    except Exception as e:
        logger.exception(f"ScannerService failed: {e}")


