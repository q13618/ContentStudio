# contentHub · Docker Compose 部署

一条命令起全套：MySQL + Redis + 后端 API + 文件服务 + 渲染 worker + 落库消费者 + MCP + 账号服务 + nginx/前端。

## 快速开始

```bash
git clone <本仓库> contentHub && cd contentHub
cp .env.example .env          # 修改 .env 里所有口令, CH_CREDENTIAL_KEY 用 openssl rand -hex 32 生成
docker compose up -d --build  # 首次构建约 5–10 分钟(含 Chromium)
```

浏览器打开 `http://服务器IP:8080/`，用 `.env` 里的 `CH_ADMIN_LOGINID` / `CH_ADMIN_PASSWD` 登录。

## 容器一览

| 服务 | 作用 | 说明 |
|---|---|---|
| `web` | nginx 网关 + Vue 前端 | 唯一对外端口 `CH_HTTP_PORT`(默认 8080) |
| `api` | Flask `/chapi` 业务接口 | gunicorn 3 worker |
| `filesvc` | 文件服务 `/upload` `/hfile` | 原 `ylwzRecvFiles.py` + `uploadShim.py` |
| `render` | 渲染 worker(Playwright 截图) | 处理 `renderMode=job` 异步任务 |
| `trans` | Redis 队列 → MySQL 落库消费者 | 原 `transferCHMysql.py` |
| `mcp` | MCP Server(streamable-http) | 经 nginx `/mcp` 暴露, 需 MCP token |
| `accountsvc` | **新增** 本地账号服务 | 替代仓库缺失的外部 `/acis` 服务 |
| `ops` | 每日巡检 + 归档(dry-run) | 替代 crontab |
| `init` | 建表 + 种子数据 | 每次 `up` 跑一次, 幂等, 跑完退出 |
| `mysql` / `redis` | 数据库 | 不对外暴露端口 |

数据卷：`mysqldata` `redisdata` `webdata`(临时文件/预览) `filestorage`(素材与产物) `chdata` `logs`。

## 相对原仓库的改动

1. **账号服务**：新增 `docker/accountsvc/accountsvc.py`，按 `common/accountClient.py` 的 CMD 协议实现登录/会话/角色/用户数据；口令 PBKDF2 加盐存储；自助注册默认关闭；前端目前没有用户管理页，建号/改口令用命令行(见下方「日常运维」)。
2. **上传通道**：用 `docker/filesvc/uploadShim.py` 等价实现 nginx-upload-module 的 `/upload`，不必再自己编译 nginx。
3. **配置**：`config/*.py` 的 `home` 环境改为「环境变量优先、原值兜底」；`local_settings._SYS` 可由 `CH_SYS` 覆盖。不设环境变量时行为与原来完全一致。

## 上线到服务器(推荐香港轻量云, Ubuntu 22.04/24.04, 2C4G)

```bash
curl -fsSL https://get.docker.com | sh
# 上传/克隆代码, 编辑 .env:
#   CH_PUBLIC_BASE_URL=https://你的域名/
#   CH_HTTP_PORT=80   (或保留 8080, 前面再挂 Caddy/宝塔 做 HTTPS)
docker compose up -d --build
```

- **HTTPS**：最省事是在宿主机装 Caddy，`你的域名 { reverse_proxy 127.0.0.1:8080 }`，自动签证书。
- **公众号**：到公众号后台「设置与开发 → 基本配置 → IP 白名单」加上服务器公网 IP；AppID/AppSecret 在界面「第三方账号管理」里录入(加密落库)。
- **防火墙**：只开放 80/443(和 SSH)，MySQL/Redis 不映射端口。

## 日常运维

```bash
docker compose ps                     # 状态
docker compose logs -f api render     # 日志
git pull && docker compose up -d --build   # 更新代码后重建
# 用户管理(前端暂无该页面)
docker compose exec accountsvc python manage.py add sam 初始口令 operator
docker compose exec accountsvc python manage.py passwd sam 新口令
docker compose exec accountsvc python manage.py list
# 备份
docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" contenthub_data' > backup_$(date +%F).sql
docker run --rm -v contenthub_filestorage:/d -v $PWD:/b ubuntu tar czf /b/filestorage_$(date +%F).tgz -C /d .
```

## 特殊网络环境(可选)

- 机器在企业代理后：把代理根证书 `*.crt` 放进 `docker/certs/`，构建时会自动信任。
- 无法下载 Chromium：把 Playwright 浏览器缓存(`chromium-XXXX` 等目录)放进 `docker/backend/pw-cache/`，并在 `.env` 设置配套的 `PLAYWRIGHT_VERSION`。
