import os
import tempfile
import subprocess
from logger import setup_logger
logger = setup_logger(__name__)

class RsyncAudioSynchronizer:
    def __init__(self, audio_sync_data, remote_os_sep, ip_addr, port=22, user=None):
        self.audio_sync_data = audio_sync_data
        self.remote_os_sep = remote_os_sep
        self.ip_addr = ip_addr
        self.port = port
        self.user = user

    def synchronize(self, checksum=False):
        # 同期対象ファイルリストを一時ファイルに書き出す
        include_set = set()
        def add_all_dirs(path):
            parts = path.split(self.remote_os_sep)
            for i in range(1, len(parts)):
                dir_path = self.remote_os_sep.join(parts[:i])
                if dir_path:
                    include_set.add(dir_path + "/")
            include_set.add(path)
        for audio in self.audio_sync_data.sheet_Albums:
            if getattr(audio, 'sync', None) == "○":
                rel_path = audio.filepath_to_relative.replace(os.sep, self.remote_os_sep)
                add_all_dirs(rel_path)
        for audio in self.audio_sync_data.sheet_Not_in_Albums:
            if getattr(audio, 'sync', None) == "○":
                rel_path = audio.filepath_to_relative.replace(os.sep, self.remote_os_sep)
                add_all_dirs(rel_path)
        # プレイリストは後で個別送信するため、ここでは含めない

        fd, include_path = tempfile.mkstemp()
        try:
            with open(include_path, "w", encoding="utf-8") as f:
                for path in include_set:
                    f.write(path + "\n")
                f.flush()
            # sortとuniqをコマンドで実行
            subprocess.run(f"sort {include_path} | uniq > {include_path}.tmp && mv {include_path}.tmp {include_path}", shell=True, check=True)
            # rsyncコマンドの組み立て（音楽ファイルのみ）
            first_audio = next(iter(self.audio_sync_data.sheet_Albums), None)
            if first_audio is None:
                raise RuntimeError("No audio files found in sheet_Albums.")
            src_dir = first_audio.filepath_from[:-len(first_audio.filepath_to_relative)]
            dest = f"{self.user+'@' if self.user else ''}{self.ip_addr}:~"
            rsync_cmd = [
                "rsync", "-avz", "--delete", "--stats", f"--include-from={include_path}", "--exclude=*", "-e",
                f"ssh -p {self.port}", src_dir + "/", dest
            ]
            if checksum:
                rsync_cmd.insert(1, "-c")
            logger.info("Executing rsync: " + " ".join(rsync_cmd))
            try:
                proc = subprocess.Popen(rsync_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    print(line, end="")
                    logger.info(line.rstrip())
                proc.wait()
                if proc.returncode != 0:
                    print("rsync failed: returncode", proc.returncode)
            except Exception as e:
                print("rsync failed:", e)
            # プレイリストm3uファイルを一時作成し、個別にrsyncで送信
            for name, playlist in self.audio_sync_data.sheets_playlist.items():
                fd_m3u, m3u_path = tempfile.mkstemp(suffix=".m3u")
                try:
                    with open(m3u_path, "w", encoding="utf-8") as f:
                        f.write(playlist.make_m3u8(sep=self.remote_os_sep))
                        f.flush()
                    remote_path = f"{name}.m3u"
                    rsync_m3u_cmd = [
                        "rsync", "-avz", "-e", f"ssh -p {self.port}", m3u_path, f"{dest}/{remote_path}"
                    ]
                    logger.info(f"Send playlist: {' '.join(rsync_m3u_cmd)}")
                    try:
                        proc = subprocess.Popen(rsync_m3u_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        for line in proc.stdout:
                            print(line, end="")
                            logger.info(line.rstrip())
                        proc.wait()
                        if proc.returncode != 0:
                            print(f"rsync playlist failed: returncode {proc.returncode}")
                    except Exception as e:
                        print(f"rsync playlist failed: {e}")
                finally:
                    os.close(fd_m3u)
                    os.remove(m3u_path)
        finally:
            os.close(fd)
            os.remove(include_path)
