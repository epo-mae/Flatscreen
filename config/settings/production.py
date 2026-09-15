from .base import *
from django.core.exceptions import ImproperlyConfigured

if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('Set FLATSCREEN_SECRET_KEY to a random secret of at least 50 characters.')
if not os.environ.get('FLATSCREEN_ALLOWED_HOSTS') or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit FLATSCREEN_ALLOWED_HOSTS for production.')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
# Flatscreen commonly uses one private hostname. Subdomain-wide HSTS and browser
# preload registration would be inappropriate without control of the whole domain.
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
# Only enable behind the documented loopback-only, trusted reverse proxy.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
