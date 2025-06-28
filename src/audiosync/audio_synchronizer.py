import os
import errno
from posixpath import split
import tempfile
from abc import ABCMeta, abstractmethod

from adbutils import adb

import subprocess

from logger import setup_logger
logger = setup_logger(__name__)

class AudioSynchronizer(metaclass=ABCMeta):
    
    def __init__(self,audio_sync_data,remote_os_sep):
        self.audio_sync_data = audio_sync_data
        self.__remote_os_sep = remote_os_sep #同期先における、ディレクトリ区切り文字(Winとlinux系で違う)
    
    @abstractmethod
    def cp(self,filepath_from,relative_path_to):
        #filepath_fromのファイルをrelative_path_toへコピーする
        #relative_path_toはファイル
        #
        #filepath_from : 文字列。ローカルのファイルパス。
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでのコピー先。ファイル名
        pass

    @abstractmethod
    def rm_remote(self,relative_filepath_to):
        #コピー先ディレクトリのrelative_filepath_toにあるファイルを削除する
        #
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでの削除ファイル。
        pass

    @abstractmethod
    def mkdir_p_remote(self,relative_filepath_to):
        #コピー先ディレクトリにディレクトリrelative_filepath_toを作成する
        #-rオプション付き相当のmkdirとする
        #ディレクトリを作らなくてもファイルを置けるなら空の実装で良い
        pass
    
    @abstractmethod
    def ls_remote(self,relative_dir=""):
        #コピー先ディレクトリでのls結果を返す
        #「ls ${audio_sync_data.dir_to_synctonize[0]}${relative_dir}」に相当
        #
        #戻り値 : (String:ファイル名・ディレクトリ名, Bool:ディレクトリか否か)のリスト
        #
        #存在しないファイルやディレクトリを指定したときは、次のように例外を投げること。
        #raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), ファイル名)
        pass

    def put_playlist_file(self,relative_dir=""):
        for name, playlist in self.audio_sync_data.sheets_playlist.items():
            fd, path = tempfile.mkstemp()
            with open(path,"w",encoding="utf-8")as f:
                f.write(playlist.make_m3u8())
                f.flush()
            self.cp(path, relative_dir + self.__remote_os_sep + name + ".m3u")
            os.close(fd)
            os.remove(path)

    def synchronize(self):
        #同期メイン処理。オーバーライドの必要なし
        #いまのところ、audio_sync_data.dir_to_synchronize[0]だけの同期に対応

        dict_from = {}
        #dictionary{コピー先相対ファイルパス: (同期済みフラグ, Audioインスタンス)}
        dict_to = {}
        #dictionary{コピー先相対ファイルパス: ファイル保持フラグ}
        
        #コピー元のファイルを一覧化
        logger.debug("read data for synchronize. sheet=Albums")
        for audio in self.audio_sync_data.sheet_Albums:
            dict_from[audio.filepath_to_relative] = (False, audio)
            #list_from.append([False,(audio.filepath_to_relative, False)])
        logger.debug("read data for synchronize. sheet=Not in Albums")
        for audio in self.audio_sync_data.sheet_Not_in_Albums:
            dict_from[audio.filepath_to_relative] = (False, audio)
            #list_from.append([False,(audio.filepath_to_relative, False)])

        #コピー先のファイルを一覧化(パスでの文字列比較のため、ディレクトリ区切り文字はos.sepにしてdict_toに入れる！)
        def make_list_remote(relative_path, root_path):
            logger.debug("execute \"ls\" on remote. relative_path=" + relative_path + ", root_path=" + root_path)
            print(".", end="", flush=True)
            try :
                for filename, is_dir in self.ls_remote(relative_path):
                    if is_dir:
                        logger.debug(relative_path + self.__remote_os_sep + filename + " is directory.")
                        make_list_remote(relative_path + self.__remote_os_sep + filename, root_path)
                    else:
                        logger.debug(relative_path + self.__remote_os_sep + filename + " is file.")
                        dict_to[relative_path.replace(self.__remote_os_sep, os.sep) + os.sep + filename] = False
                        #list_to.append([False,(relative_path + os.sep + filename, is_dir)])
            except FileNotFoundError:
                pass        
        print("scanning remote",end="")
        make_list_remote("",self.audio_sync_data.dir_to_synchronize[0])
        print("")

        #AudioSyncDataでチェックが付いていて、コピー先ファイルの一覧にあるファイルに、from,to双方フラグ建てる
        for relative_filepath, (chkflg, audio) in dict_from.items():
            if audio.sync == "○" and relative_filepath in dict_to:
                logger.info(audio.filename + " already exists on remote.")
                dict_to[relative_filepath] = True
                dict_from[relative_filepath]= (True, audio)
        
        #コピー先でファイル保持フラグ立ってない音楽ファイルを削除（拡張子で判断）
        for relative_filepath, chkflg in dict_to.items():
            if chkflg == False:
                if os.path.splitext(relative_filepath)[1] in self.audio_sync_data.include_extention:
                    logger.info("remove file on remote. path=" + relative_filepath.replace(os.sep, self.__remote_os_sep))
                    print("remove file on remote. path=" + relative_filepath.replace(os.sep, self.__remote_os_sep))
                    self.rm_remote(relative_filepath.replace(os.sep, self.__remote_os_sep))
        
        #AudioSyncDataでチェックがついて、かつ同期済みフラグの付いていないファイルをコピー先へpush。ディレクトリが無いなら前もってmkdir
        def num_of_cp():
            for relative_filepath, (chkflg, audio) in dict_from.items():
                if chkflg == False and audio.sync == "○":
                    yield None
        n = len([None for _ in num_of_cp()])
        i = 0
        for relative_filepath, (chkflg, audio) in dict_from.items():
            if chkflg == False and audio.sync == "○":
                i += 1
                print(str(i) + "/" + str(n) + " Copy file. path=" + audio.filepath_to_relative.replace(os.sep, self.__remote_os_sep))
                try:
                    #TODO : ディレクトリ存在確認とりあえずの実装。existsメソッドとか追加したほうが良いかも
                    self.ls_remote(os.path.dirname(audio.filepath_to_relative).replace(os.sep, self.__remote_os_sep))
                except FileNotFoundError:
                    logger.info("make directory on remote. path=" + os.path.dirname(audio.filepath_to_relative).replace(os.sep, self.__remote_os_sep))
                    self.mkdir_p_remote(os.path.dirname(audio.filepath_to_relative).replace(os.sep, self.__remote_os_sep))
                logger.info("copy file. path=" + audio.filepath_to_relative.replace(os.sep, self.__remote_os_sep))
                self.cp(audio.filepath_from, audio.filepath_to_relative.replace(os.sep, self.__remote_os_sep))
        
        #playlistコピー
        #TODO : プレイリスト削除実装
        self.put_playlist_file()
    


