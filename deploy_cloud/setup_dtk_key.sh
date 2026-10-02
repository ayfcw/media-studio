#!/bin/bash
# 云端 DTK 生成 API Key 并写入平台 settings
# 用法：DTK_ADMIN_PASSWORD=xxx bash setup_dtk_key.sh（密码不入库）
set -e
DTK=http://172.17.0.1:8000
GW=http://127.0.0.1:9000
ADMIN_PW="${DTK_ADMIN_PASSWORD:?export DTK_ADMIN_PASSWORD first}"

# 1. 登录 DTK
curl -s -c /tmp/s.txt -X POST "$DTK/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "$(ADMIN_PW="$ADMIN_PW" python3 -c "import json,os;print(json.dumps({'username':'admin','password':os.environ['ADMIN_PW']}))")" > /dev/null

# 2. 生成 API Key（douyin:read，永久）
echo "--- create api key ---"
curl -s -b /tmp/s.txt -X POST "$DTK/api/v1/admin/api-keys" -H 'Content-Type: application/json' \
  -d '{"name":"mediastudio-cloud","scopes":["douyin:read"]}' > /tmp/key_resp.json
NEWKEY=$(python3 -c "import json;d=json.load(open('/tmp/key_resp.json'));print(d['data']['key'])")
echo "key prefix: ${NEWKEY:0:20}..."

# 3. 写入平台 settings（网关深合并，nginx 注入 X-API-Key）
echo "--- update platform settings ---"
NEWKEY="$NEWKEY" python3 -c "import json,os;print(json.dumps({'dtk':{'api_key':os.environ['NEWKEY']}}))" > /tmp/set.json
curl -s -X PUT "$GW/api/v1/settings" -H "X-API-Key: ${GATEWAY_API_KEY:?export GATEWAY_API_KEY first}" -H 'Content-Type: application/json' -d @/tmp/set.json | head -c 300
echo ""
rm -f /tmp/s.txt /tmp/key_resp.json /tmp/set.json
echo "DONE"
