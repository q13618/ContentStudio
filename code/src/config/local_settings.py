#! /usr/bin/env python3
#encoding: utf-8

#Filename: local_settings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   contentHub(内容中枢) 运行环境入口,
#仅负责声明当前环境(_SYS)与服务名(_SYS_SERVER_NAME), 不承载业务配置

# 本地开发环境
# _SYS = "local"

# 服务器01生产环境(阿里云OSS)
# _SYS = "server_01"

# 服务器01生产环境(阿里云OSS)
import os
# ★ docker: 可用环境变量 CH_SYS 覆盖(容器内为 "home"), 未设置时保持原值
_SYS = os.getenv("CH_SYS", "server_02")

# 测试服务器环境
# _SYS = "test_server"

# 家庭/本地服务器环境
# _SYS = "home"

#local server name
_SYS_SERVER_NAME = os.getenv("CH_SERVER_NAME", "chserver_01")

if __name__ == "__main__":
    # import pdb
    # pdb.set_trace()
    print ("_SYS:",_SYS)
    print ("_SYS_SERVER_NAME:",_SYS_SERVER_NAME)
