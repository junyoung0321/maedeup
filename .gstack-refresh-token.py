"""Refresh .gstack-demo-token with a fresh 30-day JWT."""
import sys
from datetime import datetime, timedelta, timezone

env_path = '.env'
env_vars = {}
with open(env_path, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            env_vars[k.strip()] = v.strip()

jwt_secret = env_vars.get('JWT_SECRET', '')
if not jwt_secret:
    print('ERROR: JWT_SECRET not found in .env', file=sys.stderr)
    sys.exit(1)

from jose import jwt as jose_jwt

payload = {
    'sub': '1',
    'email': 'dnfltkagudwp123@gmail.com',
    'name': '정준영',
    'picture': None,
    'calendar_consent': True,
    'is_guest': False,
    'exp': datetime.now(timezone.utc) + timedelta(days=30),
}
token = jose_jwt.encode(payload, jwt_secret, algorithm='HS256')
with open('.gstack-demo-token', 'w', encoding='utf-8') as f:
    f.write(token)
print('Token written to .gstack-demo-token')
print('Expires (UTC):', (datetime.now(timezone.utc) + timedelta(days=30)).isoformat())
