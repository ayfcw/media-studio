#!/bin/bash
# 云端 DTK 初始化：setup token → 建管理员 → 登录 → 导入抖音 Cookie
# 用法：DTK_ADMIN_PASSWORD=xxx bash init_dtk.sh（密码不入库）
set -e
DTK=http://172.17.0.1:8000
ADMIN_PW="${DTK_ADMIN_PASSWORD:?export DTK_ADMIN_PASSWORD first}"

# 1. 取 setup token（启动横幅 /setup?token=xxx；redis 复用时新日志也会打印）
TOKEN=$(docker logs dtk-api-1 2>&1 | grep -oE 'setup\?token=[A-Za-z0-9_-]+' | tail -1 | cut -d'=' -f2)
if [ -z "$TOKEN" ]; then echo "ERROR: no setup token found"; exit 1; fi
echo "token prefix: ${TOKEN:0:10}..."

# 2. 初始化管理员（与本地 DTK 同一套账号）
echo "--- setup/init ---"
TOKEN="$TOKEN" ADMIN_PW="$ADMIN_PW" python3 -c "import json,os;print(json.dumps({'token':os.environ['TOKEN'],'username':'admin','password':os.environ['ADMIN_PW']}))" > /tmp/dtk_init.json
curl -sS -X POST "$DTK/api/setup/init" -H 'Content-Type: application/json' -d @/tmp/dtk_init.json | head -c 300
echo ""

# 3. 登录拿会话
echo "--- login ---"
curl -s -c /tmp/dtk_session.txt -X POST "$DTK/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "$(ADMIN_PW="$ADMIN_PW" python3 -c "import json,os;print(json.dumps({'username':'admin','password':os.environ['ADMIN_PW']}))")" | head -c 200
echo ""

# 4. 导入抖音身份
echo "--- import identity ---"
python3 -c "
import json
cookies = open('/tmp/dy_cookie.txt').read().strip()
ua = open('/tmp/dy_ua.txt').read().strip()
json.dump({'platform':'douyin','cookies':cookies,'user_agent':ua}, open('/tmp/dy_import.json','w'))
"
curl -s -b /tmp/dtk_session.txt -X POST "$DTK/api/v1/admin/identities/import" \
  -H 'Content-Type: application/json' -d @/tmp/dy_import.json | head -c 400
echo ""

# 5. 校验身份池
echo "--- identity pool ---"
curl -s -b /tmp/dtk_session.txt "$DTK/api/v1/admin/identities/pool" | head -c 600
echo ""
rm -f /tmp/dtk_init.json /tmp/dy_import.json /tmp/dtk_session.txt /tmp/dy_cookie.txt /tmp/dy_ua.txt
echo "DONE"
