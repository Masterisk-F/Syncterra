import os
import subprocess
import sys
from audio_sync_data import AudioSyncData

from logger import setup_logger

logger = setup_logger(__name__)

# 使い方
# 通常時
# python .\audio_list.py
#
# AudioSyncData.xlsxのタグ情報をすべて更新したいとき
# python .\audio_list.py -all
#
#


if __name__ == "__main__":
    logger.info(
        "audio_list start. path="
        + os.path.dirname(__file__)
        + os.sep
        + "AudioSyncData.xlsx"
    )

    all = len(sys.argv) >= 2 and sys.argv[1] == "-all"

    data = AudioSyncData(os.path.dirname(__file__) + os.sep + "AudioSyncData.xlsx")
    data.update(update_all=all)
    data.save(os.path.dirname(__file__) + os.sep + "AudioSyncData.xlsx")
    logger.info("audio_list end.")

    subprocess.run(
        "xdg-open AudioSyncData.xlsx", cwd=os.path.dirname(__file__), shell=True
    )
