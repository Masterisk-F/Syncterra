from logging import getLogger, StreamHandler, FileHandler, Formatter, DEBUG, WARNING

###
# 使い方
#
# モジュールの最初で
# from logger import setup_logger
# logger = setup_logger(__name__)
#
# ログを吐きたいところで
# logger.debug("ログログログ")
# logger.info("ログログログ")
# logger.worning("ログログログ")
# logger.error("ログログログ")
###


def setup_logger(name, logfile="Log.log"):
    logger = getLogger(name)

    formatter = Formatter(
        "%(asctime)s,%(levelname)s,%(filename)s - %(funcName)s,line=%(lineno)d,%(message)s",
        "%Y-%m-%dT%H:%M:%S",
    )

    sthdlr = StreamHandler()
    sthdlr.setFormatter(formatter)
    sthdlr.setLevel(WARNING)
    logger.addHandler(sthdlr)

    filhdlr = FileHandler(logfile, encoding="utf-8")
    filhdlr.setFormatter(formatter)
    filhdlr.setLevel(DEBUG)
    logger.addHandler(filhdlr)

    logger.setLevel(DEBUG)
    return logger
