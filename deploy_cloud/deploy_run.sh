#!/bin/bash
# 自媒体智能体平台 · 服务器端部署脚本
set -e
cd /opt/mediastudio

# 1. Docker 镜像加速（阿里云服务器拉 Docker Hub 必需）
if [ ! -f /etc/docker/daemon.json ] || ! grep -q "mirror" /etc/docker/daemon.json 2>/dev/null; then
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev"
  ]
}
EOF
  systemctl daemon-reload
  systemctl restart docker
  sleep 5
  docker start $(docker ps -aq) 2>/dev/null || true
  echo "docker mirror configured"
fi

# 2. compose 环境变量
echo "GATEWAY_API_KEY=$(cat deploy_cloud/gateway_api_key.txt)" > deploy_cloud/.env

# 3. 构建并启动
cd deploy_cloud
docker compose -f docker-compose.cloud.yml --env-file .env up -d --build
echo "=== build & up done ==="
docker compose -f docker-compose.cloud.yml ps
