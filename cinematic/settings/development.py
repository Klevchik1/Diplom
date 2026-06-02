from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']  # Удобно для разработки

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cinema',
        'USER': 'postgres',
        'PASSWORD': '123',
        'HOST': '192.168.0.10',
        'PORT': '5432',
    }
}

# Для разработки без HTTPS
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False