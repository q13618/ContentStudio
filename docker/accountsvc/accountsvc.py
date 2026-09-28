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
#   A6A0 / A7A0 邮箱验证码登录(经 Resend 发信; 复用原「短信验证」通道 smsrequest/smsverify,
#               contentHub 后端零改动即可转发)
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
import requests
from flask import Flask, Response, request

application = Flask(__name__)

REDIS_HOST = os.getenv("ACIS_REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("ACIS_REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("ACIS_REDIS_DB", "2"))
SESSION_TTL = int(os.getenv("ACIS_SESSION_TTL", str(7 * 24 * 3600)))
ALLOW_REGISTRATION = os.getenv("ACIS_ALLOW_REGISTRATION", "0") == "1"
DEFAULT_ROLE = os.getenv("ACIS_DEFAULT_ROLE", "operator")

# ---- 邮箱验证码登录(Resend) ----
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM", "").strip() or "contentHub <onboarding@resend.dev>"
RESEND_API_URL = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")
EMAIL_CODE_TTL = int(os.getenv("ACIS_EMAIL_CODE_TTL", "600"))          # 验证码有效期(秒)
EMAIL_CODE_COOLDOWN = int(os.getenv("ACIS_EMAIL_CODE_COOLDOWN", "60"))  # 同一邮箱两次发送最小间隔
EMAIL_CODE_HOURLY_MAX = int(os.getenv("ACIS_EMAIL_CODE_HOURLY_MAX", "10"))   # 同一邮箱每小时上限
EMAIL_CODE_IP_HOURLY_MAX = int(os.getenv("ACIS_EMAIL_CODE_IP_HOURLY_MAX", "30"))  # 同一 IP 每小时上限
EMAIL_CODE_MAX_TRY = int(os.getenv("ACIS_EMAIL_CODE_MAX_TRY", "5"))    # 单个验证码最多校验次数
# 这些域名的邮箱首次验证即自动建号(逗号分隔, 如 "example.com,example.cn"); 为空则只有已登记邮箱可登录
EMAIL_ALLOWED_DOMAINS = {x.strip().lower().lstrip("@") for x in
                         os.getenv("ACIS_EMAIL_ALLOWED_DOMAINS", "").split(",") if x.strip()}
APP_NAME = os.getenv("ACIS_APP_NAME", "内容中枢")

VALID_ROLES = ["administrator", "manager", "operator", "customer", "visitor"]
ADMIN_ROLES = ["administrator", "manager"]

_db = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

_K_USER = "acis:user:"
_K_SESSION = "acis:session:"
_K_UDATA = "acis:udata:"
_K_EMAIL = "acis:email:"          # email -> loginID 索引
_K_ECODE = "acis:ecode:"          # 验证码(哈希) + 已校验次数
_K_ECOOL = "acis:ecode:cool:"     # 发送冷却
_K_ECNT = "acis:ecode:cnt:"       # 每小时发送计数(邮箱 / IP)
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
    if data["email"]:
        _db.set(_K_EMAIL + _normEmail(data["email"]), loginID)
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


# ------------------------------------------------------------------ 邮箱验证码登录
def _normEmail(email):
    return str(email or "").strip().lower()


def _validEmail(email):
    if not email or len(email) > 254 or email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".") \
        and not any(c.isspace() for c in email)


def _loginIDByEmail(email):
    """邮箱 -> loginID: 先查索引, 再兼容 loginID 本身就是邮箱的账号。"""
    loginID = _db.get(_K_EMAIL + email)
    if loginID and _getUser(loginID):
        return loginID
    if _getUser(email):
        return email
    return ""


def _canAutoRegister(email):
    return ALLOW_REGISTRATION or email.split("@")[1] in EMAIL_ALLOWED_DOMAINS


def _codeHash(email, code):
    return hashlib.sha256(f"{email}:{code}".encode("utf-8")).hexdigest()


def _hitLimit(key, limit, window=3600):
    n = _db.incr(key)
    if n == 1:
        _db.expire(key, window)
    return n > limit


