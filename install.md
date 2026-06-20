# 📦 УСТАНОВКА И НАСТРОЙКА ВЕБ-ПРИЛОЖЕНИЯ «КИНОТЕАТР»

Данное руководство содержит пошаговые инструкции по установке и настройке веб-приложения «Кинотеатр» в среде разработки (локально) и на продакшен-сервере.

---

## 📋 СОДЕРЖАНИЕ

1. [Системные требования](#-системные-требования)
2. [Подготовка окружения](#-подготовка-окружения)
3. [Установка приложения (локальная разработка)](#-установка-приложения-локальная-разработка)
4. [Настройка переменных окружения](#-настройка-переменных-окружения)
5. [Настройка базы данных](#-настройка-базы-данных)
6. [Настройка Django](#-настройка-django)
7. [Настройка внешних сервисов](#-настройка-внешних-сервисов)
8. [Установка на продакшен-сервер](#-установка-на-продакшен-сервер)
9. [Настройка веб-сервера Nginx](#-настройка-веб-сервера-nginx)
10. [Настройка Gunicorn и Supervisor](#-настройка-gunicorn-и-supervisor)
11. [Настройка автоматического деплоя](#-настройка-автоматического-деплоя)
12. [Устранение неполадок](#-устранение-неполадок)

---

## 💻 СИСТЕМНЫЕ ТРЕБОВАНИЯ

### Минимальные требования для сервера

| Компонент | Требование |
|-----------|------------|
| **Операционная система** | Ubuntu Server 24.04 LTS |
| **Процессор** | 2 ядра, 2.2 ГГц |
| **Оперативная память** | 4 ГБ |
| **Дисковое пространство** | 30 ГБ (SSD) |
| **Интерпретатор** | Python 3.12 |
| **СУБД** | PostgreSQL 16 |
| **Веб-сервер** | Nginx 1.24 |

### Требования для клиентских устройств

| Компонент | Требование |
|-----------|------------|
| **Операционная система** | Windows 10+, macOS, Linux |
| **Веб-браузер** | Яндекс.Браузер, Chrome 90+, Firefox 88+, Edge 90+, Safari 14+ |
| **Интернет-соединение** | от 10 Мбит/с |

---

## 🛠️ ПОДГОТОВКА ОКРУЖЕНИЯ

### Установка Python 3.12

```bash
# Добавление репозитория deadsnakes для Ubuntu
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Установка Python 3.12 и необходимых пакетов
sudo apt install python3.12 python3.12-venv python3.12-dev python3-pip

# Проверка установки
python3.12 --version
```

### Установка PostgreSQL 16

```bash
# Добавление официального репозитория PostgreSQL
sudo sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# Установка PostgreSQL
sudo apt install postgresql-16 postgresql-contrib-16

# Проверка статуса
sudo systemctl status postgresql
```

### Установка Nginx

```bash
sudo apt install nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Установка Git

```bash
sudo apt install git
git --version
```

---

## 📥 УСТАНОВКА ПРИЛОЖЕНИЯ (ЛОКАЛЬНАЯ РАЗРАБОТКА)

### Клонирование репозитория

```bash
# Переход в рабочую директорию
cd ~/Desktop

# Клонирование репозитория
git clone https://gitlab.irkat.ru/22024/cinema-system
cd Diplom
```

### Создание виртуального окружения

```bash
# Создание виртуального окружения
python3.12 -m venv .venv

# Активация виртуального окружения
# Для Windows:
.venv\Scripts\activate

# Для Linux/macOS:
source .venv/bin/activate
```

### Установка зависимостей

```bash
# Установка всех необходимых пакетов
pip install -r requirements.txt

# Проверка установленных пакетов
pip list
```

---

## 🔧 НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ

### Создание файла .env для локальной разработки
В корневой директории проекта создайте файл .env:
```bash
# Создание файла
touch .env
```

### Содержимое файла .env

```
# Django
SECRET_KEY=ваш-секретный-ключ-замените-на-свой
DEBUG=True

# База данных (локальная)
DB_NAME=cinema
DB_USER=postgres
DB_PASSWORD=ваш-пароль
DB_HOST=localhost
DB_PORT=5432

# API токены Poiskkino.dev (можно несколько через запятую)
KINOPOISK_API_KEYS=ваш-токен-1,ваш-токен-2

# Email (Яндекс.Почта или другой SMTP)
EMAIL_HOST_USER=ваш-email@yandex.ru
EMAIL_HOST_PASSWORD=пароль-приложения

# YooKassa
YOOKASSA_SHOP_ID=ваш-shop-id
YOOKASSA_SECRET_KEY=ваш-secret-key
```

### Создание секретного ключа Django

```bash
# Генерация ключа через Python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Скопируйте полученный ключ и вставьте его в поле SECRET_KEY в файле .env.

---

## 🗄️ НАСТРОЙКА БАЗЫ ДАННЫХ

### Создание базы данных и пользователя PostgreSQL
```bash
# Вход в PostgreSQL
sudo -u postgres psql

# Создание пользователя
CREATE USER cinema_user WITH PASSWORD 'ваш-пароль';

# Создание базы данных
CREATE DATABASE cinema_db OWNER cinema_user;

# Назначение прав
GRANT ALL PRIVILEGES ON DATABASE cinema_db TO cinema_user;

# Выход из PostgreSQL
\q
```

### Настройка подключения к БД
Убедитесь, что в файле .env указаны правильные параметры подключения:
```
DB_NAME=cinema_db
DB_USER=cinema_user
DB_PASSWORD=ваш-пароль
DB_HOST=localhost
DB_PORT=5432
```

---

## ⚙️ НАСТРОЙКА DJANGO

### Выполнение миграций
```bash
# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate
```

### Сбор статических файлов
```bash
# Сбор статики
python manage.py collectstatic --noinput
```

### Создание суперпользователя
```bash
# Создание администратора
python manage.py createsuperuser_custom

# Следуйте инструкциям:
# Email: admin@example.com
# Имя: Админ
# Фамилия: Администратор
# Телефон: +79999999999
# Пароль: ваш-пароль-минимум-8-символов
```

### Создание менеджера
```bash
# Создание пользователя с правами менеджера
python manage.py create_manager --email manager@example.com

# Следуйте инструкциям
```

### Инициализация API-токенов
```bash
# Добавление токена для Poiskkino.dev
python manage.py init_tokens --token=ваш-токен --label=Основной
```

### Заполнение тестовыми данными (опционально)
```bash
# Заполнение БД тестовыми данными
python manage.py big_populate_db --interactive

# Импорт фильмов из API
python manage.py smart_import --pages=3 --year-from=2024
```

### Запуск сервера разработки
```bash
# Запуск Django development server
python manage.py runserver

# Сервер будет доступен по адресу: http://127.0.0.1:8000/
```
---

## 🔌 НАСТРОЙКА ВНЕШНИХ СЕРВИСОВ

Для корректной работы веб-приложения необходимо настроить интеграцию с внешними сервисами: платёжной системой YooKassa, API кинопоиска Poiskkino.dev и SMTP-сервером для отправки электронных писем.

### Настройка YooKassa (платёжная система)

YooKassa используется для приёма онлайн-платежей, генерации чеков и обработки возвратов.

1. **Регистрация в YooKassa**
   - Перейдите на официальный сайт [yookassa.ru](https://yookassa.ru/)
   - Зарегистрируйтесь и создайте магазин
   - Пройдите процедуру идентификации (необходимо для приёма платежей)

2. **Получение ключей API**
   - В личном кабинете перейдите в раздел **Настройки** → **API-ключи**
   - Скопируйте значения:
     - **Shop ID** — идентификатор вашего магазина
     - **Secret Key** — секретный ключ для подписи запросов

3. **Настройка webhook для уведомлений**
   - В личном кабинете YooKassa перейдите в раздел **Настройки** → **Webhook**
   - Добавьте URL для получения уведомлений: https://ваш-домен/webhook/yookassa/
   - YooKassa будет отправлять POST-запросы на этот URL при изменении статуса платежа

4. **Добавление параметров в файл `.env`**
```env
YOOKASSA_SHOP_ID=ваш-shop-id
YOOKASSA_SECRET_KEY=ваш-secret-key
```
#### Важно: Для тестирования используйте тестовые ключи YooKassa. Для приёма реальных платежей необходимо заменить их на боевые и пройти полную идентификацию магазина.

### Настройка Poiskkino.dev API (импорт фильмов)

Poiskkino.dev — это API-сервис для получения информации о фильмах, актёрах, режиссёрах, жанрах и странах. Система использует его для автоматического наполнения базы данных контентом.

1. **Получение API-ключа**
   - Перейдите на сайт [api.poiskkino.dev](https://api.poiskkino.dev/)
   - Зарегистрируйтесь или войдите в существующий аккаунт
   - В личном кабинете перейдите в раздел управления API-ключами
   - Создайте новый API-ключ и скопируйте его

2. **Настройка лимитов запросов**
   - Бесплатный тариф предоставляет 200 запросов в день
   - Для увеличения лимита можно приобрести платный тариф
   - Рекомендуется иметь несколько ключей для ротации

3. **Добавление параметров в файл `.env`**
   ```env
   # Один ключ
   KINOPOISK_API_KEYS=ваш-ключ
   
   # Несколько ключей для ротации (через запятую)
   KINOPOISK_API_KEYS=ключ-1,ключ-2,ключ-3
   ```
4. **Проверка работоспособности**
    ```
   # Тестовый импорт одного фильма
    python manage.py smart_import --pages=1 --year-from=2024 --limit=1
   ```
#### Примечание: При использовании нескольких ключей система автоматически переключается на следующий при исчерпании лимита запросов текущего ключа. Ротация происходит без участия пользователя.

### Настройка SMTP-сервера (отправка писем)

Для отправки уведомлений, кодов подтверждения и билетов на электронную почту необходимо настроить SMTP-сервер. Система использует email для следующих целей:
- Подтверждение регистрации (6-значный код)
- Восстановление пароля (6-значный код)
- Смена email (подтверждение)
- Отправка PDF-билетов после покупки
- Отправка чеков об оплате
- Приветственные письма

1. **Настройка почтового ящика**
   - Зарегистрируйте почтовый ящик на Яндексе (например, `noreply@yandex.ru`)
   - Войдите в почту и перейдите в **Настройки** → **Все настройки**
   - В разделе **Почтовые программы** включите опцию **Доступ по протоколу IMAP**
   - Сохраните изменения

2. **Создание пароля приложения**
   - Перейдите в раздел **Безопасность**
   - Включите **Двухфакторную аутентификацию** (если ещё не включена)
   - В разделе **Пароли приложений** нажмите **Создать новый пароль**
   - Укажите название приложения (например, "Кинотеатр")
   - Скопируйте сгенерированный пароль (он будет показан только один раз)

3. **Добавление параметров в файл `.env`**
   ```env
   EMAIL_HOST_USER=ваш-логин@yandex.ru
   EMAIL_HOST_PASSWORD=пароль-приложения
   ```
   
Для проверки корректности настроек выполните команду:
```bash
# Отправка тестового письма
python manage.py sendtestemail admin@example.com
```

---

## 🚀 Установка на продакшен-сервер

### Подготовка сервера

Подключитесь к серверу по SSH и выполните базовую настройку:

```bash
# Подключение к серверу
ssh root@IP-адрес-сервера

# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
sudo apt install -y python3.12 python3.12-venv python3.12-dev \
  postgresql-16 nginx git supervisor certbot python3-certbot-nginx
```

### Клонирование проекта

```bash
# Создание директории для веб-приложений
sudo mkdir -p /var/www
cd /var/www

# Клонирование репозитория
sudo git clone https://github.com/Klevchik1/Diplom.git cinema
cd cinema
```

### Настройка виртуального окружения

```bash
# Создание виртуального окружения
sudo python3.12 -m venv venv

# Назначение прав на директорию
sudo chown -R www-data:www-data /var/www/cinema

# Активация окружения
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### Создание файла .env.production

```bash
sudo nano /var/www/cinema/.env.production
```

Содержимое файла `.env.production`:

```env
# Django
DJANGO_ENVIRONMENT=production
SECRET_KEY=ваш-секретный-ключ-замените-на-свой
DEBUG=False
ALLOWED_HOSTS=ваш-домен.ru,www.ваш-домен.ru,IP-адрес-сервера,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://ваш-домен.ru,https://www.ваш-домен.ru

# База данных
DB_NAME=cinema_db
DB_USER=cinema_user
DB_PASSWORD=ваш-надёжный-пароль
DB_HOST=localhost
DB_PORT=5432

# API токены
KINOPOISK_API_KEYS=ваш-токен

# Email
EMAIL_HOST_USER=ваш-email@yandex.ru
EMAIL_HOST_PASSWORD=пароль-приложения

# YooKassa
YOOKASSA_SHOP_ID=ваш-shop-id
YOOKASSA_SECRET_KEY=ваш-secret-key

# SSL
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Применение миграций и сбор статики

```bash
# Применение миграций
sudo python manage.py migrate --settings=cinematic.settings.production

# Сбор статических файлов
sudo python manage.py collectstatic --noinput --settings=cinematic.settings.production

# Создание суперпользователя
sudo python manage.py createsuperuser_custom --settings=cinematic.settings.production
```

### Создание директорий для логов и сокетов

```bash
# Создание директорий
sudo mkdir -p /var/www/cinema/logs /var/www/cinema/run

# Назначение прав
sudo chown -R www-data:www-data /var/www/cinema/logs /var/www/cinema/run
sudo chmod -R 755 /var/www/cinema/logs /var/www/cinema/run
```

---

## 🌐 Настройка веб-сервера Nginx

### Создание конфигурационного файла

```bash
sudo nano /etc/nginx/sites-available/cinema
```

```nginx
server {
    listen 80;
    server_name ваш-домен.ru www.ваш-домен.ru;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /var/www/cinema;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        root /var/www/cinema;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/cinema/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    access_log /var/www/cinema/logs/nginx-access.log;
    error_log /var/www/cinema/logs/nginx-error.log;
}
```

### Активация конфигурации

```bash
# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/cinema /etc/nginx/sites-enabled/

# Проверка синтаксиса конфигурации
sudo nginx -t

# Перезагрузка Nginx
sudo systemctl reload nginx
```

---

## ⚡ Настройка Gunicorn и Supervisor

### Создание конфигурации Gunicorn

```bash
sudo nano /var/www/cinema/gunicorn_config.py
```

```python
bind = "unix:/var/www/cinema/run/gunicorn.sock"
workers = 3
worker_class = "sync"
timeout = 120
keepalive = 5
pidfile = "/var/www/cinema/run/gunicorn.pid"
accesslog = "/var/www/cinema/logs/gunicorn-access.log"
errorlog = "/var/www/cinema/logs/gunicorn-error.log"
loglevel = "info"
raw_env = ['DJANGO_SETTINGS_MODULE=cinematic.settings.production']
```

### Настройка Supervisor

```bash
sudo nano /etc/supervisor/conf.d/cinema.conf
```

```ini
[program:cinema]
command=/var/www/cinema/venv/bin/gunicorn -c /var/www/cinema/gunicorn_config.py cinematic.wsgi:application
directory=/var/www/cinema
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/cinema/logs/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
```

### Запуск и управление

```bash
# Обновление конфигурации
sudo supervisorctl reread
sudo supervisorctl update

# Запуск приложения
sudo supervisorctl start cinema

# Проверка статуса
sudo supervisorctl status cinema

# Перезапуск приложения
sudo supervisorctl restart cinema

# Просмотр логов
sudo supervisorctl tail cinema
```

---

## 🛡️ Настройка SSL-сертификата

### Получение сертификата Let's Encrypt

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение и установка сертификата
sudo certbot --nginx -d ваш-домен.ru -d www.ваш-домен.ru

# Проверка автоматического обновления
sudo certbot renew --dry-run
```

### Автоматическое обновление сертификатов

Сертификаты Let's Encrypt действительны 90 дней. Для автоматического обновления добавьте задачу в crontab:

```bash
sudo crontab -e
```

Добавьте строку:
```
0 3 * * * /usr/bin/certbot renew --quiet
```

---

## 🔄 Настройка автоматического деплоя

### Создание скрипта деплоя

```bash
sudo nano /var/www/cinema/deploy.sh
```

```bash
#!/bin/bash
echo "🚀 Деплой на сервер..."

cd /var/www/cinema
source venv/bin/activate

# Обновление кода
git pull origin main

# Установка новых зависимостей
pip install -r requirements.txt

# Применение миграций
python manage.py migrate --noinput --settings=cinematic.settings.production

# Сбор статики
python manage.py collectstatic --noinput --settings=cinematic.settings.production

# Перезапуск приложения
sudo supervisorctl restart cinema

echo "✅ Деплой завершен!"
```

```bash
# Назначение прав на выполнение
sudo chmod +x /var/www/cinema/deploy.sh
```

### Использование деплой-скрипта

```bash
# Ручной запуск
cd /var/www/cinema && ./deploy.sh
```

---

## 🔧 Устранение неполадок

### Общие проблемы

#### Проблемы с правами доступа

```bash
# Исправление прав на все файлы проекта
sudo chown -R www-data:www-data /var/www/cinema
sudo chmod -R 755 /var/www/cinema
sudo chmod -R 775 /var/www/cinema/logs /var/www/cinema/run
```

#### Проблемы с базой данных

```bash
# Проверка статуса PostgreSQL
sudo systemctl status postgresql

# Проверка подключения к БД
sudo -u postgres psql -d cinema_db -c "SELECT 1;"

# Просмотр логов PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-16-main.log

# Восстановление БД из дампа
sudo -u postgres psql -d cinema_db < /backup/cinema_db_20260101.sql
```

#### Проблемы с Gunicorn

```bash
# Проверка логов Gunicorn
sudo tail -f /var/www/cinema/logs/gunicorn-error.log

# Проверка статуса Supervisor
sudo supervisorctl status

# Перезапуск приложения
sudo supervisorctl restart cinema

# Проверка существования сокета
sudo ls -la /var/www/cinema/run/gunicorn.sock
```

#### Проблемы с Nginx

```bash
# Проверка синтаксиса конфигурации
sudo nginx -t

# Перезагрузка Nginx
sudo systemctl reload nginx

# Просмотр логов Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/www/cinema/logs/nginx-error.log
```

#### Проблемы с отправкой писем

```bash
# Проверка SMTP-настроек
python manage.py sendtestemail admin@example.com

# Просмотр логов отправки
tail -f /var/www/cinema/logs/django.log | grep -i email
```

### Проверка работоспособности

```bash
# Проверка доступности сайта
curl -I http://localhost
curl -I https://ваш-домен.ru

# Проверка Gunicorn сокета
sudo ls -la /var/www/cinema/run/gunicorn.sock

# Проверка логов приложения в реальном времени
sudo tail -f /var/www/cinema/logs/django.log
```

---

## 📋 Полезные команды

### Управление приложением

```bash
# Перезапуск всех сервисов
sudo supervisorctl restart cinema && sudo systemctl reload nginx

# Просмотр всех логов в реальном времени
sudo tail -f /var/www/cinema/logs/*.log

# Полное обновление приложения
cd /var/www/cinema && ./deploy.sh
```

### Резервное копирование и восстановление

```bash
# Создание дампа базы данных
sudo -u postgres pg_dump cinema_db > /backup/cinema_db_$(date +%Y%m%d).sql

# Создание дампа с сжатием
sudo -u postgres pg_dump cinema_db | gzip > /backup/cinema_db_$(date +%Y%m%d).sql.gz

# Восстановление базы данных
sudo -u postgres psql -d cinema_db < /backup/cinema_db_20260101.sql

# Восстановление из сжатого дампа
gunzip -c /backup/cinema_db_20260101.sql.gz | sudo -u postgres psql -d cinema_db
```

### Мониторинг

```bash
# Просмотр использования ресурсов
htop

# Просмотр логов в реальном времени
sudo journalctl -u nginx -f
sudo journalctl -u postgresql -f
sudo supervisorctl tail -f cinema

# Проверка доступности сайта
curl -I https://ваш-домен.ru
```

---

> **Примечание:** Данное руководство предполагает, что вы имеете базовые навыки работы с командной строкой Linux. При возникновении проблем обращайтесь к официальной документации используемых технологий или создавайте Issue в репозитории проекта.