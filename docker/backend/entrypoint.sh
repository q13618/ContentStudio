#!/bin/sh
# contentHub 容器入口: 按第一个参数启动对应进程
set -e
SRC=/data/contenthub/src
mkdir -p /data/webserver/temp /data/webserver/ch_data /data/filestorage /data/contenthub/log
mkdir -p /data/webserver/temp/output
for i in 0 1 2 3 4 5 6 7 8 9; do mkdir -p /data/webserver/temp/$i /data/webserver/temp/web/$i; done

waitfor() {  # waitfor host port
  for n in $(seq 1 60); do
    python -c "import socket,sys; socket.create_connection(('$1',$2),2)" 2>/dev/null && return 0
    echo "waiting for $1:$2 ..."; sleep 2
  done
  echo "timeout waiting for $1:$2"; exit 1
}

case "$1" in
  accountsvc)
    waitfor "${ACIS_REDIS_HOST:-redis}" 6379
    cd /data/contenthub/accountsvc
    exec gunicorn -w 2 -b 0.0.0.0:8160 --access-logfile - accountsvc:application ;;
  init)
    waitfor "$CH_MYSQL_HOST" 3306
    cd $SRC
    python tools/initTables.py
    python tools/initSeed.py
    echo "init done" ;;
  api)
    waitfor "$CH_MYSQL_HOST" 3306; waitfor "$CH_REDIS_HOST" 6379
    cd $SRC/main
    exec gunicorn -w "${CH_API_WORKERS:-3}" -b 0.0.0.0:9978 --timeout 120 --access-logfile - chAPI:application ;;
  filesvc)
    waitfor "$CH_REDIS_HOST" 6379
    cd $SRC/main
    exec gunicorn -w 2 -b 0.0.0.0:8005 --timeout 300 --access-logfile - uploadShim:application ;;
  render)
    waitfor "$CH_MYSQL_HOST" 3306; waitfor "$CH_REDIS_HOST" 6379
    cd $SRC/schedule
    exec python renderWorker.py ;;
  trans)
    waitfor "$CH_MYSQL_HOST" 3306; waitfor "$CH_REDIS_HOST" 6379
    cd $SRC/processor
    exec python transferCHMysql.py ;;
  mcp)
    waitfor "$CH_MCP_UPSTREAM_HOST" "$CH_MCP_UPSTREAM_PORT"
    cd $SRC/mcpapi
    exec python mcp_entry.py ;;
  ops)
    # 每日巡检 + 归档(dry-run), 替代 crontab
    cd $SRC
    while true; do
      python chmonitor/dailyCheck.py || true
      python schedule/archive.py || true
      sleep 86400
    done ;;
  *)
    exec "$@" ;;
esac
