from .base import *
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv(BASE_DIR / '.env.production')

DEBUG = False
ALLOWED_HOSTS = ['cinemapremiere.online', 'www.cinemapremiere.online', '168.222.140.166', 'localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'cinema_db'),
        'USER': os.getenv('DB_USER', 'cinema_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Статические и медиа файлы
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Email настройки (Яндекс)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.yandex.ru'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# API Кинопоиска (токены через запятую)
KINOPOISK_API_KEY = os.getenv('KINOPOISK_API_KEY', '').split(',')

# YooKassa
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')

# Безопасность
CSRF_COOKIE_SECURE = True  # Изменить на True после настройки HTTPS
SESSION_COOKIE_SECURE = True  # Изменить на True после настройки HTTPS
SECURE_SSL_REDIRECT = True
CSRF_TRUSTED_ORIGINS = [
    'https://cinemapremiere.online',
    'https://www.cinemapremiere.online',
    'http://cinemapremiere.online',
    'http://www.cinemapremiere.online',
    'http://168.222.140.166',
    'http://localhost',
    'http://127.0.0.1',
]

# Логирование
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/var/www/cinema/logs/django.log',  # Полный путь, а не BASE_DIR
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
