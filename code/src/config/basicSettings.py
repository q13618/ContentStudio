#! /usr/bin/env python3
#encoding: utf-8

#Filename: basicSettings.py
#Author: Steven Lian's team
#E-mail:  steven.lian@gmail.com
#Date: 2026-09-17
#Description:   contentHub(内容中枢) 通用配置管理: 文件系统开关/本地路径/图片规格/角色权限,
#配置驱动是三条红线之一: 文件后端一律经 FILE_SYSTEM_MODE 选择, 代码中不得出现硬编码厂商分支

_VERSION="20260921"


import os
import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
if sys.getdefaultencoding() != 'utf-8':
    pass
    #reload(sys)
    #sys.setdefaultencoding('utf-8')

from config import local_settings as local_settings


#当前运行环境 rss | 测试环境 dss
_SYS = local_settings._SYS

_SYS_SERVER_NAME = local_settings._SYS_SERVER_NAME


#项目根目录(code/), 用于本地开发时定位可写的数据目录
_CODE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#本地开发的数据根目录: <code>/data/
_LOCAL_DATA_DIR = os.path.join(_CODE_DIR, "data")


def _p(path):
    """统一转成 posix 风格并补尾斜杠, 与 pathlib.Path(...).as_posix() 语义对齐"""
    return str(path).replace("\\", "/").rstrip("/") + "/"


_HOME_DIR = {
    "local":r"/data/contenthub",
    "server_01":r"/data/contenthub",
    "server_02":r"/data/contenthub",
    "test_server":r"/data/contenthub",
    "home":os.getenv("CH_HOME_DIR", r"../.."),
    }[_SYS]

_DATA_DIR = {
    "local":f"{_HOME_DIR}/data",
    "server_01":f"{_HOME_DIR}/data",
    "server_02":f"{_HOME_DIR}/data",
    "test_server":f"{_HOME_DIR}/data",
    "home":f"{_HOME_DIR}/data",
    }[_SYS]

_DATA_CONFIG_DIR = {
    "local":f"{_DATA_DIR}/config",
    "server_01":f"{_DATA_DIR}/config",
    "server_02":f"{_DATA_DIR}/config",
    "test_server":f"{_DATA_DIR}/config",
    "home":f"{_DATA_DIR}/config",
    }[_SYS]


ACCOUNT_SERVICE_URL ={
    "local":"http://127.0.0.1:8160/acis",
    "server_01":"http://127.0.0.1:8160/acis",
    "server_02":"http://127.0.0.1:8160/acis",
    "test_server":"http://127.0.0.1:8160/acis",
    "home":os.getenv("CH_ACCOUNT_SERVICE_URL", "http://127.0.0.1:8160/acis"),
}[_SYS]


#服务器地址等信息
CH_SERVER_HOST ={
    "local":"127.0.0.1",
    "server_01":"www.test.com",
    "server_02":"www.test.net",
    "test_server":"www.test.com",
    "home":os.getenv("CH_SERVER_HOST", "192.168.5.100"),
}[_SYS]


#文件系统模式, ALIOSS(阿里云OSS), TENCENT(腾讯云COS), SELFFILE(本地文件), FASTDFS(FastDFS)
#多桶能力见 config/bucketSettings.py; 本地开发全程 SELFFILE, 云端能力在对应环境验证
FILE_SYSTEM_MODE = {
    "local":"ALIOSS",
    "server_01":"ALIOSS",
    "server_02":"ALIOSS",
    "test_server":"ALIOSS",
    "home":"SELFFILE",
}[_SYS]

#多bucket情况下, 选择bucket
FILE_SYSTEM_BUCKET_NAME = {
    "local":"artifact",
    "server_01":"artifact",
    "server_02":"artifact",
    "test_server":"artifact",
    "home":"artifact",
}[_SYS]


#fastdfs  cmd path (upload,delete, etc.)
FASTDFS_CMD_PATH ={
    "local":r"/usr/bin/",
    "server_01":r"/usr/bin/",
    "server_02":r"/usr/bin/",
    "test_server":r"/usr/bin/",
    "home":r"/usr/bin/",
}[_SYS]

#fastdfs client conf path
FASTDFS_CLIENT_CONF_PATH ={
    "local":r"/etc/fdfs/client.conf",
    "server_01":r"/etc/fdfs/client.conf",
    "server_02":r"/etc/fdfs/client.conf",
    "test_server":r"/etc/fdfs/client.conf",
    "home":r"/etc/fdfs/client.conf",
}[_SYS]

