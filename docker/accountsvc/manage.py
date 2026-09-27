#! /usr/bin/env python3
# encoding: utf-8
# 账号命令行工具(界面暂无用户管理页时使用)
#   docker compose exec accountsvc python manage.py add  <loginID> <口令> [角色]
#   docker compose exec accountsvc python manage.py passwd <loginID> <新口令>
#   docker compose exec accountsvc python manage.py role <loginID> <角色>
#   docker compose exec accountsvc python manage.py list
# 角色: administrator / manager / operator / customer / visitor
import hashlib
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
            print(f"{u.get('loginID'):<20} {u.get('roleName'):<14} {u.get('regYMDHMS','')}")
        return 0
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
    if cmd == "role":
        if argv[3] not in svc.VALID_ROLES:
            print(f"角色须为 {svc.VALID_ROLES}"); return 1
        svc._db.hset(svc._K_USER + loginID, "roleName", argv[3])
        print("角色已更新"); return 0
    print("未知命令"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
