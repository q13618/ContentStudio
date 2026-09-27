#! /usr/bin/env python3
#encoding: utf-8

#Filename: selfFileSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   本地文件系统(SELFFILE)的配置管理,
#沿用 ylwz 双文件机制(<fileID>.data 存内容 + <fileID>.info 存元信息)

_VERSION="20260918"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import local_settings as local_settings


_DEBUG = True

#当前运行环境
_SYS = local_settings._SYS

_SYS_SERVER_NAME = local_settings._SYS_SERVER_NAME

#项目根目录(code/), 用于本地开发时定位可写的数据目录
_CODE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCAL_DATA_DIR = os.path.join(_CODE_DIR, "data")


def _p(path):
    """统一转成 posix 风格并补尾斜杠"""
    return str(path).replace("\\", "/").rstrip("/") + "/"


_HOME_DIR = {
    "local":r"/data/contenthub",
    "server_01":r"/data/contenthub",
    "server_02":r"/data/contenthub",
    "test_server":r"/data/contenthub",
    "home":os.getenv("CH_HOME_DIR", r".."),
    }[_SYS]


LOCAL_FILE_SERVER_DIR_NAME = "temp"

#local server path
LOCAL_FILE_SERVER_PATH ={
    "local":f"http://127.0.0.1:9000/{LOCAL_FILE_SERVER_DIR_NAME}/",
    "server_01":f"https://www.iottest.online/{LOCAL_FILE_SERVER_DIR_NAME}/",
    "server_02":f"https://mindgram.iottest.online/{LOCAL_FILE_SERVER_DIR_NAME}/",
    "test_server":f"https://www.iottest.online/{LOCAL_FILE_SERVER_DIR_NAME}/",
    "home":os.getenv("CH_PUBLIC_BASE_URL", "http://192.168.100.100/").rstrip("/") + f"/{LOCAL_FILE_SERVER_DIR_NAME}/",
}[_SYS]

#local server path, local 环境指向本项目 <code>/data/webserver/temp/, 保证本地可跑
LOCAL_FILE_SERVER_BASE ={
    "local":_p(os.path.join(_LOCAL_DATA_DIR, "webserver", LOCAL_FILE_SERVER_DIR_NAME)),
    "server_01":r"/data/webserver/temp/",
    "server_02":r"/data/webserver/temp/",
    "test_server":r"/data/webserver/temp/",
    "home":r"/data/webserver/temp/",
}[_SYS]

LOCAL_FILE_TEMP_WEB_DIR = 'web/'

#local server file storage
# SELF_FILE_SERVER_STORAGE_IF_REMOTE = True #是否远程存储
SELF_FILE_SERVER_STORAGE_IF_REMOTE = False #是否远程存储

SELF_FILE_SERVER_STORAGE_ADDR = {
    "local":"127.0.0.1",
    "server_01":"127.0.0.1",
    "server_02":"127.0.0.1",
    "test_server":"127.0.0.1",
    "home":"127.0.0.1",
}[_SYS]

#SELFFILE 实际存储根目录, local 环境指向本项目 <code>/data/filestorage/, 保证本地可跑
SELF_FILE_SERVER_STORAGE_DIR ={
    "local":_p(os.path.join(_LOCAL_DATA_DIR, "filestorage")),
    "server_01":r"/data/filestorage/",
    "server_02":r"/data/filestorage/",
    "test_server":r"/data/filestorage/",
    "home":r"/data/filestorage/",
}[_SYS]

#本地目录下面最多有1000个目录,随机存储
LOCAL_FILE_STORAGE_DIR_MAX_NUM = 1000
LOCAL_FILE_STORAGE_DIR_LEN = 3 #1000个是3位从000-999


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)

    print ("_SYS_SERVER_NAME", _SYS_SERVER_NAME)
    print ("_HOME_DIR", _HOME_DIR)
    print ("LOCAL_FILE_SERVER_PATH", LOCAL_FILE_SERVER_PATH)
    print ("LOCAL_FILE_SERVER_BASE", LOCAL_FILE_SERVER_BASE)
    print ("SELF_FILE_SERVER_STORAGE_DIR", SELF_FILE_SERVER_STORAGE_DIR)
