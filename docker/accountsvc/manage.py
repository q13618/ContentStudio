#! /usr/bin/env python3
# encoding: utf-8
# 账号命令行工具(界面暂无用户管理页时使用)
#   docker compose exec accountsvc python manage.py add  <loginID> <口令> [角色]
#   docker compose exec accountsvc python manage.py passwd <loginID> <新口令>
#   docker compose exec accountsvc python manage.py role <loginID> <角色>
#   docker compose exec accountsvc python manage.py list
#   docker compose exec accountsvc python manage.py invite <邮箱> [角色]     # 邮箱验证码登录的无口令账号
#   docker compose exec accountsvc python manage.py email <loginID> <邮箱>  # 给已有账号绑定登录邮箱
# 角色: administrator / manager / operator / customer / visitor
import hashlib
import secrets
import sys

import accountsvc as svc


def digest(loginID, plain):
    return hashlib.md5(f"{plain}{loginID}".encode("utf-8")).hexdigest()


def main(argv):
    if len(argv) < 2:
        print(__doc__ or open(__file__).read().split("import")[0]); return 1
    cmd = argv[1]
    if cmd == "list":
        for key in sorted(svc._db.scan_iter(svc._K_USER + "*")):
            u = svc._db.hgetall(key)
            print(f"{u.get('loginID'):<28} {u.get('roleName'):<14} {u.get('email',''):<28} {u.get('regYMDHMS','')}")
        return 0
    if cmd == "invite":
        email = svc._normEmail(argv[2])
        role = argv[3] if len(argv) > 3 else "operator"
        if not svc._validEmail(email):
            print("邮箱格式无效"); return 1
        if role not in svc.VALID_ROLES:
            print(f"角色须为 {svc.VALID_ROLES}"); return 1
        if svc._loginIDByEmail(email):
            print("该邮箱已登记"); return 1
        svc._createUser(email, secrets.token_hex(32), role, {"email": email, "nickName": email.split("@")[0]})
        print(f"已邀请 {email} ({role}), 用邮箱验证码登录"); return 0
    loginID = argv[2]
    if cmd == "add":
        role = argv[4] if len(argv) > 4 else "operator"
        if svc._getUser(loginID):
            print("用户已存在"); return 1
        svc._createUser(loginID, digest(loginID, argv[3]), role)
        print(f"已创建 {loginID} ({role})"); return 0
    if not svc._getUser(loginID):
        print("用户不存在"); return 1
    if cmd == "passwd":
        svc._db.hset(svc._K_USER + loginID, "passwd", svc._hashPasswd(digest(loginID, argv[3])))
        print("口令已更新"); return 0
    if cmd == "email":
        email = svc._normEmail(argv[3])
        if not svc._validEmail(email):
            print("邮箱格式无效"); return 1
        owner = svc._loginIDByEmail(email)
        if owner and owner != loginID:
            print(f"该邮箱已被 {owner} 使用"); return 1
        old = svc._normEmail(svc._getUser(loginID).get("email"))
        if old and old != email:
            svc._db.delete(svc._K_EMAIL + old)
        svc._db.hset(svc._K_USER + loginID, "email", email)
        svc._db.set(svc._K_EMAIL + email, loginID)
        print(f"已绑定 {loginID} -> {email}"); return 0
    if cmd == "role":
        if argv[3] not in svc.VALID_ROLES:
            print(f"角色须为 {svc.VALID_ROLES}"); return 1
        svc._db.hset(svc._K_USER + loginID, "roleName", argv[3])
        print("角色已更新"); return 0
    print("未知命令"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
