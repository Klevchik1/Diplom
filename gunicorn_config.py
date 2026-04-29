import os
import sys

# Основные настройки
bind = "127.0.0.1:8000"
workers = 3
timeout = 120
max_requests = 1000
max_requests_jitter = 50

# Директории для логов и pid
pidfile = "/var/www/cinema/run/gunicorn.pid"
accesslog = "/var/log/cinema_access.log"
errorlog = "/var/log/cinema_error.log"
loglevel = "info"

# Рабочая директория
chdir = "/var/www/cinema"

# Путь к Python
pythonpath = "/var/www/cinema"

# Безопасность
user = "www-data"
group = "www-data"
umask = 0o022

# Переменные окружения
raw_env = [
    "DJANGO_SETTINGS_MODULE=cinematic.production_settings",
]
