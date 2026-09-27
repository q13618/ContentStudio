#! /usr/bin/env python3
#encoding: utf-8

#Filename: mysqlSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-18
#Description:   contentHub(内容中枢) MySQL 数据库连接配置: 读写分离 host/port/db/user/passwd,
#按 _SYS 映射取值(改环境不改代码); 连接对象由 common/mysqlHandle.py 构造后注入。
#
#约束(对齐主计划 3.2 实测差异 D1):
#  1. 本项目沿用基线形态——pymysql 单条长连接注入式(dbW/dbR), 不引入连接池;
#  2. 口令不写死真实密钥(主计划 R-19): 一律优先取环境变量, 未设置时仅本地开发使用默认值;
#  3. 无数据库环境下(仅做静态检查/通过 HTTP 调用下游)设置 MYSQL_SKIP_CONNECT=1,
#     导入本模块即不建连, mysqlDB 为 None, 避免导入期阻塞或失败。

_VERSION="20260920"

import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)

from config import local_settings as local_settings

from common import  mysqlHandle as mysqlHandle

#当前运行环境 local | server_01 | server_02 | test_server | home
_SYS = local_settings._SYS


#mysql数据库信息  begin
#主库，写记录
MYSQL_WRITE_HOST = {
    "local":"127.0.0.1",
    "server_01":"127.0.0.1",
    "server_02":"rm-f8zd6012efm91y10d.mysql.rds.aliyuncs.com",
    "test_server":"127.0.0.1",
    "home":os.getenv("CH_MYSQL_HOST", "192.168.100.100"),
    }[_SYS]

MYSQL_WRITE_PORT = {
    "local":3306,
    "server_01":3306,
    "server_02":3306,
    "test_server":3306,
    "home":int(os.getenv("CH_MYSQL_PORT", "3306")),
    }[_SYS]

MYSQL_WRITE_DB = {
    "local":"contenthub_data",
    "server_01":"contenthub_data",
    "server_02":"contenthub_data",
    "test_server":"contenthub_test",
    "home":os.getenv("CH_MYSQL_DB", "contenthub_data"),
    }[_SYS]

MYSQL_WRITE_USER = {
    "local":"your_account",
    "server_01":"your_account",
    "server_02":"your_account",
    "test_server":"your_account",
    "home":os.getenv("CH_MYSQL_USER", "your_account"),
    }[_SYS]

#口令: 环境变量 CH_MYSQL_WRITE_PASSWD 优先, 未设置时仅本地/家庭环境回落开发默认值;
#      线上环境默认空串, 必须在部署时通过环境变量或 KMS 注入(禁止写死在代码库)
MYSQL_WRITE_PASSWD = {
    "local": os.getenv("CH_MYSQL_WRITE_PASSWD", "") or "your_password",
    "server_01": os.getenv("CH_MYSQL_WRITE_PASSWD", "") or "your_password",
    "server_02": os.getenv("CH_MYSQL_WRITE_PASSWD", "") or "your_password",
    "test_server": os.getenv("CH_MYSQL_WRITE_PASSWD", "") or "your_password",
    "home": os.getenv("CH_MYSQL_WRITE_PASSWD", "") or "your_password",
    }[_SYS]

#从库，读记录
MYSQL_READ_HOST = {
    "local":"127.0.0.1",
    "server_01":"127.0.0.1",
    "server_02":"rm-f8zd6012efm91y10d.mysql.rds.aliyuncs.com",
    "test_server":"127.0.0.1",
    "home":os.getenv("CH_MYSQL_HOST", "192.168.100.100"),
    }[_SYS]

MYSQL_READ_PORT = {
    "local":3306,
    "server_01":3306,
    "server_02":3306,
    "test_server":3306,
    "home":int(os.getenv("CH_MYSQL_PORT", "3306")),
    }[_SYS]

MYSQL_READ_DB = {
    "local":"contenthub_data",
    "server_01":"contenthub_data",
    "server_02":"contenthub_data",
    "test_server":"contenthub_test",
    "home":os.getenv("CH_MYSQL_DB", "contenthub_data"),
    }[_SYS]

