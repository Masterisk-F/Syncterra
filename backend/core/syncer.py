import os
import tempfile
import subprocess
import ftplib
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import List, Callable, Optional
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from ..db.models import Track, Setting, Playlist, PlaylistTrack
from ..db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# Base Synchronizer
class AudioSynchronizer(ABC):
    def __init__(
        self,
        tracks: List[Track],
        playlists: List[dict],
        settings: dict,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.tracks = tracks
        self.playlists = playlists  # List of dict {name, content} or similar
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
        sync_dest = self.settings.get("sync_dest", "/sdcard/Music")  # Default?
        target_exts = self.settings.get("target_exts", "mp3,mp4,m4a").split(",")
        target_exts = [f".{e.strip()}" for e in target_exts]

        # 1. List remote files
        remote_files = set()  # Set of relative paths

        def traverse_remote(rel_path):
            try:
                items = self.ls_remote(rel_path)
            except FileNotFoundError:
                return

            for name, is_dir in items:
                child_path = (
                    (rel_path + self.remote_os_sep + name) if rel_path else name
                )
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
                self.mkdir_p_remote(target_dir)  # Optimization: cache created dirs
                self.cp(track.file_path, r_path)
            else:
                # Already exists. Check size/date? Skip for now per original logic (if exists, skip)
                pass

        # DELETE
        # Iterate remote files, if not in local_map AND matches extension, delete
        for r_file in remote_files:
            ext = os.path.splitext(r_file)[1]
            if r_file not in local_map:
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
        return (
            s.replace(" ", "\\ ")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("&", "\\&")
            .replace("|", "\\|")
            .replace("'", "\\'")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )

    def _run_cmd(self, args):
        result = subprocess.run(
            args,
            encoding="utf-8",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result

    def cp(self, filepath_from, relative_path_to):
        cmd = ["adb", "push", filepath_from, f"{self.sync_root}/{relative_path_to}"]
        self._run_cmd(cmd)

    def rm_remote(self, relative_filepath_to):
        target = f"{self.sync_root}/{relative_filepath_to}"
        cmd = f'adb shell rm -f "{self.adb_escape(target)}"'
        subprocess.run(
            cmd, shell=True
        )  # shell=True for complex escaping or split manually

    def mkdir_p_remote(self, relative_filepath_to):
        target = f"{self.sync_root}/{relative_filepath_to}"
        cmd = f'adb shell mkdir -p "{self.adb_escape(target)}"'
        subprocess.run(cmd, shell=True)

    def ls_remote(self, relative_dir=""):
        target = f"{self.sync_root}/{relative_dir}".rstrip("/")
        cmd = f'adb shell ls "{self.adb_escape(target)}" -F1'
        # Let's use shell=True for adb shell commands to be safe with escapes
        res = subprocess.run(
            cmd,
            shell=True,
            encoding="utf-8",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if res.returncode != 0 or "No such file" in res.stderr:
            raise FileNotFoundError()

        rt = []
        for line in res.stdout.splitlines():
            if not line:
                continue
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
        dest_path = self.settings.get("rsync_dest") or self.settings.get("sync_dest", "~")
        use_key = self.settings.get("rsync_use_key", "0") == "1"
        key_path = self.settings.get("rsync_key_path")
        password = self.settings.get("rsync_pass")

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

            # Get source directories from settings
            scan_paths_str = self.settings.get("scan_paths", "[]")
            import json

            try:
                scan_paths = json.loads(scan_paths_str)
            except Exception:
                scan_paths = []
            if not scan_paths:
                self.log("No scan paths configured")
                return

            src_dirs = [s.rstrip(os.sep) for s in scan_paths]

            # Build rsync command
            cmd = []
            
            # hostが定義されている場合のみSSH認証を使用
            if host:
                # SSH認証方式の判定
                if use_key:
                    # SSH鍵認証
                    if not key_path:
                        self.log("SSH key authentication enabled but key path not configured")
                        return
                    if not os.path.exists(key_path):
                        self.log(f"SSH key file not found: {key_path}")
                        return
                    self.log(f"Using SSH key authentication: {key_path}")
                elif password:
                    # パスワード認証（sshpassを使用）
                    cmd = ["sshpass", "-p", password]
                    self.log("Using password authentication")
                else:
                    self.log("No valid authentication method configured for SSH")
                    return
            
            # rsyncコマンドの基本部分
            cmd.extend([
                "rsync",
                "-avz",
                "--delete-excluded",
                "--include-from",
                include_path,
                "--exclude=*",
            ])
            cmd.extend(src_dirs)

            # リモート先の設定
            if host:
                # SSH経由でのリモート同期
                ssh_opts = f"ssh -p {port}"
                if use_key and key_path:
                    ssh_opts += f" -i {key_path}"
                
                cmd.extend(["-e", ssh_opts])
                
                if user:
                    remote = f"{user}@{host}:{dest_path}"
                else:
                    remote = f"{host}:{dest_path}"
            else:
                # ローカル同期
                remote = dest_path
            
            cmd.append(remote)

            # Log command without password
            log_cmd = [c if c != password else '***' for c in cmd]
            self.log(f"Running rsync: {' '.join(log_cmd)}")

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.log(line.strip())
            proc.wait()

            if proc.returncode != 0:
                self.log(f"Rsync failed with code {proc.returncode}")
            else:
                self.log("Rsync completed successfully")

        finally:
            os.close(fd)
            os.remove(include_path)

        # Playlist sync
        self.put_playlist_file()

    # cp/rm/mkdir not used by main synchronize, but implemented for playlist
    def cp(self, filepath_from, relative_path_to):
        user = self.settings.get("rsync_user")
        host = self.settings.get("rsync_host")
        port = self.settings.get("rsync_port", "22")
        dest_path = self.settings.get("rsync_dest") or self.settings.get("sync_dest", "~")
        use_key = self.settings.get("rsync_use_key", "0") == "1"
        key_path = self.settings.get("rsync_key_path")
        password = self.settings.get("rsync_pass")

        # Build rsync command
        cmd = []
        
        # hostが定義されている場合のみSSH認証を使用
        if host:
            if use_key:
                # SSH鍵認証
                if not key_path or not os.path.exists(key_path):
                    self.log(f"SSH key not available: {key_path}")
                    return
            elif password:
                # パスワード認証（sshpassを使用）
                cmd = ["sshpass", "-p", password]
        
        # rsyncコマンドの基本部分
        cmd.extend(["rsync", "-avz"])
        
        # リモート先の設定
        if host:
            # SSH経由でのリモート同期
            ssh_opts = f"ssh -p {port}"
            if use_key and key_path:
                ssh_opts += f" -i {key_path}"
            
            cmd.extend(["-e", ssh_opts])
            
            if user:
                remote = f"{user}@{host}:{dest_path}"
            else:
                remote = f"{host}:{dest_path}"
        else:
            # ローカル同期
            remote = dest_path
        
        remote_full = f"{remote}/{relative_path_to}".replace("//", "/")
        cmd.extend([filepath_from, remote_full])

        # Log command without password
        log_cmd = [c if c != password else '***' for c in cmd]
        self.log(f"Copying file (rsync): {' '.join(log_cmd)}")
        
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            self.log(f"Rsync cp failed: {proc.stderr}")
        else:
            self.log(f"File copied successfully: {relative_path_to}")

    def rm_remote(self, p):
        pass

    def mkdir_p_remote(self, p):
        pass

    def ls_remote(self, p):
        pass


# FTP Implementation
class FtpSynchronizer(AudioSynchronizer):
    def __init__(self, tracks, playlists, settings, log_callback=None):
        super().__init__(tracks, playlists, settings, log_callback)
        self.remote_os_sep = "/"
        self.sync_root = self.settings.get("sync_dest", "/")
        if not self.sync_root.startswith("/"):
            self.sync_root = "/" + self.sync_root

        ip_addr = self.settings.get("ftp_host", "192.168.10.3")
        port = int(self.settings.get("ftp_port", 2221))
        user = self.settings.get("ftp_user", "francis")
        passwd = self.settings.get("ftp_pass", "francis")

        self.log(f"Connecting to FTP {ip_addr}:{port} as {user}")
        try:
            self.ftp = ftplib.FTP()
            self.ftp.encoding = "utf-8"
            self.ftp.set_pasv(True)
            self.ftp.connect(host=ip_addr, port=port)
            self.ftp.login(user=user, passwd=passwd)
            self.log("FTP login success.")
        except Exception as e:
            self.log(f"FTP connection failed: {e}")
            raise

    def __del__(self):
        try:
            self.ftp.quit()
        except Exception:
            try:
                self.ftp.close()
            except Exception:
                pass

    def _get_full_remote_path(self, relative_path):
        # Ensure separators are / and relative_path is clean
        rel = relative_path.replace("\\", "/").strip("/")
        root = self.sync_root.replace("\\", "/").rstrip("/")
        if not root.startswith("/"):
            root = "/" + root
            
        if not rel:
            return root if root else "/"
        
        # If root is just "/", joining with "/" + rel would create "//rel"
        if root == "/":
            return "/" + rel
        return root + "/" + rel

    def cp(self, filepath_from, relative_path_to):
        full_path = self._get_full_remote_path(relative_path_to)
        remote_dir = os.path.dirname(full_path)
        filename = os.path.basename(full_path)

        self.log(f"FTP Uploading: {filename} to {remote_dir}")
        try:
            # Ensure we are at root before CWD to absolute-like path
            self.ftp.cwd("/")
            self.ftp.cwd(remote_dir.lstrip("/"))
            with open(filepath_from, "rb") as f:
                stor = "STOR " + filename
                self.ftp.storbinary(stor, f)
            self.log(f"FTP STOR success: {filename} at {remote_dir}")
        except Exception as e:
            self.log(f"FTP STOR failed for {filename}: {e}")
            # Do not raise, just log error to allow sync to continue with other files
            return
        finally:
            try:
                self.ftp.cwd("/")
            except Exception:
                pass

    def rm_remote(self, relative_filepath_to):
        full_path = self._get_full_remote_path(relative_filepath_to)
        try:
            self.ftp.delete(full_path.lstrip("/"))
            self.log(f"FTP delete success: {full_path}")
        except ftplib.error_perm as e:
            self.log(f"FTP delete failed: {e}")

    def mkdir_p_remote(self, relative_filepath_to):
        # Create directories recursively
        full_path = self._get_full_remote_path(relative_filepath_to)
        parts = full_path.strip("/").split("/")
        current = ""
        for part in parts:
            current = (current + "/" + part) if current else ("/" + part)
            try:
                self.ftp.mkd(current.lstrip("/"))
                self.log(f"FTP MKD success: {current}")
            except ftplib.error_perm:
                # ignore if directory already exists
                pass

    def ls_remote(self, relative_dir=""):
        target = self._get_full_remote_path(relative_dir)

        self.log(f"FTP Listing: {target}")
        # Check existence first
        try:
            self.ftp.cwd("/")
            self.ftp.cwd(target.lstrip("/"))
        except ftplib.error_perm:
            raise FileNotFoundError(f"FTP directory not found: {target}")

        items = []
        try:
            # MLSD without facts avoids OPTS MLST which is often unsupported
            for name, facts in self.ftp.mlsd(path=""):
                if name in [".", ".."]:
                    continue
                is_dir = facts.get("type") == "dir"
                items.append((name, is_dir))
        except (ftplib.error_perm, Exception) as e:
            self.log(f"FTP MLSD failed for {target}: {e}. Falling back to nlst.")
            try:
                # nlst gives only names
                names = self.ftp.nlst()
                for name in names:
                    if name in [".", ".."]:
                        continue
                    # Check if it's a directory by trying to CWD
                    is_dir = False
                    try:
                        self.ftp.cwd(name)
                        is_dir = True
                        self.ftp.cwd("..")
                    except ftplib.error_perm:
                        is_dir = False
                    items.append((name, is_dir))
            except Exception as e2:
                self.log(f"FTP nlst fallback also failed: {e2}")
        finally:
            try:
                self.ftp.cwd("/")
            except Exception:
                pass
        self.log(f"FTP Listing found {len(items)} items in {target}")
        return items


def make_m3u8(tracks: List[Track], remote_sep="/") -> str:
    # Generate m3u8 content
    # #EXTM3U
    # #EXTINF:-1,Title
    # path/to/file.mp3
    rt = "#EXTM3U\n\n"
    for t in tracks:
        if not t.relative_path:
            continue

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
            p = p[len(remote_sep) :]

        rt += f"#EXTINF:-1,{title}\n"
        rt += f"{p}\n\n"
    return rt


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
                select(Playlist).options(
                    joinedload(Playlist.tracks).joinedload(PlaylistTrack.track)
                )
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

            mode = settings.get("sync_mode", "adb")  # adb, rsync, ftp

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
                    if log_callback:
                        log_callback(f"Unknown mode: {mode}")

            await run_in_threadpool(_sync)


# --- __main__ entrypoint for standalone debug ---
if __name__ == "__main__":
    import sys
    import logging
    import asyncio

    # 標準出力にログを出す設定
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    async def main():
        def log_callback(msg):
            print(msg)

        await SyncService.run_sync(log_callback=log_callback)

    asyncio.run(main())
