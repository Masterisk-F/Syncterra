import os
import datetime
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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

    async def run_scan(self, progress_callback=None, log_callback=None):
        logger.info("Scan started")
        if log_callback:
            log_callback("Scan started")

        async with AsyncSessionLocal() as db:
            await self.load_settings(db)

            scan_paths_str = self._get_setting("scan_paths", "[]")
            try:
                scan_paths = json.loads(scan_paths_str)
                if not isinstance(scan_paths, list):
                    scan_paths = [scan_paths] if scan_paths else []
            except (json.JSONDecodeError, TypeError):
                # Fallback: if it's a string like "['/path']" but with single quotes, 
                # or just a plain string path
                if isinstance(scan_paths_str, str) and scan_paths_str.strip():
                    import ast
                    try:
                        # Try literal_eval for single quotes/list representation
                        val = ast.literal_eval(scan_paths_str)
                        if isinstance(val, list):
                            scan_paths = val
                        else:
                            scan_paths = [str(val)]
                    except (ValueError, SyntaxError):
                        # Pure fallback for non-list strings
                        scan_paths = [scan_paths_str]
                else:
                    scan_paths = []

            target_exts_str = self._get_setting("target_exts", "")
            if not target_exts_str.strip():
                target_exts_str = "mp3,mp4,m4a"

            # Normalize extensions: lower case and remove leading dot for comparison later
            target_exts = [
                f".{ext.strip().lower().lstrip('.')}" 
                for ext in target_exts_str.split(",") 
                if ext.strip()
            ]

            exclude_dirs_str = self._get_setting("exclude_dirs", "")
            exclude_dirs = [d.strip() for d in exclude_dirs_str.split(",") if d.strip()]

            if not scan_paths:
                msg = "No scan paths configured."
                logger.warning(msg)
                if log_callback:
                    log_callback(msg)
                return

            # 1. Scan File System (CPU/IO bound -> ThreadPool)
            files_to_process = await run_in_threadpool(
                self._scan_filesystem, scan_paths, target_exts, exclude_dirs
            )

            total_files = len(files_to_process)
            processed_files = 0
            last_progress = 0

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
                    # ファイルの変更、またはスキャン設定によるパス変更のチェック
                    # needs_meta_update: ファイル自体（タイムスタンプ）が更新されたか
                    # path_changed: スキャンルートディレクトリが変更され、同期先の相対パスが変わったか
                    # (例: /music をスキャン対象にしていたのを /music/default に変更した場合などにtrueになる)
                    if track_in_db.missing:
                        track_in_db.missing = False
                        logger.info(f"File recovered from missing: {file_path}")

                    needs_meta_update = track_in_db.last_modified != mtime_dt
                    path_changed = track_in_db.relative_path != rel_path

                    if needs_meta_update or path_changed:
                        if needs_meta_update:
                            # ファイルが変更されている場合はメタデータを再抽出
                            meta = await run_in_threadpool(
                                self._extract_metadata, file_path
                            )
                            if meta:
                                for key, value in meta.items():
                                    setattr(track_in_db, key, value)
                                track_in_db.last_modified = mtime_dt
                                track_in_db.msg = None
                                updated_count += 1
                                msg = f"File updated (meta): {file_path}"
                                logger.info(msg)
                                if log_callback:
                                    log_callback(msg)
                        
                        if path_changed:
                            # スキャンディレクトリ設定が変更された場合、相対パスのみを更新する。
                            # ファイル実体に変更がない場合は、重いメタデータ抽出はスキップしてDB上のパスのみを修正する。
                            track_in_db.relative_path = rel_path
                            if not needs_meta_update:
                                updated_count += 1
                                msg = f"File updated (path): {file_path} -> {rel_path}"
                                logger.info(msg)
                                if log_callback:
                                    log_callback(msg)
                else:
                    # New file
                    meta = await run_in_threadpool(self._extract_metadata, file_path)
                    if meta:
                        new_track = Track(
                            file_path=file_path,
                            relative_path=rel_path,
                            last_modified=mtime_dt,
                            added_date=datetime.datetime.now(),
                            sync=False,  # Default
                            missing=False,
                            **meta,
                        )
                        db.add(new_track)
                        added_count += 1
                        msg = f"New file added: {file_path}"
                        logger.info(msg)
                        if log_callback:
                            log_callback(msg)

                processed_files += 1
                if progress_callback:
                    current_progress = int((processed_files / total_files) * 100)
                    if current_progress >= last_progress + 5 or current_progress == 100:
                        progress_callback(current_progress)
                        last_progress = current_progress

            # 3. Mark missing files
            missing_count = 0
            for file_path, track in existing_tracks.items():
                if file_path not in files_scanned_set:
                    # File removed
                    # Option A: Delete
                    # Option B: Mark as missing (missing=True)
                    if not track.missing:
                        track.missing = True
                        missing_count += 1
                        msg = f"File missing: {file_path}"
                        logger.info(msg)
                        if log_callback:
                            log_callback(msg)

            if progress_callback and last_progress < 100:
                progress_callback(100)

            await db.commit()
            summary = f"Scan complete. Added: {added_count}, Updated: {updated_count}, Missing: {missing_count}"
            logger.info(summary)
            if log_callback:
                log_callback(summary)

    def _scan_filesystem(self, paths: List[str], exts: List[str], excludes: List[str]):
        results = []  # (full_path, relative_path, mtime)
        logger.info(f"FileSystem scan started. Target paths: {paths}, Exts: {exts}")
        
        for root_path in paths:
            logger.info(f"Checking root path: {root_path}")
            if not os.path.exists(root_path):
                logger.warning(f"Path does not exist: {root_path}")
                continue
            
            if os.path.islink(root_path):
                logger.info(f"Root path '{root_path}' is a symbolic link. Target: {os.path.realpath(root_path)}")

            # We use followlinks=True to ensure mount points that are symlinks are traversed
            for root, dirs, files in os.walk(root_path, followlinks=True):
                # Filter excludes
                original_dirs = list(dirs)
                dirs[:] = [d for d in dirs if d not in excludes]
                if len(dirs) != len(original_dirs):
                    excluded = set(original_dirs) - set(dirs)
                    logger.debug(f"Excluded directories in {root}: {excluded}")

                for file in files:
                    # Case insensitive check
                    if any(file.lower().endswith(ext) for ext in exts):
                        full_path = os.path.join(root, file)
                        
                        # Strip trailing slash to ensure dirname gives parent
                        root_clean = root_path.rstrip(os.sep)
                        base_dir = os.path.dirname(root_clean)
                        
                        rel_path = (
                            full_path[len(base_dir) :]
                            if full_path.startswith(base_dir)
                            else full_path
                        )
                        if not rel_path.startswith(os.sep):
                            rel_path = os.sep + rel_path

                        try:
                            mtime = os.stat(full_path).st_mtime
                            results.append((full_path, rel_path, mtime))
                        except OSError as e:
                            logger.error(f"Error accessing file {full_path}: {e}")
                            continue

        logger.info(f"FileSystem scan finished. Found {len(results)} matching files.")
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
            "duration": None,  # length
            "codec": None,
            "msg": None,
        }

        ext = os.path.splitext(filepath)[1].lower()

        def if_key_error(tags, key):
            try:
                if isinstance(tags, EasyID3):
                    return tags[key][0]
                elif hasattr(tags, "get"):
                    val = tags.get(key)
                    if isinstance(val, list):
                        return val[0]
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
                    data["duration"] = if_key_error(
                        eid3, "length"
                    )  # EasyID3 might not have length, Mutagen File usually does
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
                trkn = if_key_error(tags, "trkn")  # (track_num, total)
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
                except Exception:
                    pass

            # Ensure duration is integer
            if data["duration"] is not None:
                try:
                    data["duration"] = int(data["duration"])
                except (ValueError, TypeError):
                    data["duration"] = None

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
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger.info("ScannerService standalone mode start")
    scanner = ScannerService()
    # run_scanはasyncなのでasyncioで実行
    try:
        asyncio.run(scanner.run_scan())
    except Exception as e:
        logger.exception(f"ScannerService failed: {e}")
