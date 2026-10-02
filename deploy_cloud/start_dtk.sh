#!/bin/bash
# 云端：启动 DTK 采集栈（镜像已 load）+ 全栈编排
set -e
cd /opt/mediastudio/Douyin_TikTok_Download_API
# DTK API 绑在 docker 网桥 IP 上：studio 容器经 host-gateway(=172.17.0.1) 可达，
# 且不暴露在公网网卡上（阿里云安全组之外多一层保险）
DTK_BIND_HOST=172.17.0.1 docker compose -p dtk -f docker/compose.yml up -d
echo "dtk stack up"
sleep 20
docker ps --format '{{.Names}} {{.Status}}' | grep dtk

# 重启 studio 网关使 DTK_URL 生效
cd /opt/mediastudio/deploy_cloud
docker compose -f docker-compose.cloud.yml --env-file .env up -d --force-recreate gateway
echo "gateway recreated"

# 端到端验证
sleep 10
echo "--- health ---"
curl -s http://127.0.0.1:9000/api/v1/health
echo ""
echo "--- dtk parse via gateway ---"
curl -s -X POST "http://127.0.0.1:9000/api/v1/tasks/analyze-link" \
  -H "X-API-Key: $(cat gateway_api_key.txt)" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://v.douyin.com/laJ4i-Ep1Ns/"}'
echo ""
