#!/bin/bash
# media-studio 云端数据每日备份：配置 + 平台数据 + DTK 数据库
# 输出 /root/ms_backup/ms-backup-YYYYmmdd.tar.gz，保留最近 7 份
set -e
BASE=/opt/mediastudio
OUT=/root/ms_backup
STAMP=$(date +%Y%m%d)
WORK=/tmp/ms-backup-$STAMP

mkdir -p "$OUT" "$WORK"

# 1. 配置与密钥（.env / gateway_api_key.txt / 真实 nginx.conf / mpt-config）
mkdir -p "$WORK/config"
cp "$BASE/deploy_cloud/.env" "$WORK/config/" 2>/dev/null || true
cp "$BASE/deploy_cloud/gateway_api_key.txt" "$WORK/config/" 2>/dev/null || true
cp "$BASE/deploy_cloud/nginx.conf" "$WORK/config/" 2>/dev/null || true
cp "$BASE/deploy_cloud/mpt-config.toml" "$WORK/config/" 2>/dev/null || true
cp "$BASE/Douyin_TikTok_Download_API/.env" "$WORK/config/dtk.env" 2>/dev/null || true

# 2. 平台数据（任务库/加密设置/媒体缓存/素材库/成片产物）
mkdir -p "$WORK/data"
if [ -d "$BASE/deploy_cloud/data" ]; then
    cp -r "$BASE/deploy_cloud/data/." "$WORK/data/" 2>/dev/null || true
fi

# 3. DTK 数据库（身份/Cookie/下载记录）
if docker ps --format '{{.Names}}' | grep -q '^dtk-postgres-1$'; then
    docker exec dtk-postgres-1 pg_dumpall -U dtk > "$WORK/dtk_pg_dumpall.sql" 2>/dev/null || true
fi

# 4. 打包 + 清理工作目录
tar -czf "$OUT/ms-backup-$STAMP.tar.gz" -C "$WORK" .
rm -rf "$WORK"

# 5. 只保留最近 7 份
ls -1t "$OUT"/ms-backup-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "backup done: $OUT/ms-backup-$STAMP.tar.gz ($(du -h "$OUT/ms-backup-$STAMP.tar.gz" | cut -f1))"
