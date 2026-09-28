# 内容中枢 contentHub

> 内容管理与多平台发布平台 —— 以「**主题（Topic）资产**」为核心，把一次选题的资料、图片、说明沉淀成可复用资产，再以版式引擎派生各平台合规产物。

contentHub 不是「又一个一键分发工具」，而是 **「选题资产工作台（Topic Asset Studio）」**：

**主题资产录入 → 多版式渲染 → 多平台合规产物 → 通道投递**

交付形态为 **「一键推送到草稿箱 / 一键生成可发布素材包」，最终发布动作 100% 保留人工确认**（受国内主流平台政策与合规红线约束）。

---

## 目录

- [项目定位](#项目定位)
- [技术栈](#技术栈)
- [整体架构](#整体架构)
- [业务模块](#业务模块)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
  - [后端（Flask `/chapi`）](#后端flask-chapi)
  - [前端（Vue 3）](#前端vue-3)
- [配置说明](#配置说明)
- [三条红线](#三条红线)
- [文档导航](#文档导航)
- [许可证](#许可证)

---

## 项目定位

| 项 | 内容 |
|---|---|
| 项目名称 | contentHub（内容中枢 / 内容管理与多平台发布平台） |
| 目标平台 | 微信公众号（草稿投递）· 小红书（素材包导出）· 通用 HTML（站内预览/导出） |
| 工程基线 | 复用 `ylwzProject/museum` 的 `common/` 公共层与代码生成器 |
| 数据表 | 12 张 `ch_*` 表 |
| 业务模块 | 8 个主干模块（C1–C8）+ 2 个后置模块（C9–C10） |
| 阶段划分 | Phase 0–3，约 12 周（单人全职，不含资质等待） |

**核心判断**（决定范围）：

1. **全自动发布在国内主流平台已被政策封死，「半自动」是唯一可行形态** —— 推送 ≠ 发布。
2. 真正的技术难点是**渲染引擎**（版式中间层），不是发布通道。
3. 市场空白在于「结构化主题资产 → 多版式渲染 → 各平台合规产物 → 通道投递」的完整流水线。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.13 + Flask（HTTP 门面 `/chapi`）+ gunicorn/uvicorn |
| 数据库 | MySQL 8.0 + Redis |
| 渲染 | Jinja2（服务端渲染）+ Playwright（HTML→PNG 卡片截图）+ Pillow（图像处理） |
| 前端 | Vue 3 + Vite 5 + Element Plus + Tailwind CSS + Pinia + Vue Router（纯 JavaScript） |
| 开放接口 | MCP Server（`mcpapi/`，streamable-http 传输，8 只读 tool + 3 resource） |
| 文件后端 | 配置驱动三态切换：`SELFFILE` / `ALIOSS` / `TENCENT` |

运行依赖见 [`code/src/requirements.txt`](code/src/requirements.txt)；前端依赖见 [`code/webserver/package.json`](code/webserver/package.json)。

---

## 整体架构

```text
┌─────────────┐     /chapi/*      ┌──────────────────────────────┐
│  浏览器前端   │ ───────────────► │  main/chAPI.py (Flask 门面)    │
│ Vue3 + Vite  │ ◄─────────────── │  main/chAPIPost.py (报文分发)  │
└─────────────┘   统一 JSON 信封   └──────────────┬───────────────┘
                                                  │
            ┌─────────────────────────────────────┼─────────────────────────────┐
            ▼                                     ▼                             ▼
    ┌──────────────┐                    ┌──────────────────┐          ┌──────────────────┐
    │ processor/*  │  业务服务层          │   engine/*       │  渲染引擎  │   schedule/*     │  异步/定时
    │ topicService │  (C1–C8 服务)       │ layoutEngine     │          │ renderWorker     │
    │ assetService │                    │ inlineStyle      │          │ credentialCheck  │
    │ publishService│                   │ htmlToImage      │          │ archive          │
    │ compliance...│                    │ imageProc        │          └──────────────────┘
    └──────┬───────┘                    └────────┬─────────┘
           │                                     │
           ▼                                     ▼
    ┌──────────────┐  门面          ┌──────────────────────────────┐
    │ common/*     │ ◄────────────  │  config/*   (FILE_SYSTEM_MODE │
    │ mysqlCommon  │  唯一数据访问    │  mysql/redis/oss/cos/... )   │
    │ fileStorage  │                └──────────────────────────────┘
    └──────────────┘
           │
           ▼
    MySQL 8.0  ──  Redis  ──  文件存储(SELFFILE/ALIOSS/TENCENT)
```

- **HTTP 门面**：`main/chAPI.py` 仅做「HTTP 协议 ↔ 业务报文」转换，不含业务逻辑；业务分发在 `main/chAPIPost.py`；统一 JSON 信封返回。
- **文件后端**：代码禁止出现 `if FILE_SYSTEM_MODE == "ALIOSS"` 之类的硬编码分支，一律经 `common/fileStorageCommon.py` 门面。
- **数据库**：结构以 `database/ch_*.txt` 为唯一数据源，由生成器驱动 `common/mysqlCommon.py`，业务层只调 `comMysql.xxx_ch_*()`。

---

## 业务模块

| 模块 | 职责 |
|---|---|
| C1 主题资产 | 主题 CRUD（全字段）、附图与图注绑定、状态机、版本快照 |
| C2 素材图库 | 三后端上传切换、`contentHash` 去重、裁剪压缩、EXIF 剥离、缩略图/封面生成 |
| C3 版式引擎 | 版式 DSL（`ch_layout`）、4 套模板（上下 / 左右轮播 / 长图 / 左右滑动多图集）、Jinja2 渲染、站内预览 |
| C4 平台适配 | 微信内联样式器与图片转存、小红书图集卡片（Playwright 截图）、通用 HTML |
| C5 发布投递 | 公众号草稿投递（`draft/add`）、小红书素材包 ZIP 导出、幂等防重发、发布记录 |
| C6 合规风控 | AI 内容标识、发布频率限流、敏感词检测、平台规格校验、二次确认 |
| C7 账号凭据 | 多账号凭据 AES 加密存储（`credentialCipher.py`）、健康巡检、平台能力矩阵 |
| C8 开放接口 | MCP Server（只读 tool + resource，streamable-http 传输）、审计日志 |
| C9–C10 | 后置模块（监控告警、运维归档等） |

---

## 目录结构

```text
contentHub/
├── code/
│   ├── src/                      # 后端（Python / Flask）
│   │   ├── main/                 # HTTP 门面（chAPI.py / chAPIPost.py）
│   │   ├── processor/            # 业务服务层（topic/asset/render/publish/compliance/audit...）
│   │   │   └── platformAdapter/  # 平台适配器（微信 / 小红书 / 通用）
│   │   ├── engine/               # 渲染引擎（layout / inlineStyle / htmlToImage / imageProc）
│   │   ├── common/               # 公共层（mysql / 文件存储 / 云厂商 SDK 门面 / 凭据加密）
│   │   ├── config/               # 配置（mysql / redis / oss / cos / wechat / mcp ...）
│   │   ├── database/             # ch_*.txt 表结构（唯一数据源）+ 生成器
│   │   ├── schedule/             # 异步/定时任务（renderWorker / credentialCheck / archive）
│   │   ├── mcpapi/               # MCP Server（独立只读层）
│   │   ├── monitor/ / chmonitor/ # 监控
│   │   ├── tools/ / test/        # 工具与测试
│   │   ├── requirements.txt
│   │   └── plan.md
│   ├── webserver/                # 前端（Vue 3 / Vite）— 详见其内 README.md
│   └── data/                     # 运行态数据（assetpack / filestorage / preview / monitor / webserver）
├── doc/                          # 文档（用户手册 PDF / 安装要求 / redis 覆盖说明 / 环境导出脚本）
└── plan/                         # 开发计划与验收报告（HTML / MD / PDF）
```

---

## 环境要求

| 项 | 后端 | 前端 |
|---|---|---|
| 运行时 | Python ≥ 3.13 | Node.js ≥ 18（实测 v22.20.0） |
| 数据库 | MySQL 8.0 + Redis | — |
| 浏览器引擎 | Playwright Chromium（截图用） | — |
| 包管理器 | pip | npm（实测 10.9.3） |

后端额外系统依赖（Debian/Ubuntu）：`apt-get install libnss3 libnspr4 ... fonts-noto-cjk`，详见 [`doc/ubuntu安装要求.txt`](doc/ubuntu安装要求.txt)。

---

## 快速开始

### 后端（Flask `/chapi`）

```bash
cd code/src

# 1. 安装依赖
pip install -r requirements.txt
#   如需小红书截图：pip install playwright && python -m playwright install chromium
#   如需云端文件后端（按环境）：pip install oss2  或  pip install cos-python-sdk-v5

# 2. 建立数据库（详见 doc/ 下建表命令与密码文件）
#    mysql 8.0 执行 database/ 下的建表脚本，并灌入种子数据

# 3. 配置（复制并修改 local_settings 模板，填入 mysql/redis/文件后端等）
#    config/local_settings.py

# 4. 启动
cd main
python chAPI.py                 # 开发态，默认端口 5000
# 或生产由 gunicorn 以 application 为 WSGI app 启动
```

### 前端（Vue 3）

```bash
cd code/webserver
npm i
npm run dev      # 访问 http://localhost:3000/chapp/
npm run build    # 产出 dist/
```

前端开发服务：`port 3000`、`host 0.0.0.0`，代理 `/chapi` 与 `/upload` 到本机后端（默认 `127.0.0.1:5000`）。
构建产物基准路径 `base: '/chapp/'`，与后端同源部署时前端挂在 `/chapp/` 下。前端完整说明见 [`code/webserver/README.md`](code/webserver/README.md)。

---

## 配置说明

配置集中在 `code/src/config/`，通过环境变量/本地配置切换：

- `FILE_SYSTEM_MODE` ∈ `{ALIOSS, TENCENT, SELFFILE}` —— 文件后端三态切换，**代码经 `common/fileStorageCommon.py` 门面，禁止硬编码分支**。
- `mysqlSettings` / `redisSettings` / `aliyunSettings` / `tencentSettings` / `wechatSettings` / `mcpConfig` —— 各能力配置。
- 凭据加密：`common/credentialCipher.py`（AES-256-GCM，SP4a·C6 投递链路）。
- 登录：Docker 部署自带 `accountsvc` 账号服务，支持账号口令与 **Resend 邮箱验证码登录**（配置 `RESEND_API_KEY` 等，详见 [`docker/README.md`](docker/README.md)）。

---

## 三条红线

1. **R1 数据库结构以 `ch_*.txt` 为唯一数据源，业务层禁止裸 SQL** —— 改表只改 `database/ch_*.txt` → 重跑生成器 → 合并 `common/mysqlCommon.py`。
2. **R2 文件后端配置驱动**，一律经 `common/fileStorageCommon.py` 门面，禁止 `if FILE_SYSTEM_MODE == "ALIOSS"` 之类的硬编码分支。
3. **R3 合规红线** —— 不引入任何小红书/公众号自动发布、自动投递入口；发布动作 100% 保留人工确认。

---

## 文档导航

- `plan/contentHub开发计划.md` —— 完整开发计划（v1.0，2026-09-17）。
- `plan/content-hub-开发计划v3.html` —— 架构与阶段口径（**冲突时以此为准**）。
- `plan/content-hub-调研与开发计划.html` —— 产品定位与合规边界。
- `plan/content-hub-Phase0-任务清单.md` —— 可执行细节。
- `plan/前端开发计划.md` —— 前端工程规范。
- `doc/contentHub用户手册.pdf` —— 用户手册。
- `doc/ubuntu安装要求.txt` / `doc/mysql数据库建立命令和password.txt` —— 安装与建库。
- `code/webserver/README.md` —— 前端工程说明。

---

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

```text
MIT License

Copyright (c) 2026 Steven Lian's team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
