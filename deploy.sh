#!/bin/bash
# Скрипт для деплоя на сервер

echo "🚀 Деплой на сервер..."

# 1. Пушим изменения на GitHub
git add .
git commit -m "Update: $(date +%Y-%m-%d_%H:%M)" || echo "Нет изменений"
git push origin master

# 2. Заходим на сервер и обновляем
ssh root@168.222.140.166 << 'ENDSSH'
cd /var/www/cinema
source venv/bin/activate

# Получаем изменения
git pull origin main

# Применяем миграции если есть
python manage.py migrate --noinput

# Собираем статику
python manage.py collectstatic --noinput

# Перезапускаем сервисы
supervisorctl restart cinema
systemctl reload nginx

echo "✅ Деплой завершен!"
ENDSSH

echo "✅ Готово! Сайт обновлен: http://168.222.140.166"