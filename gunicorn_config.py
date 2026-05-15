bind = "unix:/var/www/cinema/run/gunicorn.sock"
workers = 3
worker_class = "sync"
timeout = 120
keepalive = 5
daemon = False
pidfile = "/var/www/cinema/run/gunicorn.pid"
accesslog = "/var/www/cinema/logs/gunicorn-access.log"
errorlog = "/var/www/cinema/logs/gunicorn-error.log"
loglevel = "info"
raw_env = [
    'DJANGO_SETTINGS_MODULE=cinematic.settings.production'
]
