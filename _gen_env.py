# -*- coding: utf-8 -*-
import base64, os, secrets, io
root = r'C:\Users\24688\dev\Douyin_TikTok_Download_API'
env_path = os.path.join(root, '.env')
secret = base64.b64encode(secrets.token_bytes(48)).decode()
pg = secrets.token_hex(24)
rd = secrets.token_hex(24)
content = f"""# generated for local dtk stack
DTK_SECRET_KEY={secret}
POSTGRES_PASSWORD={pg}
REDIS_PASSWORD={rd}
DTK_DATABASE_URL=postgresql+asyncpg://dtk:{pg}@postgres:5432/dtk
DTK_REDIS_URL=redis://:{rd}@redis:6379/0
DTK_FORWARDED_ALLOW_IPS=
DTK_LOG_LEVEL=info
DTK_LOG_JSON=true
DTK_BROWSER_RPC_URL=
DTK_DOWNLOADER_URL=
DTK_BIND_HOST=127.0.0.1
DTK_BIND_PORT=8000
DTK_REDIS_MAXMEMORY=320mb
"""
io.open(env_path, 'w', encoding='utf-8', newline='\n').write(content)
print('.env written, bytes:', len(content))
print('exists:', os.path.exists(env_path))
