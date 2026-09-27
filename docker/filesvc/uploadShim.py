#! /usr/bin/env python3
# encoding: utf-8
#
# Filename: uploadShim.py
# Description: 用纯 Python 替代 nginx-upload-module 的 "/upload" 路由。
#
# 原部署: nginx(编译 upload 模块) 接收 multipart -> 落盘到 /data/webserver/temp/<0-9>/ ->
#         注入 <field>.name / .content_type / .path / .md5 / .size 表单字段 -> 转交 /hfile。
# 这里在同一个 Flask 应用(main/ylwzRecvFiles.py)上补一个 /upload 路由, 行为等价,
# 从而可以直接用官方 nginx 镜像, 不必自己编译 nginx。
#
# 启动: gunicorn -w 2 -b 0.0.0.0:8005 uploadShim:application   (工作目录 code/src/main)

import hashlib
import os
import secrets

from flask import request

import ylwzRecvFiles as recv  # noqa: E402  (复用原文件服务的 application 与 fileHandler)

application = recv.application

UPLOAD_STORE = os.getenv("CH_UPLOAD_STORE", "/data/webserver/temp")
PASS_FIELDS = {"submit", "description", "index"}   # 对齐 upload_pass_form_field


@application.route("/upload", methods=["POST"])
def uploadShim():
    dataSet = {}
    for key, fs in request.files.items(multi=True):
        if not fs or not fs.filename:
            continue
        sub = str(secrets.randbelow(10))
        folder = os.path.join(UPLOAD_STORE, sub)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{secrets.randbelow(10**10):010d}")
        md5 = hashlib.md5()
        size = 0
        with open(path, "wb") as out:
            while True:
                chunk = fs.stream.read(1024 * 1024)
                if not chunk:
                    break
                md5.update(chunk)
                size += len(chunk)
                out.write(chunk)
        os.chmod(path, 0o666)
        dataSet[f"{key}.name"] = [fs.filename]
        dataSet[f"{key}.content_type"] = [fs.mimetype or "application/octet-stream"]
        dataSet[f"{key}.path"] = [path]
        dataSet[f"{key}.md5"] = [md5.hexdigest()]
        dataSet[f"{key}.size"] = [str(size)]
    for key, vals in request.form.to_dict(flat=False).items():
        if key in PASS_FIELDS:
            dataSet[key] = vals
    rtnSet = recv.fileHandler(dataSet)
    return recv.misc.jsonDumps(rtnSet)
