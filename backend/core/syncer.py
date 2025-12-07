import os
import errno
import tempfile
import subprocess
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import List, Callable, Optional
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.future import select
from collections import defaultdict

from ..db.models import Track, Setting, Playlist, PlaylistTrack
from ..db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Base Synchronizer
class AudioSynchronizer(ABC):
    def __init__(self, tracks: List[Track], playlists: List[dict], settings: dict, log_callback: Optional[Callable[[str], None]] = None):
        self.tracks = tracks
        self.playlists = playlists # List of dict {name, content} or similar
        self.settings = settings
        self.log_callback = log_callback
        self.remote_os_sep = "/" 

    def log(self, message: str):
        logger.info(message)
        if self.log_callback:
            # log_callback is likely async, but we can't await easily in sync methods if this class is mixed.
            # Ideally, these methods run in threadpool, so we can't await. 
            # We assume log_callback handles thread safety or we just fire and forget?
            # Actually, callback should probably be a sync wrapper that schedules async task or just sync print.
            # user of this class should provide thread-safe callback.
            try:
               self.log_callback(message)
            except Exception:
               pass

    @abstractmethod
    def cp(self, filepath_from, relative_path_to):
        pass

    @abstractmethod
    def rm_remote(self, relative_filepath_to):
        pass

    @abstractmethod
    def mkdir_p_remote(self, relative_filepath_to):
        pass
    
    @abstractmethod
    def ls_remote(self, relative_dir=""):
        pass

    def put_playlist_file(self, relative_dir=""):
         for pl in self.playlists:
             name = pl["name"]
             content = pl["content"]
             fd, path = tempfile.mkstemp()
             with open(path, "w", encoding="utf-8") as f:
                 f.write(content)
                 f.flush()
             self.log(f"Copying playlist: {name}.m3u")
             target = relative_dir + self.remote_os_sep + name + ".m3u"
             # Normalize target sep?
             target = target.replace(os.sep, self.remote_os_sep).replace("//", "/")
             self.cp(path, target)
             os.close(fd)
             os.remove(path)

    def synchronize(self):
        sync_dest = self.settings.get("sync_dest", "/sdcard/Music") # Default?
        target_exts = self.settings.get("target_exts", "mp3,mp4,m4a").split(",")
        target_exts = [f".{e.strip()}" for e in target_exts]

        # 1. List remote files
        remote_files = set() # Set of relative paths
        
        def traverse_remote(rel_path):
             try:
                 items = self.ls_remote(rel_path)
             except FileNotFoundError:
                 return

             for name, is_dir in items:
                 child_path = (rel_path + self.remote_os_sep + name) if rel_path else name
                 if is_dir:
                     traverse_remote(child_path)
                 else:
                     remote_files.add(child_path)
        
        self.log(f"Scanning remote: {sync_dest}")
        traverse_remote("")

        # 2. Determine actions
        tracks_to_sync = [t for t in self.tracks if t.sync]
        
        # normalized relative paths for comparison (remote sep)
        local_map = {} 
        for t in tracks_to_sync:
             # t.relative_path is expected to be consistent (e.g. "Artist/Album/Song.mp3")
             # Ensure remote_sep
             # Also strip leading slash so it matches traverse_remote result (which builds paths relative to root without leading slash)
             r_path = t.relative_path.replace("\\", "/").replace(os.sep, "/")
             if r_path.startswith("/"):
                 r_path = r_path[1:]
             
             local_map[r_path] = t
        
        # COPY
        count = 0
        total = len(tracks_to_sync)
        for r_path, track in local_map.items():
             if r_path not in remote_files:
                 count += 1
                 self.log(f"[{count}/{total}] Copying: {track.file_name}")
                 target_dir = os.path.dirname(r_path)
                 self.mkdir_p_remote(target_dir) # Optimization: cache created dirs
                 self.cp(track.file_path, r_path)
             else:
                 # Already exists. Check size/date? Skip for now per original logic (if exists, skip)
                 pass
        
        # DELETE
        # Iterate remote files, if not in local_map AND matches extension, delete
        for r_file in remote_files:
             ext = os.path.splitext(r_file)[1]
             if ext in target_exts and r_file not in local_map:
                 self.log(f"Removing remote file: {r_file}")
                 self.rm_remote(r_file)

        # Playlist
        self.put_playlist_file()

