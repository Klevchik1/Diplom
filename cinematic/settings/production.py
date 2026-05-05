from .base import *

DEBUG = False
ALLOWED_HOSTS = ['168.222.140.166', 'localhost', '127.0.0.1']

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

# Безопасность
CSRF_COOKIE_SECURE = False  # Изменить на True после настройки HTTPS
SESSION_COOKIE_SECURE = False  # Изменить на True после настройки HTTPS
CSRF_TRUSTED_ORIGINS = [
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
            'filename': BASE_DIR / 'django.log',
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