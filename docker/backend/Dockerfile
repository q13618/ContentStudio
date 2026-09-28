# contentHub 后端统一镜像: chAPI / 文件服务 / 渲染 worker / 落库消费者 / MCP / 账号服务 共用
# 基于 Ubuntu 24.04 (Python 3.12), Playwright Chromium 依赖在 Ubuntu 上官方支持最好
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
# 可选: 锁定 playwright 版本(与离线浏览器缓存配套时使用)
ARG PLAYWRIGHT_VERSION=""
# 可选: 国内机房加速(如阿里云大陆 ECS), 在 .env 里设置, 留空 = 官方源
#   APT_MIRROR=http://mirrors.aliyun.com   PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
#   PLAYWRIGHT_DOWNLOAD_HOST=<Playwright 浏览器下载镜像>
ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""
ARG PLAYWRIGHT_DOWNLOAD_HOST=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# 可选: 企业代理/内网根证书(把 *.crt 放进 docker/certs/ 即可, 默认为空)
COPY docker/certs/ /usr/local/share/ca-certificates/extra/
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://archive.ubuntu.com|$APT_MIRROR|g; s|http://security.ubuntu.com|$APT_MIRROR|g" /etc/apt/sources.list.d/ubuntu.sources; \
    fi \
 && if [ -n "$PIP_INDEX_URL" ]; then printf '[global]\nindex-url = %s\n' "$PIP_INDEX_URL" > /etc/pip.conf; fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip ca-certificates tzdata curl fonts-noto-cjk \
 && update-ca-certificates \
 && python3 -m venv /opt/venv \
 && rm -rf /var/lib/apt/lists/*

COPY code/src/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && pip install "alibabacloud-oss-v2" "cos-python-sdk-v5>=1.9.30" "bcrypt" \
 && if [ -n "$PLAYWRIGHT_VERSION" ]; then pip install "playwright==$PLAYWRIGHT_VERSION"; fi

# Chromium: 若 docker/backend/pw-cache/ 里放了离线浏览器缓存则直接用, 否则联网下载
COPY docker/backend/pw-cache/ /ms-playwright/
RUN apt-get update \
 && python -m playwright install-deps chromium \
 && if ls /ms-playwright | grep -q '^chromium'; then echo "use offline chromium cache"; \
    else if [ -n "$PLAYWRIGHT_DOWNLOAD_HOST" ]; then export PLAYWRIGHT_DOWNLOAD_HOST; else unset PLAYWRIGHT_DOWNLOAD_HOST; fi; \
         python -m playwright install chromium; fi \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /data/contenthub/src
COPY code/src/ /data/contenthub/src/
COPY docker/accountsvc/ /data/contenthub/accountsvc/
COPY docker/filesvc/uploadShim.py /data/contenthub/src/main/uploadShim.py
COPY docker/backend/entrypoint.sh /usr/local/bin/ch-entrypoint
RUN chmod +x /usr/local/bin/ch-entrypoint \
 && mkdir -p /data/contenthub/log /data/contenthub/data /data/webserver/temp /data/filestorage

ENTRYPOINT ["ch-entrypoint"]
CMD ["api"]
