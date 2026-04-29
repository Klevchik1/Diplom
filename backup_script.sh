#!/bin/bash
cd /var/www/cinema
source venv/bin/activate
python manage.py backup_db