def _sendEmailCode(email, code):
    minutes = max(1, EMAIL_CODE_TTL // 60)
    subject = f"{APP_NAME} 登录验证码: {code}"
    text = f"你的 {APP_NAME} 登录验证码是 {code}, {minutes} 分钟内有效。如非本人操作请忽略本邮件。"
    html = (f'<div style="font-family:sans-serif;font-size:14px;color:#222">'
            f'<p>你的 <b>{APP_NAME}</b> 登录验证码:</p>'
            f'<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{code}</p>'
            f'<p style="color:#888">{minutes} 分钟内有效。如非本人操作请忽略本邮件。</p></div>')
    if not RESEND_API_KEY:
        # 未配置 Resend: 开发模式, 验证码只打到容器日志(docker compose logs accountsvc)
        print(f"[accountsvc] RESEND_API_KEY 未配置, 开发模式验证码 {email}: {code}", flush=True)
        return True
    r = requests.post(RESEND_API_URL, timeout=15,
                      headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                      json={"from": RESEND_FROM, "to": [email], "subject": subject, "text": text, "html": html})
    if r.status_code >= 300:
        application.logger.error("resend send failed: %s %s", r.status_code, r.text[:300])
        return False
    return True


def cmdEmailCodeRequest(d):
    """A6A0: 向邮箱发送 6 位登录验证码。入参 email(兼容 loginID 字段)。
       错误码: BA 邮箱格式错 / BE 邮箱未登记且不允许自动建号 / BN 发送过频或发送失败(reason 字段说明)。"""
    email = _normEmail(d.get("email") or d.get("loginID"))
    if not _validEmail(email):
        return _err("BA")
    if not _loginIDByEmail(email) and not _canAutoRegister(email):
        return _err("BE")
    if _db.exists(_K_ECOOL + email):
        return _err("BN", reason="cooldown", retryAfter=_db.ttl(_K_ECOOL + email))
    ip = str(d.get("_IP", "")).strip()
    if _hitLimit(_K_ECNT + "mail:" + email, EMAIL_CODE_HOURLY_MAX) or \
            (ip and _hitLimit(_K_ECNT + "ip:" + ip, EMAIL_CODE_IP_HOURLY_MAX)):
        return _err("BN", reason="rate_limited")
    code = f"{secrets.randbelow(10**6):06d}"
    _db.set(_K_ECOOL + email, "1", ex=EMAIL_CODE_COOLDOWN)
    if not _sendEmailCode(email, code):
        _db.delete(_K_ECOOL + email)
        return _err("BN", reason="send_failed")
    _db.set(_K_ECODE + email, json.dumps({"h": _codeHash(email, code), "n": 0}), ex=EMAIL_CODE_TTL)
    return _ok(email=email, ttl=EMAIL_CODE_TTL, cooldown=EMAIL_CODE_COOLDOWN)


def cmdEmailCodeVerify(d):
    """A7A0: 校验邮箱验证码 -> 登录(必要时自动建号) -> 返回 sessionID + 用户信息(与 A0A0 登录同形)。
       错误码: BA 邮箱格式错 / BM 验证码错误或已过期 / BE 邮箱未登记且不允许自动建号。"""
    email = _normEmail(d.get("email") or d.get("loginID"))
    code = str(d.get("code") or d.get("verifyCode") or "").strip()
    if not _validEmail(email):
        return _err("BA")
    raw = _db.get(_K_ECODE + email)
    if not raw or not code:
        return _err("BM")
    rec = json.loads(raw)
    if not secrets.compare_digest(rec.get("h", ""), _codeHash(email, code)):
        rec["n"] = int(rec.get("n", 0)) + 1
        if rec["n"] >= EMAIL_CODE_MAX_TRY:
            _db.delete(_K_ECODE + email)
        else:
            _db.set(_K_ECODE + email, json.dumps(rec), keepttl=True)
        return _err("BM")
    _db.delete(_K_ECODE + email)
    loginID = _loginIDByEmail(email)
    if loginID:
        user = _getUser(loginID)
    elif _canAutoRegister(email):
        # 无口令账号: 存一个随机摘要占位, 口令登录永远无法命中; 只能走邮箱验证码
        user = _createUser(email, secrets.token_hex(32), DEFAULT_ROLE,
                           {"email": email, "nickName": email.split("@")[0]})
    else:
        return _err("BE")
    sid = _newSession(user)
    return _ok(sessionID=sid, **_publicUser(user))


def cmdNotSupported(d):
    return _err("BS")


CMD_MAP = {
    "A0A0": cmdLogin, "A2A0": cmdGenSession, "A3A0": cmdUserInfo, "A5A0": cmdLogout,
    "A6A0": cmdEmailCodeRequest, "A7A0": cmdEmailCodeVerify, "A9A0": cmdResetPasswd,
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
    """首次启动建管理员:
       - ACIS_ADMIN_LOGINID + ACIS_ADMIN_PASSWD: 口令登录的管理员(可同时登记 ACIS_ADMIN_EMAIL);
       - 仅 ACIS_ADMIN_EMAIL: 以邮箱为 loginID 的无口令管理员, 只能邮箱验证码登录。"""
    loginID = os.getenv("ACIS_ADMIN_LOGINID", "").strip()
    plain = os.getenv("ACIS_ADMIN_PASSWD", "")
    email = _normEmail(os.getenv("ACIS_ADMIN_EMAIL", ""))
    if email and not _validEmail(email):
        print(f"[accountsvc] ACIS_ADMIN_EMAIL 格式无效, 已忽略: {email}", flush=True)
        email = ""
    if loginID and plain:
        user = _getUser(loginID)
        if not user:
            # 与前端一致: digest = md5(passwd + loginID)
            digest = hashlib.md5(f"{plain}{loginID}".encode("utf-8")).hexdigest()
            _createUser(loginID, digest, "administrator", {"nickName": "管理员", "email": email})
            print(f"[accountsvc] bootstrap administrator created: {loginID}", flush=True)
        elif email and not _loginIDByEmail(email):
            _db.hset(_K_USER + loginID, "email", email)
            _db.set(_K_EMAIL + email, loginID)
        return
    if email and not _loginIDByEmail(email):
        _createUser(email, secrets.token_hex(32), "administrator", {"nickName": "管理员", "email": email})
        print(f"[accountsvc] bootstrap administrator created (email login): {email}", flush=True)


for _i in range(30):
    try:
        _db.ping()
        bootstrapAdmin()
        break
    except redis.exceptions.ConnectionError:
        time.sleep(1)

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8160)