#fastdfs server path
FASTDFS_SERVER_PATH ={
    "local":"http://127.0.0.1:8080/",
    "server_01":"http://www.test.com:8080/",
    "server_02":"http://www.test.net:8080/",
    "test_server":"http://www.test.com:8080/",
    "home":"http://192.168.5.100:8080/",
}[_SYS]

LOCAL_FILE_SERVER_DIR_NAME = "temp"


#本地文件服务的物理根目录(web server 可访问区), local 环境指向本项目 <code>/data/webserver/, 保证本地可跑
LOCAL_WEBSERVER_ROOT_DIR = {
    "local":_p(os.path.join(_LOCAL_DATA_DIR, "webserver")),
    "server_01":r"/data/webserver/",
    "server_02":r"/data/webserver/",
    "test_server":r"/data/webserver/",
    "home":r"/data/webserver/",
}[_SYS]

#本地文件服务的访问根地址, 仅 local 为真机可访问, 其余为线上部署占位(上线前按实际域名替换)
LOCAL_WEBSERVER_ROOT_PATH ={
    "local":"http://127.0.0.1:9000/",
    "server_01":"https://www.test.com/",
    "server_02":"https://www.test.net/",
    "test_server":"https://www.test.com/",
    "home":os.getenv("CH_PUBLIC_BASE_URL", "http://192.168.5.100/"),
}[_SYS]

#local server path
LOCAL_FILE_SERVER_PATH = f"{LOCAL_WEBSERVER_ROOT_PATH}{LOCAL_FILE_SERVER_DIR_NAME}/"

#local server path
LOCAL_FILE_SERVER_BASE = f"{LOCAL_WEBSERVER_ROOT_DIR}{LOCAL_FILE_SERVER_DIR_NAME}/"

LOCAL_FILE_TEMP_WEB_DIR = 'web/'

CH_PROJECT_DATA_BASENAME = "ch_data"

CH_PROJECT_DATA_DIR = f'{LOCAL_WEBSERVER_ROOT_DIR}{CH_PROJECT_DATA_BASENAME}/'
CH_PROJECT_DATA_URL = f'{LOCAL_WEBSERVER_ROOT_PATH}{CH_PROJECT_DATA_BASENAME}/'

#本地文件系统(SELFFILE)根目录, 见 config/selfFileSettings.py

_LOCAL_FILE_STORAGE_DIR = _p(os.path.join(_LOCAL_DATA_DIR, "filestorage"))

LOCAL_FILE_SERVER_STORAGE_DIR ={
    "local":_LOCAL_FILE_STORAGE_DIR,
    "server_01":r"/data/filestorage/",
    "server_02":r"/data/filestorage/",
    "test_server":r"/data/filestorage/",
    "home":r"/data/filestorage/",
}[_SYS]

#本地目录下面最多有1000个目录,随机存储
LOCAL_FILE_STORAGE_DIR_MAX_NUM = 1000
LOCAL_FILE_STORAGE_DIR_LEN = 3 #1000个是3位从000-999

_STAT_DATA_FILE_NAME = "statDataFile.json"

#默认系统自动loginID
SYS_DEFAULT_AUTO_LOGINID ={
    "local":"10010001000",
    "server_01":"10010001000",
    "server_02":"10010001000",
    "test_server":"10010001000",
    "home":"10010001000",
}[_SYS]

#genDigistKey, 与 ylwz 文件服务协议保持同源(模式A: HTTP 调用 ylwz /hfile 时的 token 摘要)
GEN_DIGIST_KEY ={
    "local":"your_securet",
    "server_01":"your_securet",
    "server_02":"your_securet",
    "test_server":"your_securet",
    "home":os.getenv("CH_GEN_DIGIST_KEY", "your_securet"),
}[_SYS]

#file server upload url dataSet, 注意这个是一个字典
FILE_UPLOAD_URL ={
    "local":"http://www.test.com/upload",
    "server_01":"http://www.test.com/upload",
    "server_02":"http://www.test.net/upload",
    "test_server":"http://www.test.com/upload",
    "home":os.getenv("CH_FILE_UPLOAD_URL", "http://192.168.5.100/upload"),
}[_SYS]

#file server url dataSet, 注意这个是一个字典(按 serverName 取, 与 funcCommon.fileServerRequest 对齐)
FILE_SERVER_URL ={
    "local":"http://www.test.com/hfile",
    "server_01":"http://www.test.com/hfile",
    "server_02":"http://www.test.net/hfile",
    "test_server":"http://www.test.com/hfile",
    "home":os.getenv("CH_FILE_SERVER_URL", "http://192.168.5.100/hfile"),
}


