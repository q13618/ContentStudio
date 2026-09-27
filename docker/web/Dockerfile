# 前端构建 + nginx 网关(官方镜像, 无需编译 upload 模块; /upload 由 filesvc 的 uploadShim 处理)
FROM node:22-alpine AS build
WORKDIR /app
# 可选: 企业代理/内网根证书(docker/certs/*.crt)
COPY docker/certs/ /tmp/certs/
RUN cat /tmp/certs/*.crt > /tmp/extra-ca.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/tmp/extra-ca.pem
COPY code/webserver/package*.json ./
RUN npm ci --no-audit --no-fund
COPY code/webserver/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html/chapp
