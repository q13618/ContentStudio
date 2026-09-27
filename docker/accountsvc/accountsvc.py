#! /usr/bin/env python3
# encoding: utf-8
#
# Filename: accountsvc.py
# Description: contentHub 的最小账号服务(替代外部 ylwz account service "/acis")。
#
# 背景: contentHub 的登录/会话/权限全部通过 HTTP 转发给外部账号服务
#       (config/basicSettings.py::ACCOUNT_SERVICE_URL, 报文 {"CMD": "A0A0", ...}),
#       但该服务不在仓库内。本文件按 common/accountClient.py 与
#       main/subfunc/accountSvcClient.py 的调用契约实现一个自托管替身, 数据落 Redis。
#
# 已实现 CMD:
#   A0A0 登录 / 注册(建号)   A2A0 生成会话     A3A0 用户信息     A5A0 登出
#   A9A0 重置口令            AEA0 修改角色     AIA0 用户存在性   GAA0 会话 + 功能清单
#   G1A0 / G2A0 用户自定义数据
#   A6A0 / A7A0 短信(不支持, 返回 BS)
#
# 安全:
#   - 口令: 前端送来的是 md5(passwd + loginID) 摘要, 本服务再做 PBKDF2-SHA256(随机盐) 后存储;
#   - 自助注册默认关闭(ACIS_ALLOW_REGISTRATION=1 才开放);
#     管理员经 contentHub 的 useradd 建号时, 请求体携带管理员 sessionID, 本服务据此放行;
#   - 首次启动按 ACIS_ADMIN_LOGINID / ACIS_ADMIN_PASSWD 自动建一个 administrator。
#   - 本服务只应在容器内网访问, 不要对公网暴露端口。

import hashlib
import json
import os
import secrets
import time

import redis
from flask import Flask, Response, request

application = Flask(__name__)

REDIS_HOST = os.getenv("ACIS_REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("ACIS_REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("ACIS_REDIS_DB", "2"))
SESSION_TTL = int(os.getenv("ACIS_SESSION_TTL", str(7 * 24 * 3600)))
ALLOW_REGISTRATION = os.getenv("ACIS_ALLOW_REGISTRATION", "0") == "1"
DEFAULT_ROLE = os.getenv("ACIS_DEFAULT_ROLE", "operator")

VALID_ROLES = ["administrator", "manager", "operator", "customer", "visitor"]
ADMIN_ROLES = ["administrator", "manager"]

_db = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

_K_USER = "acis:user:"
_K_SESSION = "acis:session:"
_K_UDATA = "acis:udata:"
_PBKDF2_ROUNDS = 200_000


# ------------------------------------------------------------------ helpers
def _now():
    return time.strftime("%Y%m%d%H%M%S")