#图片文件最大大小 (宽,高) (width, height)
MAX_PIC_SIZE = {
    "local":(1920, 1920),
    "server_01":(1920, 1920),
    "server_02":(1920, 1920),
    "test_server":(1920, 1920),
    "home":(1920, 1920),
}[_SYS]


#thumbnail 缩略图文件大小 (宽,高) (width, height)
THUMBNAIL_SIZE = {
    "local":(640, 640),
    "server_01":(640, 640),
    "server_02":(640, 640),
    "test_server":(640, 640),
    "home":(640, 640),
}[_SYS]


#允许的文件类型清单, 空列表=不做扩展名限制(与 ylwz 文件服务现状保持一致, 避免收紧后误伤)
ALLOW_FILE_TYPE_LIST = []


#role 角色权限
ROLE_RIGHT_SET ={
    "administrator":0,
    "manager":10,
    "operator":20,
    "customer":60,
    "visitor":70,
}

#account service roleName
# administrator,manager,operator,customer,visitor
accountServiceDefaultLoginID = "chuser"
accountServiceDefaultRoleName = "visitor"

#role 角色分配的功能清单
ROLE_EN_CN_NAME_DATA = {
    "administrator":"系统管理员",
    "manager":"管理员",
    "operator":"操作员",
    "customer":"普通用户",
    "visitor":"访客",
}

#本系统到 account service 的role转换表
# accout service:(administrator,manager,operator,customer,visitor)
ROLE_ACCOUNT_ROLE = {
    "administrator":"administrator",
    "manager":"manager",
    "operator":"operator",
    "customer":"customer",
    "visitor":"visitor",
}


#不需要sessionID的命令入口清单
NO_SESSIONID_CMD_LIST = {
    #业务标签
    "generalnext",
    "login", "registration","smsrequest","smsverify","resetpasswd","chkuserexist",
    #只读查询类入口(公开版式/平台/产物)
    "platformqry", "layoutqry", "artifactqry",
    }

#role 角色分配的功能清单
#说明: 与 chAPIPost 的 CMD 注册表一一对应; 12 张 ch_* 表各 4 个 CRUD 由生成器产出
_USER_CMDS = [
    "registration", "logout", "getuserinfo", "usersearch", "userinfoqry",
    "usersavedata", "usergetdata", "genusersessionid", "gethomepagedata",
]

#管理员专属用户管理 CMD(2026-09-20 补齐 museum 账号域三端点): ★ 与 registration 独立 ——
#自助注册(registration)对所有角色开放, 而用户「增/改/删」仅管理员可调
_USER_ADMIN_CMDS = ["useradd", "usermodify", "userdel"]

#执行用户管理动作所需的角色清单: 驱动下方 ROLE_CMD_LIST 的授权(请求级判定);
#处理器侧的管理员判定统一复用 common/funcCommon.py::chkIsManager(roleName) —— administrator 或 manager,
#两处口径必须一致(改动本清单时, 请同步 chkIsManager 的角色集合)。
USER_ADMIN_ROLE_LIST = ["administrator", "manager"]

# 12 张 ch_* 表的 CRUD 命令(ch_topic / ch_topic_asset / ch_asset / ch_layout / ch_platform /
# ch_render_job / ch_artifact / ch_account / ch_publish_record / ch_mcp_token / ch_audit_log / ch_topic_version)
_CRUD_TITLES = [
    "topic", "topicasset", "asset", "layout",
    "platform", "renderjob", "artifact", "account",
    "publishrecord", "mcptoken", "auditlog", "topicversion",
]

_CRUD_CMDS = []
for _title in _CRUD_TITLES:
    _CRUD_CMDS += [f"{_title}add", f"{_title}del", f"{_title}modify", f"{_title}qry"]

# 6 个新增业务端点(见 plan/chAPIPost分拆方案.md)
_BIZ_CMDS = [
    "topicrender", "artifactpack", "publishpush", "publishcheck", "accounthealth", "mcpinvoke",
]

