import os
import subprocess
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseRestorer:
    """Класс для восстановления базы данных"""

    @staticmethod
    def restore_from_backup(backup_path):
        """Восстановить БД из файла backup"""
        db_settings = settings.DATABASES['default']

        # Команда восстановления
        cmd = [
            'psql',
            '-h', db_settings.get('HOST', 'localhost'),
            '-p', str(db_settings.get('PORT', '5432')),
                                              '-U', db_settings['USER'],
                                      '-d', db_settings['NAME'],
                                      '-f', backup_path
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']

        # Настройки для Windows
        if os.name == 'nt':
            env['PGCLIENTENCODING'] = 'UTF8'
        # Используем правильный набор символов для Windows
        import locale
        try:
            # Пытаемся установить UTF-8 для Windows
            os.system('chcp 65001 > nul')
        except:
            pass

        try:
            # Выполняем команду
            logger.info(f"Выполняем восстановление из файла: {backup_path}")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=True  # Используем shell для Windows
            )

            logger.info(f"Код возврата: {result.returncode}")
            if result.stdout:
                logger.info(f"Вывод: {result.stdout[:500]}")
            if result.stderr:
                logger.error(f"Ошибка: {result.stderr[:500]}")

            return result.returncode == 0, result.stdout, result.stderr

        except Exception as e:
            logger.error(f"Исключение при восстановлении: {e}")
            return False, "", str(e)

    @staticmethod
    def test_psql_connection():
        """Протестировать подключение к PostgreSQL"""
        db_settings = settings.DATABASES['default']

        cmd = [
            'psql',
            '-h', db_settings.get('HOST', 'localhost'),
            '-p', str(db_settings.get('PORT', 5432)),
            '-U', db_settings['USER'],
            '-d', db_settings['NAME'],
            '-c', 'SELECT 1;'
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                shell=True
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)