MYSQL_READ_USER = {
    "local":"your_account",
    "server_01":"your_account",
    "server_02":"your_account",
    "test_server":"your_account",
    "home":os.getenv("CH_MYSQL_USER", "your_account"),
    }[_SYS]

#口令: 环境变量 CH_MYSQL_READ_PASSWD 优先, 未设置时回落写库口令
MYSQL_READ_PASSWD = {
    "local": os.getenv("CH_MYSQL_READ_PASSWD", "") or MYSQL_WRITE_PASSWD,
    "server_01": os.getenv("CH_MYSQL_READ_PASSWD", "") or MYSQL_WRITE_PASSWD,
    "server_02": os.getenv("CH_MYSQL_READ_PASSWD", "") or MYSQL_WRITE_PASSWD,
    "test_server": os.getenv("CH_MYSQL_READ_PASSWD", "") or MYSQL_WRITE_PASSWD,
    "home": os.getenv("CH_MYSQL_READ_PASSWD", "") or MYSQL_WRITE_PASSWD,
    }[_SYS]

#mysql数据库信息  end


#是否跳过建立数据库连接:
#默认不跳过(与既有部署行为完全一致); 在不需要直连数据库的设备上(例如仅通过 HTTP 调用 /chapi 的
#渲染 worker、MCP 进程、CI 静态检查), 设置环境变量 MYSQL_SKIP_CONNECT=1, 可避免导入本模块时
#因数据库不可达而失败/长时间阻塞(此时 mysqlDB 为 None, 任何直连数据库的调用都会失败,
#但 HTTP 路径不依赖它)
_SKIP_CONNECT = os.getenv("MYSQL_SKIP_CONNECT", "").strip().lower() in ("1", "true", "yes", "y", "on")


if _SKIP_CONNECT:
    mySqlW = None
    mySqlR = None
    mysqlDB = None
else:
    #主库，写记录
    mySqlW = mysqlHandle.getMysqlDB(MYSQL_WRITE_HOST ,MYSQL_WRITE_USER,MYSQL_WRITE_PASSWD,MYSQL_WRITE_DB)

    #从库，读记录
    mySqlR = mysqlHandle.getMysqlDB(MYSQL_READ_HOST ,MYSQL_READ_USER,MYSQL_READ_PASSWD,MYSQL_READ_DB)

    mysqlDB = mysqlHandle.mysqlHandle(dbW=mySqlW,dbR=mySqlR)


def mysqlReconnect():
    """重建读写连接(连接失效时调用); 跳过直连模式下保持 mysqlDB 为 None 并原样返回"""
    global mySqlW, mySqlR, mysqlDB
    if _SKIP_CONNECT:
        return mysqlDB
    #主库，写记录
    mySqlW = mysqlHandle.getMysqlDB(MYSQL_WRITE_HOST ,MYSQL_WRITE_USER,MYSQL_WRITE_PASSWD,MYSQL_WRITE_DB)

    #从库，读记录
    mySqlR = mysqlHandle.getMysqlDB(MYSQL_READ_HOST ,MYSQL_READ_USER,MYSQL_READ_PASSWD,MYSQL_READ_DB)

    mysqlDB = mysqlHandle.mysqlHandle(dbW=mySqlW,dbR=mySqlR)

    return mysqlDB


_DEBUG = True  #预设trace开关，禁止修改

if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)
    print ("_SKIP_CONNECT",_SKIP_CONNECT)
    print ("MYSQL_WRITE_HOST",MYSQL_WRITE_HOST)
    print ("MYSQL_WRITE_DB",MYSQL_WRITE_DB)
    print ("MYSQL_WRITE_USER",MYSQL_WRITE_USER)

    print ("MYSQL_READ_HOST",MYSQL_READ_HOST)
    print ("MYSQL_READ_DB",MYSQL_READ_DB)
    print ("MYSQL_READ_USER",MYSQL_READ_USER)

    print ("mySqlW",mySqlW)
    print ("mySqlR",mySqlR)

    print ("mysqlDB",mysqlDB)