ROLE_CMD_LIST =\
{
"administrator": _USER_CMDS + _CRUD_CMDS + _BIZ_CMDS,
"manager":       _USER_CMDS + _CRUD_CMDS + _BIZ_CMDS,
"operator":      _USER_CMDS + _BIZ_CMDS + [
    #主题/素材/渲染域: 全权
    "topicadd", "topicdel", "topicmodify", "topicqry",
    "topicassetadd", "topicassetdel", "topicassetmodify", "topicassetqry",
    "assetadd", "assetdel", "assetmodify", "assetqry",
    "renderjobadd", "renderjobdel", "renderjobmodify", "renderjobqry",
    "topicversionadd", "topicversiondel", "topicversionmodify", "topicversionqry",
    #只读域
    "layoutqry", "platformqry", "artifactqry", "accountqry", "publishrecordqry",
    #★ 2026-09-23 手改(第三方账号管理): operator 开放「自管本人平台账号」写权限;
    #  归属隔离由处理器强制(ownerID 由服务端按 loginID 派生, 见 crudApi/accountApi),
    #  故授权面放宽不构成越权。accounthealth 已含于 _BIZ_CMDS, 无需重复声明。
    "accountadd", "accountmodify", "accountdel",
    ],
"customer":      [
    "registration", "logout", "getuserinfo", "usersavedata", "usergetdata",
    "topicqry", "assetqry", "topicassetqry", "renderjobqry", "artifactqry",
    "layoutqry", "platformqry", "topicversionqry",
    #★ 2026-09-23 手改(第三方账号管理): customer 开放本人账号的读/写/巡检(四端点 + accounthealth);
    #  ★ 不给 visitor(无菜单/无路由/请求级亦不在本清单)。
    "accountqry", "accountadd", "accountmodify", "accountdel", "accounthealth",
    ],
"visitor":       [
    "registration", "logout", "getuserinfo",
    #公开只读(与 NO_SESSIONID_CMD_LIST 对齐)
    "platformqry", "layoutqry", "artifactqry",
    ],
}

#管理员专属 CMD 按 USER_ADMIN_ROLE_LIST 授权(与 accountApi._chkUserAdminRole 同源, 避免两处漂移)
for _roleName in USER_ADMIN_ROLE_LIST:
    if _roleName in ROLE_CMD_LIST:
        ROLE_CMD_LIST[_roleName] = list(ROLE_CMD_LIST[_roleName]) + _USER_ADMIN_CMDS

FUNCTION_CMD_CNNAME_DATA = {
    "chkuserexist":"用户是否存在",
    "generalnext":"获取下一批数据",
    "getuserinfo":"用户信息获取",
    "login":"用户登录",
    "logout":"用户注销/登出",
    "registration":"用户注册",
    "resetpasswd":"用户重置密码",
    "smsrequest":"短信验证请求",
    "smsverify":"短信验证反馈",
    "useradd":"用户增加",
    "userdel":"用户删除",
    "usergetdata":"获取用户存储数据",
    "userinfoqry":"用户信息查询",
    "usermodify":"用户修改",
    "usersavedata":"用户存储数据",
    "usersearch":"用户查询",
    "topicqry":"主题查询",
    "assetqry":"素材查询",
    "artifactqry":"产物查询",
    "layoutqry":"版式查询",
    "platformqry":"平台查询",
}

menuParameters = {
}


#MCP工具清单(角色 -> 允许调用的工具名清单), 空dict=不限制(见 mcpapi/mcpPost.py::_genAllowedTools)
MCP_TOOL_LIST = {
}


TRUST_DOMAIN_LIST = [
    "localhost",
    "127.0.0.1",
]

_LOG = None #预设日志对象，禁止修改
_DEBUG = True  #预设trace开关，禁止修改

#contentHub API 服务默认会话(sessionID), 便于本地/服务间联调
CH_API_SESSIONID ={
    "local":"your_token",
    "server_01":"your_token",
    "server_02":"your_token",
    "test_server":"your_token",
    "home":"your_token",
}[_SYS]


if __name__ == "__main__":
    pass
    # import pdb
    # pdb.set_trace()
    print ("_SYS",_SYS)
    print ("_SYS_SERVER_NAME",_SYS_SERVER_NAME)

    print ("FILE_SYSTEM_MODE", FILE_SYSTEM_MODE)
    print ("THUMBNAIL_SIZE", THUMBNAIL_SIZE)
    print ("ROLE_CMD_LIST", ROLE_CMD_LIST)
    print ("SYS_DEFAULT_AUTO_LOGINID", SYS_DEFAULT_AUTO_LOGINID)

    print ("LOCAL_FILE_SERVER_BASE", LOCAL_FILE_SERVER_BASE)
    print ("LOCAL_FILE_SERVER_PATH", LOCAL_FILE_SERVER_PATH)
