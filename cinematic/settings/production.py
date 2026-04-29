from .base import *

DEBUG = False
ALLOWED_HOSTS = ['168.222.140.166', 'your-domain.com']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'cinema_db'),
        'USER': os.getenv('DB_USER', 'cinema_user'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

CSRF_COOKIE_SECURE = False  # True после настройки HTTPS
SESSION_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = ['http://168.222.140.166']