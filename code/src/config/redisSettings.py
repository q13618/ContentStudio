#! /usr/bin/env python3
#encoding: utf-8

#Filename: netQualityBasicSettings.py  
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2022-08-23
#Description:   通用的配置管理,网络地址等

_VERSION="20260917"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from common import redisHandle as redisHandle

from config import basicSettings as settings


#生产环境 rss | 测试环境 dss
_SYS = settings._SYS
#_SYS = "server_01"
#_SYS = "local"


#redis数据库信息  begin
_REDIS_DB_PORT_ORIGINAL = 6379
_REDIS_DB_PORT_YLWZ = 6378
_REDIS_DB_PORT_DEFAULT = _REDIS_DB_PORT_ORIGINAL
_REDIS_DB_NO_DEFAULT = 0


#iottest-01 -> iottest-01 
#vc-voice -> iottest-01 

#主库，写记录
REDIS_WRITE_HOST = {
    "local":"127.0.0.1",
    "server_01":"127.0.0.1", 
    "server_02":"127.0.0.1", 
    "test_server":"127.0.0.1",
    "home":os.getenv("CH_REDIS_HOST", "192.168.100.100"),
    }[_SYS]

REDIS_WRITE_PORT = {
    "local":_REDIS_DB_PORT_ORIGINAL,
    "server_01":_REDIS_DB_PORT_DEFAULT, 
    "server_02":_REDIS_DB_PORT_DEFAULT, 
    "test_server":_REDIS_DB_PORT_DEFAULT,
    "home":_REDIS_DB_PORT_DEFAULT,
    }[_SYS]

REDIS_WRITE_DB = {
    "local":_REDIS_DB_NO_DEFAULT,
    "server_01":_REDIS_DB_NO_DEFAULT, 
    "server_02":_REDIS_DB_NO_DEFAULT, 
    "test_server":_REDIS_DB_NO_DEFAULT,
    "home":_REDIS_DB_NO_DEFAULT,
   }[_SYS]

#从库，读记录
REDIS_READ_HOST = {
    "local":"127.0.0.1",
    "server_01":"127.0.0.1", 
    "server_02":"127.0.0.1", 
    "test_server":"127.0.0.1",
    "home":os.getenv("CH_REDIS_HOST", "192.168.100.100"),
    }[_SYS]
    
REDIS_READ_PORT = {
    "local":_REDIS_DB_PORT_ORIGINAL,
    "server_01":_REDIS_DB_PORT_DEFAULT, 
    "server_02":_REDIS_DB_PORT_DEFAULT, 
    "test_server":_REDIS_DB_PORT_DEFAULT,
    "home":_REDIS_DB_PORT_DEFAULT,
    }[_SYS]
    
REDIS_READ_DB = {
    "local":_REDIS_DB_NO_DEFAULT,
    "server_01":_REDIS_DB_NO_DEFAULT, 
    "server_02":_REDIS_DB_NO_DEFAULT, 
    "test_server":_REDIS_DB_NO_DEFAULT, 
    "home":_REDIS_DB_NO_DEFAULT, 
    }[_SYS]

REDIS_USERNAME = {
    "local":"",
    "server_01":"", 
    "server_02":"", 
    "test_server":"",
    "home":"", 
    }[_SYS]

REDIS_PASSWD = {
    "local":"", 
    "server_01":"", 
    "server_02":"", 
    "test_server":"",
    "home":"", 
    }[_SYS]


passwordPromptMsg = ""
if REDIS_PASSWD == "":
    passwordPromptMsg = "no password"
    #主库，写记录
    dbMainW = redisHandle.getRedisDB(host=REDIS_WRITE_HOST,port=REDIS_WRITE_PORT,db=REDIS_WRITE_DB)
    #从库，读记录
    dbMainR = redisHandle.getRedisDB(host=REDIS_READ_HOST,port=REDIS_READ_PORT,db=REDIS_READ_DB)
else:
    passwordPromptMsg = "with password"
    #主库，写记录
    dbMainW = redisHandle.getRedisDB(host=REDIS_WRITE_HOST,port=REDIS_WRITE_PORT,db=REDIS_WRITE_DB, username=REDIS_USERNAME, passwd=REDIS_PASSWD)
    #从库，读记录
    dbMainR = redisHandle.getRedisDB(host=REDIS_READ_HOST,port=REDIS_READ_PORT,db=REDIS_READ_DB, username=REDIS_USERNAME, passwd=REDIS_PASSWD)
    
redisMainDB = redisHandle.RedisHandle(dbW=dbMainW,dbR=dbMainR)
pipeMainHandle = redisHandle.PipeHandle(redisMainDB)

#redis数据库信息  end

if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)
    print ("REDIS_WRITE_HOST",REDIS_WRITE_HOST)
    print ("REDIS_WRITE_PORT",REDIS_WRITE_PORT)
    print ("REDIS_WRITE_DB",REDIS_WRITE_DB)
    print ("REDIS_READ_HOST",REDIS_READ_HOST)
    print ("REDIS_READ_PORT",REDIS_READ_PORT)
    print ("REDIS_READ_DB",REDIS_READ_DB)
    print ("dbW",dbMainW)
    print ("dbR",dbMainR)
    print ("redisDB",redisMainDB)
    print("PASSWD",passwordPromptMsg)
    