class AdbAudioSynchronizer(AudioSynchronizer):

    def __init__(self, audio_sync_data):
        super().__init__(audio_sync_data,"/")
        
        #self.device = adb.device()
        #デバイスが接続されていなければRuntimeErrorを投げる


    def cp(self,filepath_from,relative_path_to):
        #filepath_fromのファイルをrelative_path_toへコピーする
        #relative_path_toはファイル
        #
        #filepath_from : 文字列。ローカルのファイルパス。
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでのコピー先。ファイル名

        #self.device.sync.push(filepath_from, self.dir_to_synchronize[0] + relative_filepath_to)
        command = "adb push \"" + filepath_from + "\" \""+ (self.audio_sync_data.dir_to_synchronize[0] + relative_path_to) + "\""
        result = subprocess.run(command, encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug(command + ". stdout=" + result.stdout + " stderr=" + result.stderr)
        if result.stderr != "":
            print(result.stdout + " " +result.stderr)
        pass

    def rm_remote(self,relative_filepath_to):
        #コピー先ディレクトリのrelative_filepath_toにあるファイルを削除する
        #
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでの削除ファイル。

        command = "adb shell rm -f \"" + self.adb_escape(self.audio_sync_data.dir_to_synchronize[0] + relative_filepath_to) + "\""
        result = subprocess.run(command, encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug(command + ". stdout=" + result.stdout + " stderr=" + result.stderr)
        if result.stderr != "" or result.stdout != "":
            print(result.stdout + " " +result.stderr)
        pass

    def mkdir_p_remote(self,relative_filepath_to):
        #コピー先ディレクトリにディレクトリrelative_filepath_toを作成する
        #-pオプション付き相当のmkdirとする
        #ディレクトリを作らなくてもファイルを置けるなら空の実装で良い

        #TODO : subprocessで自前実装
        command = "adb shell mkdir -p \"" + self.adb_escape(self.audio_sync_data.dir_to_synchronize[0] + relative_filepath_to) + "\""
        result = subprocess.run(command, encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.debug(command + ". stdout=" + result.stdout + " stderr=" + result.stderr)
        pass
    
    def ls_remote(self,relative_dir=""):
        #コピー先ディレクトリでのls結果を返す
        #「ls ${self.dir_to_synctonize[0]}${relative_dir}」に相当
        #
        #戻り値 : (String:ファイル名・ディレクトリ名, Bool:ディレクトリか否か)のリスト
        #
        #存在しないファイルやディレクトリを指定したときは、次のように例外を投げること。
        #raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), ファイル名)

        command = "adb shell ls \"" + self.adb_escape(self.audio_sync_data.dir_to_synchronize[0] + relative_dir) + "\" -F1"
        logger.debug(command)
        result = subprocess.run(command,encoding="utf-8", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stderr != "" and result.stderr[:-1].endswith("No such file or directory"):
            logger.debug(result.stderr[:-1])
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), self.audio_sync_data.dir_to_synchronize[0] + relative_dir)

        rt = []
        for file in result.stdout[:-1].split("\n"):
            if file == "":
                break
            if file.endswith("/"):
                rt.append((file[:-1], True))
            elif file.endswith("*"):
                rt.append((file[:-1], False))
            else:
                rt.append((file,False))
        logger.debug(rt)
        return rt

    def adb_escape(self, s):
        return s.replace(" ","\\ ").replace("(","\\(").replace(")","\\)").replace("&","\\&").replace("|","\\|").replace("'","\\'").replace("\"","\\\"").replace("\n","\\n")


import ftplib
class FtpAudioSynchronizer(AudioSynchronizer):
    
    def __init__(self, audio_sync_data, ip_addr = "192.168.10.3", port = 2221, user = "francis", passwd = "francis"):
        super().__init__(audio_sync_data,"/")
        logger.debug("FtpAudioSynchronizer started.")
        ftplib.FTP.encoding="utf-8"
        self.ftp = ftplib.FTP()
        self.ftp.set_pasv(True)
        self.ftp.connect(host=ip_addr,port=port)
        self.ftp.login(user=user, passwd=passwd)
        logger.debug("FTP login success.")

    def __del__(self):
        self.ftp.close()

    def cp(self,filepath_from,relative_path_to):
        #filepath_fromのファイルをrelative_path_toへコピーする
        #relative_path_toはファイル
        #
        #filepath_from : 文字列。ローカルのファイルパス。
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでのコピー先。ファイル名
        with open(filepath_from,"rb") as f:
            self.ftp.cwd(os.path.dirname(relative_path_to))
            stor="STOR " + os.path.basename(relative_path_to)
            self.ftp.storbinary(stor,f)
            self.ftp.cwd("/")
        logger.debug("success : FTP STOR " + os.path.basename(relative_path_to))


    def rm_remote(self,relative_filepath_to):
        #コピー先ディレクトリのrelative_filepath_toにあるファイルを削除する
        #
        #relative_filepath_to : 文字列。コピー先（リモート）での、相対パスでの削除ファイル。
        self.ftp.delete(relative_filepath_to)
        logger.debug("success : FTP delete " + relative_filepath_to)

    def mkdir_p_remote(self,relative_filepath_to):
        #コピー先ディレクトリにディレクトリrelative_filepath_toを作成する
        #-pオプション付き相当のmkdirとする
        #ディレクトリを作らなくてもファイルを置けるなら空の実装で良い
        
        dir_split = relative_filepath_to.split("/")
        for i in range(1,len(dir_split)):
            dir = "/".join(dir_split[:i+1])
            try:
                self.ftp.mkd(dir)
            except ftplib.error_perm as e:
                args = e.args
                logger.debug("ftp mkd err:" + args[0])
        logger.debug("success : FTP MKD " + relative_filepath_to)

         
    def ls_remote(self,relative_dir="/"):
        #コピー先ディレクトリでのls結果を返す
        #「ls ${audio_sync_data.dir_to_synctonize[0]}${relative_dir}」に相当
        #
        #戻り値 : (String:ファイル名・ディレクトリ名, Bool:ディレクトリか否か)のリスト
        #
        #存在しないファイルやディレクトリを指定したときは、次のように例外を投げること。
        #raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), ファイル名)

        #ディレクトリが無いかどうか確認する。（cwdできなければディレクトリなし）
        def exists_dir(dir):
            exists = False
            try:
                self.ftp.cwd(dir)
            except ftplib.error_perm as e:
                exists = False
            else:
                exists = True
            finally:
                self.ftp.cwd("")
            return exists
            
        if not exists_dir(relative_dir):
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), relative_dir)

        list = []
        self.ftp.cwd(relative_dir)
        for file in self.ftp.mlsd(path="", facts=["type"]):
            list.append((file[0],file[1]["type"]=="dir"))
        self.ftp.cwd("/")
        
        return list