# ADB Implementation
class AdbSynchronizer(AudioSynchronizer):
    def __init__(self, tracks, playlists, settings, log_callback=None):
        super().__init__(tracks, playlists, settings, log_callback)
        self.remote_os_sep = "/"
        self.sync_root = self.settings.get("sync_dest", "/sdcard/Music")

    def adb_escape(self, s):
        return s.replace(" ","\\ ").replace("(","\\(").replace(")","\\)").replace("&","\\&").replace("|","\\|").replace("'","\\'").replace("\"","\\\"").replace("\n","\\n")

    def _run_cmd(self, args):
        result = subprocess.run(args, encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result

    def cp(self, filepath_from, relative_path_to):
        cmd = ["adb", "push", filepath_from, f"{self.sync_root}/{relative_path_to}"]
        self._run_cmd(cmd)

    def rm_remote(self, relative_filepath_to):
        target = f"{self.sync_root}/{relative_filepath_to}"
        cmd = f"adb shell rm -f \"{self.adb_escape(target)}\""
        subprocess.run(cmd, shell=True) # shell=True for complex escaping or split manually

    def mkdir_p_remote(self, relative_filepath_to):
        target = f"{self.sync_root}/{relative_filepath_to}"
        cmd = f"adb shell mkdir -p \"{self.adb_escape(target)}\""
        subprocess.run(cmd, shell=True)

    def ls_remote(self, relative_dir=""):
        target = f"{self.sync_root}/{relative_dir}".rstrip("/")
        cmd = f"adb shell ls \"{self.adb_escape(target)}\" -F1"
        # Let's use shell=True for adb shell commands to be safe with escapes
        res = subprocess.run(cmd, shell=True, encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if res.returncode != 0 or "No such file" in res.stderr:
             raise FileNotFoundError()
        
        rt = []
        for line in res.stdout.splitlines():
            if not line: continue
            if line.endswith("/"):
                rt.append((line[:-1], True))
            elif line.endswith("*"):
                rt.append((line[:-1], False))
            else:
                rt.append((line, False))
        return rt

# Rsync Implementation
class RsyncSynchronizer(AudioSynchronizer):
    # Rsync implementation might be diff logic (rsync takes care of everything)
    # Original code generates include-list and runs rsync.
    def __init__(self, tracks, playlists, settings, log_callback=None):
        super().__init__(tracks, playlists, settings, log_callback)
        self.remote_os_sep = "/"
        # Settings: rsync_host, rsync_port, rsync_user, rsync_path
    
    def synchronize(self):
        # Override synchronize to use native rsync features
        user = self.settings.get("rsync_user")
        host = self.settings.get("rsync_host")
        port = self.settings.get("rsync_port", "22")
        dest_path = self.settings.get("sync_dest", "~")
        
        # Generate include list
        include_list = set()
        tracks_to_sync = [t for t in self.tracks if t.sync]
        
        for t in tracks_to_sync:
             # Add all parent dirs
             parts = t.relative_path.replace("\\", "/").split("/")
             for i in range(1, len(parts)):
                 include_list.add("/".join(parts[:i]) + "/")
             include_list.add(t.relative_path.replace("\\", "/"))
        
        fd, include_path = tempfile.mkstemp()
        try:
             with open(include_path, "w") as f:
                 for p in include_list:
                     f.write(p + "\n")
             
             # Roots to sync from?
             # AudioSyncData had "include_dir".
             # Here we have tracks with absolute paths. Rsync needs common root or src dirs.
             # This is tricky if tracks are scattered.
             # TODO: Current implementation assumes scan_paths from settings. 
             #       Better logic would be to determine source directories from track paths (absolute vs relative).
             # Original: src_dir = [d.rstrip("/") for d in self.audio_sync_data.include_dir]
             # We need to recover roots from settings?
             scan_paths_str = self.settings.get("scan_paths", "[]")
             import json
             try: scan_paths = json.loads(scan_paths_str)
             except: scan_paths = []
             if not scan_paths: return
             
             src_dirs = [s.rstrip(os.sep) + os.sep for s in scan_paths]
             
             remote = f"{user}@{host}:{dest_path}" if user else f"{host}:{dest_path}"
             
             cmd = [
                 "rsync", "-avz", "--delete-excluded", "--include-from", include_path, "--exclude=*",
                 "-e", f"ssh -p {port}"
             ]
             cmd.extend(src_dirs)
             cmd.append(remote)
             
             self.log(f"Running rsync: {' '.join(cmd)}")
             
             proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for line in proc.stdout:
                 self.log(line.strip())
             proc.wait()
             
             if proc.returncode != 0:
                 self.log(f"Rsync failed with code {proc.returncode}")

        finally:
             os.close(fd)
             os.remove(include_path)
             
        # Playlist sync (manual scp/rsync)
        self.put_playlist_file()

    # cp/rm/mkdir not used by main synchronize, but implemented for playlist
    def cp(self, filepath_from, relative_path_to):
        user = self.settings.get("rsync_user")
        host = self.settings.get("rsync_host")
        port = self.settings.get("rsync_port", "22")
        dest_path = self.settings.get("sync_dest", "~")
        
        remote = f"{user}@{host}:{dest_path}" if user else f"{host}:{dest_path}"
        # dest_path joined with relative_path_to
        # Wait, dest_path is root. relative_path_to is from root.
        # Clean logic: remote destination is `host:dest_path/relative_path_to`
        # Careful with joining
        remote_full = f"{remote}/{relative_path_to}".replace("//", "/")
        
        cmd = [
             "rsync", "-avz", 
             "-e", f"ssh -p {port}",
             filepath_from, remote_full
        ]
        self.log(f"Copying file (rsync): {relative_path_to}")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
             self.log(f"Rsync cp failed: {proc.stderr}")

    def rm_remote(self, p): pass
    def mkdir_p_remote(self, p): pass
    def ls_remote(self, p): pass


import ftplib

# FTP Implementation
class FtpSynchronizer(AudioSynchronizer):
    def __init__(self, tracks, playlists, settings, log_callback=None):
        super().__init__(tracks, playlists, settings, log_callback)
        self.remote_os_sep = "/"
        
        ip_addr = self.settings.get("ftp_host", "192.168.10.3")
        port = int(self.settings.get("ftp_port", 2221))
        user = self.settings.get("ftp_user", "francis")
        passwd = self.settings.get("ftp_pass", "francis")
        
        self.log(f"Connecting to FTP {ip_addr}:{port} as {user}")
        self.ftp = ftplib.FTP()
        self.ftp.encoding = "utf-8"
        self.ftp.set_pasv(True)
        self.ftp.connect(host=ip_addr, port=port)
        self.ftp.login(user=user, passwd=passwd)
        self.log("FTP login success.")

    def __del__(self):
        try:
            self.ftp.quit()
        except:
            try: self.ftp.close()
            except: pass

    def cp(self, filepath_from, relative_path_to):
        remote_dir = os.path.dirname(relative_path_to).replace(os.sep, self.remote_os_sep)
        filename = os.path.basename(relative_path_to)
        
        try:
            self.ftp.cwd(remote_dir)
        except ftplib.error_perm:
            # Maybe dir doesn't exist? Try to make it?
            # mkdir_p_remote should have been called before.
            # Retry ensuring root?
            pass

        try:
            with open(filepath_from, "rb") as f:
                stor = "STOR " + filename
                self.ftp.storbinary(stor, f)
            self.log(f"FTP STOR success: {filename}")
        finally:
            self.ftp.cwd("/")

    def rm_remote(self, relative_filepath_to):
        try:
            self.ftp.delete(relative_filepath_to)
            self.log(f"FTP delete success: {relative_filepath_to}")
        except ftplib.error_perm as e:
            self.log(f"FTP delete failed: {e}")

    def mkdir_p_remote(self, relative_filepath_to):
        # Create directories recursively
        # relative_filepath_to is the target directory path
        parts = relative_filepath_to.strip(self.remote_os_sep).split(self.remote_os_sep)
        current = ""
        for part in parts:
            current = (current + self.remote_os_sep + part) if current else part
            try:
                self.ftp.mkd(current)
            except ftplib.error_perm:
                pass # Exists?

    def ls_remote(self, relative_dir=""):
        target = relative_dir.replace(os.sep, self.remote_os_sep)
        if not target: target = "/"
        
        # Check existence first
        try:
            self.ftp.cwd(target)
        except ftplib.error_perm:
            raise FileNotFoundError()
        
        items = []
        try:
            # mlsd is better for type detection
            for name, facts in self.ftp.mlsd(path="", facts=["type"]):
                if name in [".", ".."]: continue
                items.append((name, facts.get("type") == "dir"))
        except ftplib.error_perm:
            # Fallback for servers not supporting MLSD?
            # Using nlst but it doesn't give type.
            # Assume MLSD is supported as per original requirement (audio_synchronizer used mlsd)
            pass
        finally:
             self.ftp.cwd("/")
        return items

def make_m3u8(tracks: List[Track], remote_sep="/") -> str:
    # Generate m3u8 content
    # #EXTM3U
    # #EXTINF:-1,Title
    # path/to/file.mp3
    rt = "#EXTM3U\n\n"
    for t in tracks:
        if not t.relative_path: continue
        
        title = t.title if t.title else t.file_name
        # Path should be relative to playlist location? Or relative to sync root?
        # Typically relative to playlist file. If playlist is in root, then relative path is fine.
        # Need to ensure correct separators.
        # relative_path stored in DB likely has leading slash (as verified).
        # m3u8 path shouldn't usually have leading slash if in same dir? Or maybe yes.
        # User requirement: "relative_filepath_to" used in original code.
        # Original: filepath = self.__sheet.cell(row=row, column=self.header["同期先相対ファイルパス"]).value[1:].replace(os.sep, sep)
        # [1:] implies removing leading slash.
        
        # Replace backslashes (Windows) and OS specific sep with remote_sep
        p = t.relative_path.replace("\\", "/").replace(os.sep, "/")
        if remote_sep != "/":
            p = p.replace("/", remote_sep)
            
        if p.startswith(remote_sep):
             p = p[len(remote_sep):]
        
        rt += f"#EXTINF:-1,{title}\n"
        rt += f"{p}\n\n"
    return rt

from sqlalchemy.orm import joinedload

class SyncService:
    @staticmethod
    async def run_sync(log_callback: Optional[Callable[[str], None]] = None):
        async with AsyncSessionLocal() as db:
            # Load settings
            result = await db.execute(select(Setting))
            settings = {s.key: s.value for s in result.scalars().all()}
            
            # Load tracks
            result = await db.execute(select(Track))
            tracks = result.scalars().all()
            
            # Load playlists from DB with tracks
            result = await db.execute(
                select(Playlist).options(joinedload(Playlist.tracks).joinedload(PlaylistTrack.track))
            )
            db_playlists = result.scalars().unique().all()
            
            playlists = []
            
            # 2. DB Playlists
            for pl in db_playlists:
                # filter out tracks that might have been deleted but link exists? 
                # (Should be handled by FK cascade, but safety check)
                
                # Sort by order
                sorted_pt = sorted(pl.tracks, key=lambda pt: pt.order)
                pl_tracks = [pt.track for pt in sorted_pt if pt.track]
                
                if pl_tracks:
                    content = make_m3u8(pl_tracks)
                    playlists.append({"name": pl.name, "content": content})

            mode = settings.get("sync_mode", "adb") # adb, rsync, ftp

            
            # Run in thread
            def _sync():
                if mode == "adb":
                    sync = AdbSynchronizer(tracks, playlists, settings, log_callback)
                    sync.synchronize()
                elif mode == "rsync":
                    sync = RsyncSynchronizer(tracks, playlists, settings, log_callback)
                    sync.synchronize()
                elif mode == "ftp":
                    sync = FtpSynchronizer(tracks, playlists, settings, log_callback)
                    sync.synchronize()
                else:
                    if log_callback: log_callback(f"Unknown mode: {mode}")

            await run_in_threadpool(_sync)
