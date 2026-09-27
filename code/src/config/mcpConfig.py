#! /usr/bin/env python3
#encoding: utf-8

#Filename: mcpConfig.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   contentHub(内容中枢) MCP服务配置文件,
#负责服务名/版本号/监听地址/传输协议/下游REST服务地址/鉴权入口读取
#参照 stock_rotation_strategy/src/config/mcpConfig.py 的结构与命名约定

_VERSION = "20260917"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

#global defintion/common var etc.
from config import basicSettings as settings


#当前运行环境(_SYS: local/server_01/server_02/test_server/home)
_SYS = settings._SYS
_SYS_SERVER_NAME = settings._SYS_SERVER_NAME
#兼容: basicSettings 未定义 _HOME_DIR 时回退空串(日志目录由 misc.setLogNew 内部兜底)
_HOME_DIR = getattr(settings, "_HOME_DIR", "")


#MCP服务名(对应mcp_config.json中的serverName)
MCP_SERVER_NAME = "contenthub-mcp-server"

#MCP服务版本号
MCP_SERVER_VERSION = "1.0.0"

#MCP服务监听主机(0.0.0.0=监听所有网络接口, 允许来自任意网络地址的连接)
MCP_SERVER_HOST = "0.0.0.0"

#MCP服务监听端口(★ 8891: 避开 stock-mcp-server 占用的 8889 与 contentHub 早期占位口径 8890)
MCP_SERVER_PORT = 8891

#MCP传输协议: streamable-http(网络HTTP)/sse(网络SSE)/stdio(标准输入输出)
# streamable-http 与 sse 为网络传输, 支持通过 host/port 进行远程监听
MCP_TRANSPORT = "streamable-http"

#contentHub REST服务默认访问地址(入口为 main/chAPI.py 的 /chapi/<urlPath>)
CH_SERVER_HOST = os.getenv("CH_MCP_UPSTREAM_HOST", "127.0.0.1")
CH_SERVER_PORT = int(os.getenv("CH_MCP_UPSTREAM_PORT", "80"))
CH_SERVER_ROOT_PATH = ""

#contentHub 服务sessionID, 优先从环境变量读取, 其次使用默认账号
CH_SESSION_ID_ENV_KEY = "CONTENTHUB_SESSION_ID"
CH_SESSION_ID = os.environ.get(CH_SESSION_ID_ENV_KEY, "")

#工具返回结果截断条数, 防止token超限
TOOL_RESULT_LIMIT = 30

#单次查询默认返回条数上限(MCP工具入参 limit 缺省值)
QUERY_DEFAULT_LIMIT = 30

#REST请求超时时间(秒)
HTTP_REQUEST_TIMEOUT = 30

#MCP鉴权配置(FastMCP AuthSettings必填字段, 当前为占位值; 无auth_server_provider时不触发OAuth流程)
#可通过环境变量覆盖
MCP_AUTH_ISSUER_URL = os.environ.get("MCP_AUTH_ISSUER_URL", "http://127.0.0.1:8891")
MCP_AUTH_RESOURCE_SERVER_URL = os.environ.get("MCP_AUTH_RESOURCE_SERVER_URL", "http://127.0.0.1:8891")


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print("_SYS:", _SYS)
    print("MCP_SERVER_NAME:", MCP_SERVER_NAME)
    print("MCP_SERVER_VERSION:", MCP_SERVER_VERSION)
    print("MCP_SERVER_HOST:", MCP_SERVER_HOST)
    print("MCP_SERVER_PORT:", MCP_SERVER_PORT)
    print("MCP_TRANSPORT:", MCP_TRANSPORT)
    print("CH_SERVER_HOST:", CH_SERVER_HOST)
    print("CH_SERVER_PORT:", CH_SERVER_PORT)
