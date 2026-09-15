from .base import *
import secrets

DEBUG = True
LOCAL_SETUP = True
# A persistent local-only secret; production requires an environment variable.
secret_file = DATA_DIR / '.development-secret'
if not SECRET_KEY:
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(64), encoding='utf-8')
    SECRET_KEY = secret_file.read_text(encoding='utf-8').strip()

