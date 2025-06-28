import os

from audio_sync_data import AudioSyncData
from audio_synchronizer import AdbAudioSynchronizer
from audio_synchronizer import FtpAudioSynchronizer
from logger import setup_logger
logger = setup_logger(__name__)

#dockerのテスト環境で実行する
if __name__ == "__main__":
    logger.info("audio_sync start. path=" + os.path.dirname(__file__) + "\AudioSyncData.xlsx")
    #AdbAudioSynchronizer(AudioSyncData(os.getcwd()+"\AudioSyncData.xlsx")).synchronize()
    FtpAudioSynchronizer(
        AudioSyncData(os.path.dirname(__file__)+"\AudioSyncData.xlsx"),
        ip_addr="192.168.10.70",
        port=21,
        user="username",
        passwd="mypass"
    ).synchronize()
    logger.info("audio_sync end.")
