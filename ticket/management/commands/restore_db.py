import os
import subprocess
import sys
from datetime import timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ticket.models import BackupManager


class Command(BaseCommand):
    help = 'Restore database from a backup file'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_id',
            type=int,
            help='ID of the backup to restore from'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def execute_sql_file(self, sql_file_path):
        """Выполнить SQL файл с правильной кодировкой"""
        db_settings = settings.DATABASES['default']

        cmd = [
            'psql',
            '-h', db_settings.get('HOST', 'localhost'),
            '-p', str(db_settings.get('PORT', 5432)),
            '-U', db_settings['USER'],
            '-d', db_settings['NAME'],
            '-f', sql_file_path,
            '-v', 'ON_ERROR_STOP=on'
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_settings['PASSWORD']

        # Настройка кодировки для Windows
        if os.name == 'nt':
            env['PGCLIENTENCODING'] = 'UTF8'
            env['CHCP'] = '65001'  # UTF-8 code page

        try:
            # Пытаемся выполнить с UTF-8
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
        except UnicodeDecodeError:
            # Если UTF-8 не работает, пробуем Windows-1251
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding='cp1251',
                errors='replace'
            )

        return result

    def handle(self, *args, **options):
        backup_id = options['backup_id']
        confirm = options.get('confirm', False)

        try:
            backup = BackupManager.objects.get(id=backup_id)
        except BackupManager.DoesNotExist:
            raise CommandError(f'Backup with ID {backup_id} not found')

        if not backup.file_exists():
            raise CommandError(f'Backup file not found: {backup.backup_file}')

        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('⚠️  ВНИМАНИЕ: ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ'))
        self.stdout.write(self.style.WARNING('=' * 70))

        self.stdout.write(f'📁 Бэкап: {backup.name}')
        self.stdout.write(f'📄 Файл: {backup.backup_file}')
        self.stdout.write(f'📊 Тип: {backup.get_backup_type_display()}')
        self.stdout.write(f'📅 Дата бэкапа: {backup.backup_date}')
        self.stdout.write(f'💾 Размер файла: {backup.file_size()}')
        self.stdout.write('')

        self.stdout.write(f'🎯 Целевая БД: {settings.DATABASES["default"]["NAME"]}')
        self.stdout.write('')

        if not confirm:
            confirm_input = input(
                '❓ Вы уверены, что хотите восстановить БД? Все текущие данные будут потеряны! (yes/no): ')
            if confirm_input.lower() != 'yes':
                self.stdout.write(self.style.ERROR('❌ Восстановление отменено'))
                return

        self.stdout.write(self.style.WARNING('🔄 Начало восстановления...'))

        # Получаем полный путь к файлу
        backup_path = backup.get_file_path()

        # Проверяем кодировку файла
        try:
            with open(backup_path, 'rb') as f:
                raw_data = f.read(1000)
                # Пытаемся определить кодировку
                try:
                    raw_data.decode('utf-8')
                    self.stdout.write('🔤 Кодировка файла: UTF-8')
                except UnicodeDecodeError:
                    self.stdout.write('🔤 Кодировка файла: Windows-1251 (предположительно)')
        except Exception as e:
            self.stdout.write(f'⚠️  Не удалось определить кодировку: {e}')

        # Выполняем восстановление
        result = self.execute_sql_file(backup_path)

        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS('✅ Восстановление успешно завершено!'))
            if result.stdout:
                self.stdout.write(f'📝 Вывод: {result.stdout[:200]}...')

            # Обновляем статус backup
            backup.restoration_status = 'completed'
            backup.restored_at = timezone.now()
            backup.restoration_log = f"Восстановление выполнено через команду\n{result.stdout[:500]}"
            backup.save()

        else:
            self.stdout.write(self.style.ERROR('❌ Ошибка восстановления'))
            self.stdout.write(f'📝 Код ошибки: {result.returncode}')
            if result.stderr:
                self.stdout.write(f'📝 Ошибка: {result.stderr[:500]}')
            if result.stdout:
                self.stdout.write(f'📝 Вывод: {result.stdout[:500]}')

            # Обновляем статус backup
            backup.restoration_status = 'failed'
            backup.restoration_log = f"Ошибка: {result.returncode}\n{result.stderr[:1000]}"
            backup.save()