def _hashPasswd(digest, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", digest.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ROUNDS).hex()
    return f"pbkdf2${salt}${h}"


def _chkPasswd(digest, stored):
    try:
        _, salt, _h = stored.split("$", 2)
    except ValueError:
        return False
    return secrets.compare_digest(_hashPasswd(digest, salt), stored)


def _getUser(loginID):
    if not loginID:
        return {}
    return _db.hgetall(_K_USER + str(loginID)) or {}


def _publicUser(u):
    return {
        "loginID": u.get("loginID", ""),
        "nickName": u.get("nickName", "") or u.get("loginID", ""),
        "realName": u.get("realName", ""),
        "email": u.get("email", ""),
        "mobile": u.get("mobile", ""),
        "sex": u.get("sex", ""),
        "roleName": u.get("roleName", DEFAULT_ROLE),
    }


def _createUser(loginID, digest, roleName, extra=None):
    extra = extra or {}
    data = {
        "loginID": loginID,
        "passwd": _hashPasswd(digest),
        "roleName": roleName if roleName in VALID_ROLES else DEFAULT_ROLE,
        "nickName": extra.get("nickName", "") or loginID,
        "realName": extra.get("realName", ""),
        "email": extra.get("email", ""),
        "mobile": extra.get("mobile", ""),
        "regYMDHMS": _now(),
    }
    _db.hset(_K_USER + loginID, mapping=data)
    return data


def _newSession(user):
    sid = secrets.token_hex(24)
    payload = {"loginID": user["loginID"], "roleName": user.get("roleName", DEFAULT_ROLE),
               "openID": "", "activeFlag": "Y", "YMDHMS": _now()}
    _db.set(_K_SESSION + sid, json.dumps(payload), ex=SESSION_TTL)
    return sid


def _getSession(sid):
    if not sid:
        return {}
    raw = _db.get(_K_SESSION + str(sid))
    if not raw:
        return {}
    _db.expire(_K_SESSION + str(sid), SESSION_TTL)   # 滑动续期
    s = json.loads(raw)
    u = _getUser(s.get("loginID"))
    if not u:
        return {}
    s["roleName"] = u.get("roleName", s.get("roleName"))
    return s


def _ok(**kw):
    r = {"errCode": "B0", "MSG": {"errCode": "B0"}}
    r.update(kw)
    return r


def _err(code, **kw):
    r = {"errCode": code, "MSG": {"errCode": code}}
    r.update(kw)
    return r


# ------------------------------------------------------------------ commands
def cmdLogin(d):
    """A0A0: 已存在 -> 校验口令并建会话; 不存在 -> 注册(需开放注册或管理员会话)。"""
    loginID = str(d.get("loginID", "")).strip()
    digest = str(d.get("passwd", ""))
    if len(loginID) < 2:
        return _err("B2")
    if not digest:
        return _err("B3")
    user = _getUser(loginID)
    if user:
        if not _chkPasswd(digest, user.get("passwd", "")):
            return _err("B5")
        sid = _newSession(user)
        return _ok(sessionID=sid, **_publicUser(user))
    # 新建账号
    operator = _getSession(d.get("sessionID"))
    isAdminCreate = operator.get("roleName") in ADMIN_ROLES
    if not (isAdminCreate or ALLOW_REGISTRATION):
        return _err("BS")
    role = d.get("roleName") if isAdminCreate else DEFAULT_ROLE
    user = _createUser(loginID, digest, role, d)
    if isAdminCreate:
        return _ok(**_publicUser(user))
    sid = _newSession(user)
    return _ok(sessionID=sid, **_publicUser(user))


def cmdGenSession(d):
    s = _getSession(d.get("sessionID"))
    if not s:
        return _err("B8")
    return _ok(sessionID=_newSession(_getUser(s["loginID"])))


def cmdUserInfo(d):
    loginID = d.get("loginID") or _getSession(d.get("sessionID")).get("loginID")
    u = _getUser(loginID)
    if not u:
        return _err("B1")
    return _ok(**_publicUser(u))


def cmdLogout(d):
    sid = d.get("sessionID")
    if sid:
        _db.delete(_K_SESSION + str(sid))
    return _ok()


def cmdResetPasswd(d):
    """A9A0: 本人(旧口令正确)或管理员可改口令; 新口令字段 newPasswd(同为 md5 摘要)。"""
    s = _getSession(d.get("sessionID"))
    loginID = d.get("loginID") or s.get("loginID")
    u = _getUser(loginID)
    newDigest = d.get("newPasswd", "")
    if not u:
        return _err("B1")
    if not newDigest:
        return _err("B6")
    isAdmin = s.get("roleName") in ADMIN_ROLES
    if not isAdmin and not _chkPasswd(str(d.get("passwd", "")), u.get("passwd", "")):
        return _err("BM")
    _db.hset(_K_USER + loginID, "passwd", _hashPasswd(newDigest))
    return _ok()


def cmdModifyRole(d):
    s = _getSession(d.get("sessionID"))
    if s.get("roleName") not in ADMIN_ROLES:
        return _err("BG")
    loginID, role = d.get("loginID"), d.get("roleName")
    if not _getUser(loginID):
        return _err("B1")
    if role not in VALID_ROLES:
        return _err("BA")
    _db.hset(_K_USER + loginID, "roleName", role)
    return _ok()


def cmdUserExist(d):
    loginID = d.get("userID") or d.get("loginID")
    return _ok(userExistFlag="Y" if _getUser(loginID) else "N")


def cmdSessionCmdList(d):
    s = _getSession(d.get("sessionID"))
    if not s:
        return {"errCode": "B0", "data": {"errCode": "B8", "sessionIDSet": {}}}
    return {"errCode": "B0", "data": {"errCode": "B0", "sessionIDSet": s}}


def cmdSaveUserData(d):
    s = _getSession(d.get("sessionID"))
    if not s:
        return _err("B8")
    key, val = d.get("key", "default"), d.get("val", d.get("data", ""))
    _db.hset(_K_UDATA + s["loginID"], key, json.dumps(val, ensure_ascii=False))
    return _ok()


def cmdGetUserData(d):
    s = _getSession(d.get("sessionID"))
    if not s:
        return _err("B8")
    key = d.get("key", "default")
    raw = _db.hget(_K_UDATA + s["loginID"], key)
    return _ok(key=key, val=json.loads(raw) if raw else "")


def cmdNotSupported(d):
    return _err("BS")


CMD_MAP = {
    "A0A0": cmdLogin, "A2A0": cmdGenSession, "A3A0": cmdUserInfo, "A5A0": cmdLogout,
    "A6A0": cmdNotSupported, "A7A0": cmdNotSupported, "A9A0": cmdResetPasswd,
    "AEA0": cmdModifyRole, "AIA0": cmdUserExist, "GAA0": cmdSessionCmdList,
    "G1A0": cmdSaveUserData, "G2A0": cmdGetUserData,
}


@application.route("/acis", methods=["POST"])
def acis():
    try:
        d = json.loads(request.get_data(as_text=True) or "{}")
    except Exception:
        d = {}
    fn = CMD_MAP.get(d.get("CMD", ""), cmdNotSupported)
    try:
        rtn = fn(d)
    except Exception as e:  # 不外抛, 与原账号服务行为一致
        application.logger.exception("acis error")
        rtn = _err("B8", detail=str(e))
    return Response(json.dumps(rtn, ensure_ascii=False), content_type="application/json; charset=utf-8")


@application.route("/healthz")
def healthz():
    _db.ping()
    return "ok"


def bootstrapAdmin():
    loginID = os.getenv("ACIS_ADMIN_LOGINID", "").strip()
    plain = os.getenv("ACIS_ADMIN_PASSWD", "")
    if not loginID or not plain:
        return
    if _getUser(loginID):
        return
    # 与前端一致: digest = md5(passwd + loginID)
    digest = hashlib.md5(f"{plain}{loginID}".encode("utf-8")).hexdigest()
    _createUser(loginID, digest, "administrator", {"nickName": "管理员"})
    print(f"[accountsvc] bootstrap administrator created: {loginID}", flush=True)


for _i in range(30):
    try:
        _db.ping()
        bootstrapAdmin()
        break
    except redis.exceptions.ConnectionError:
        time.sleep(1)

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8160)
