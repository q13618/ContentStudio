# contentHub · Docker Compose 部署

一条命令起全套：MySQL + Redis + 后端 API + 文件服务 + 渲染 worker + 落库消费者 + MCP + 账号服务 + nginx/前端。

## 快速开始

```bash
git clone <本仓库> contentHub && cd contentHub
cp .env.example .env          # 修改 .env 里所有口令, CH_CREDENTIAL_KEY 用 openssl rand -hex 32 生成
docker compose up -d --build  # 首次构建约 5–10 分钟(含 Chromium)
```

浏览器打开 `http://服务器IP:8080/`，用 `.env` 里的 `CH_ADMIN_LOGINID` / `CH_ADMIN_PASSWD` 登录；
或切到「邮箱验证码」页签，用 `CH_ADMIN_EMAIL` 收码登录（见下方「邮箱验证码登录」）。

## 容器一览

| 服务 | 作用 | 说明 |
|---|---|---|
| `web` | nginx 网关 + Vue 前端 | 唯一对外端口 `CH_HTTP_PORT`(默认 8080) |
| `api` | Flask `/chapi` 业务接口 | gunicorn 3 worker |
| `filesvc` | 文件服务 `/upload` `/hfile` | 原 `ylwzRecvFiles.py` + `uploadShim.py` |
| `render` | 渲染 worker(Playwright 截图) | 处理 `renderMode=job` 异步任务 |
| `trans` | Redis 队列 → MySQL 落库消费者 | 原 `transferCHMysql.py` |
| `mcp` | MCP Server(streamable-http) | 经 nginx `/mcp` 暴露, 需 MCP token |
| `accountsvc` | **新增** 本地账号服务 | 替代仓库缺失的外部 `/acis` 服务；口令登录 + Resend 邮箱验证码登录 |
| `ops` | 每日巡检 + 归档(dry-run) | 替代 crontab |
| `init` | 建表 + 种子数据 | 每次 `up` 跑一次, 幂等, 跑完退出 |
| `mysql` / `redis` | 数据库 | 不对外暴露端口 |

数据卷：`mysqldata` `redisdata` `webdata`(临时文件/预览) `filestorage`(素材与产物) `chdata` `logs`。

## 相对原仓库的改动

1. **账号服务**：新增 `docker/accountsvc/accountsvc.py`，按 `common/accountClient.py` 的 CMD 协议实现登录/会话/角色/用户数据；口令 PBKDF2 加盐存储；自助注册默认关闭；前端目前没有用户管理页，建号/改口令用命令行(见下方「日常运维」)。
2. **上传通道**：用 `docker/filesvc/uploadShim.py` 等价实现 nginx-upload-module 的 `/upload`，不必再自己编译 nginx。
3. **配置**：`config/*.py` 的 `home` 环境改为「环境变量优先、原值兜底」；`local_settings._SYS` 可由 `CH_SYS` 覆盖。不设环境变量时行为与原来完全一致。

## 邮箱验证码登录（Resend）

登录页默认是「邮箱验证码」：输入邮箱 → 收到 6 位验证码 → 登录。用户不必记口令，管理员也不用帮人重置口令。
实现全部在 `accountsvc` 里（A6A0 发码 / A7A0 校验，复用后端原有的 `smsrequest` / `smsverify` 通道），
业务后端只多了一处「验证码登录成功后同步 USER_BASIC」。

**配置（`.env`）**

| 变量 | 说明 |
|---|---|
| `RESEND_API_KEY` | Resend 控制台 → API Keys 创建。**留空 = 开发模式**：不发信，验证码打印在 `docker compose logs accountsvc` |
| `RESEND_FROM` | 发件人，如 `内容中枢 <login@your-domain.com>`；域名须先在 Resend → Domains 验证（加 SPF/DKIM DNS 记录）。未验证域名时只能用 `onboarding@resend.dev`，且只能发给你自己的 Resend 账号邮箱 |
| `CH_ADMIN_EMAIL` | 首次启动绑定到管理员；若 `CH_ADMIN_PASSWD` 留空，则创建一个只能用邮箱登录的管理员 |
| `CH_EMAIL_ALLOWED_DOMAINS` | 这些域名（逗号分隔）的邮箱首次验证即自动建号（角色 operator）；其余邮箱需管理员邀请 |
| `CH_ALLOW_REGISTRATION` | 设为 `1` 时任何邮箱都能自动建号（公开站点慎用） |
| `CH_PASSWORD_LOGIN` | `false` = 登录页去掉「账号口令」页签（纯邮箱登录）；改后需 `docker compose build web` |

**安全措施**：验证码 10 分钟有效、只存哈希、用后即焚；同一码最多试 5 次；同一邮箱 60 秒冷却、每小时最多 10 封；
同一 IP 每小时最多 30 封（均可用 `ACIS_EMAIL_*` 环境变量调整，见 `accountsvc.py` 顶部）。邮箱登录建的账号没有口令，口令登录无法命中。

**邀请用户 / 绑定邮箱**

```bash
docker compose exec accountsvc python manage.py invite sam@your-domain.com operator   # 邀请(无口令账号)
docker compose exec accountsvc python manage.py email admin boss@your-domain.com      # 给已有账号绑定登录邮箱
```

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

### 阿里云大陆机房（杭州/上海/北京等）额外注意

1. **域名须 ICP 备案**才能用 80/443 对外提供网站；备案前只能用 IP + 非标准端口临时测试。香港/新加坡机房无需备案。
2. **Docker Hub 在大陆基本不可用**：`mysql` / `redis` / `nginx` / `node` / `ubuntu` 基础镜像需要配镜像加速
   （阿里云控制台「容器镜像服务 ACR → 镜像加速器」给出专属地址，写进 `/etc/docker/daemon.json` 的 `registry-mirrors`），
   或在香港机器/本地构建好后推到 ACR 个人版，再在服务器上 `docker pull`。
3. **构建加速**：在 `.env` 打开 `APT_MIRROR` / `PIP_INDEX_URL` / `NPM_REGISTRY`（见 `.env.example` 末尾）。
   Chromium 下载若仍失败，用上文「特殊网络环境」的离线 `pw-cache`。
4. **Resend 发信**：接口在海外，大陆服务器一般能调通；但发往 QQ/163 邮箱时注意先完成发件域名验证，否则易进垃圾箱。

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
