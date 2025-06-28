import os

from audio_sync_data import AudioSyncData
from audio_synchronizer import AdbAudioSynchronizer
from audio_synchronizer import FtpAudioSynchronizer
from logger import setup_logger
logger = setup_logger(__name__)


if __name__ == "__main__":
    logger.info("audio_sync start. path=" + os.path.dirname(__file__) + os.sep + "AudioSyncData.xlsx")
    #AdbAudioSynchronizer(AudioSyncData(os.getcwd()+"\AudioSyncData.xlsx")).synchronize()
    FtpAudioSynchronizer(
        AudioSyncData(os.path.dirname(__file__)+os.sep+"AudioSyncData.xlsx"),
        ip_addr="192.168.10.11",
        port=2221,
        user="francis",
        passwd="francis"
    ).synchronize()

    logger.info("audio_sync end.")
