import os
from audio_sync_data import AudioSyncData
from rsync_audio_synchronizer import RsyncAudioSynchronizer
from logger import setup_logger
logger = setup_logger(__name__)

if __name__ == "__main__":
    logger.info("audio_sync (rsync) start. path=" + os.path.dirname(__file__) + os.sep + "AudioSyncData.xlsx")
    RsyncAudioSynchronizer(
        AudioSyncData(os.path.dirname(__file__)+os.sep+"AudioSyncData.xlsx"),
        remote_os_sep="/",
        ip_addr="192.168.10.11",
        port=2222,
        user="tatu"
    ).synchronize()
    logger.info("audio_sync (rsync) end.")
