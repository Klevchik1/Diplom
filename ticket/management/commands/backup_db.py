import os
import subprocess
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from ticket.models import BackupManager


class Command(BaseCommand):
    help = 'Create professional database backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Create backup for specific date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--simple',
            action='store_true',
            help='Create simple backup instead of full'
        )

    def handle(self, *args, **options):
        backup_date = options.get('date')
        simple_mode = options.get('simple')

        # Директория для бэкапов
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Создаем имя файла
        if backup_date:
            filename = f"backup_{backup_date}.sql"
            backup_type = 'daily'
            name = f"Дневной бэкап {backup_date}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"full_backup_{timestamp}.sql"
            backup_type = 'full'
            name = f"Полный бэкап {timestamp}"

        backup_path = os.path.join(backup_dir, filename)

        self.stdout.write(f"🔄 Создание {backup_type} бэкапа...")

        try:
            if simple_mode:
                success = self.create_simple_backup(backup_path)
            else:
                success = self.create_pro_backup(backup_path)

            if success:
                # Создаем запись в БД
                from django.utils.dateparse import parse_date

                backup = BackupManager.objects.create(
                    name=name,
                    backup_file=filename,
                    backup_type=backup_type,
                    backup_date=parse_date(backup_date) if backup_date else None
                )

                file_size = os.path.getsize(backup_path)
                size_mb = file_size / 1024 / 1024

                if size_mb > 1:
                    size_str = f"{size_mb:.2f} MB"
                else:
                    size_str = f"{file_size / 1024:.1f} KB"

                self.stdout.write(
                    self.style.SUCCESS(f'✅ Бэкап создан: {filename}')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'📊 Размер: {size_str}')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'📝 ID записи: {backup.id}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Не удалось создать бэкап')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {str(e)}')
            )

    def create_pro_backup(self, backup_path):
        """Создает профессиональный бэкап всей БД"""
        try:
            db_config = settings.DATABASES['default']

            # Команда для создания бэкапа
            cmd = [
                'pg_dump',
                '-h', db_config.get('HOST', 'localhost'),
                '-p', str(db_config.get('PORT', '5432')),
                '-U', db_config['USER'],
                '-d', db_config['NAME'],
                '-f', backup_path,
                '--verbose',
                '--no-owner',
                '--no-privileges',
                '--clean',
                '--if-exists',
                '--encoding=UTF8',
                '--schema=public'
            ]

            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['PASSWORD']

            # Для Windows
            if os.name == 'nt':
                env['PGCLIENTENCODING'] = 'UTF8'

            self.stdout.write(f"🔧 Выполняю pg_dump...")

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                self.stdout.write("✅ pg_dump выполнен успешно")
                return True
            else:
                self.stdout.write(f"❌ pg_dump ошибка: {result.returncode}")
                # Пробуем без pg_dump
                return self.create_manual_backup(backup_path)

        except FileNotFoundError:
            self.stdout.write("⚠️ pg_dump не найден, создаю ручной бэкап...")
            return self.create_manual_backup(backup_path)
        except Exception as e:
            self.stdout.write(f"⚠️ Ошибка pg_dump: {e}, создаю ручной бэкап...")
            return self.create_manual_backup(backup_path)

    def create_manual_backup(self, backup_path):
        """Создает ручной бэкап без pg_dump"""
        try:
            import psycopg2
            from psycopg2 import sql

            self.stdout.write("🛠️ Создание ручного бэкапа...")

            db_config = settings.DATABASES['default']

            # Подключаемся к БД
            conn = psycopg2.connect(
                host=db_config.get('HOST', 'localhost'),
                database=db_config['NAME'],
                user=db_config['USER'],
                password=db_config['PASSWORD'],
                port=db_config.get('PORT', '5432')
            )

            cur = conn.cursor()

            # Получаем все таблицы
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            with open(backup_path, 'w', encoding='utf-8') as f:
                # Заголовок
                f.write("-- PostgreSQL Database Backup\n")
                f.write(f"-- Generated: {datetime.now()}\n")
                f.write(f"-- Database: {db_config['NAME']}\n")
                f.write(f"-- Total tables: {len(tables)}\n\n")

                f.write("BEGIN;\n\n")

                # Для каждой таблицы
                for table in tables:
                    self.stdout.write(f"📝 Таблица: {table}")

                    # Получаем структуру таблицы
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns 
                        WHERE table_name = %s AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """, (table,))

                    columns = cur.fetchall()

                    # Создаем DROP и CREATE
                    f.write(f"\n-- Table: {table}\n")
                    f.write(f"DROP TABLE IF EXISTS {table} CASCADE;\n")

                    f.write(f"CREATE TABLE {table} (\n")

                    col_defs = []
                    for col in columns:
                        col_name, data_type, is_nullable, col_default = col

                        # Определяем тип данных
                        if data_type.startswith('character varying'):
                            size = data_type.split('(')[1].split(')')[0]
                            type_str = f"VARCHAR({size})"
                        elif data_type == 'text':
                            type_str = "TEXT"
                        elif data_type == 'integer':
                            type_str = "INTEGER"
                        elif data_type == 'bigint':
                            type_str = "BIGINT"
                        elif data_type.startswith('numeric'):
                            type_str = data_type.upper()
                        elif data_type == 'boolean':
                            type_str = "BOOLEAN"
                        elif data_type.startswith('timestamp'):
                            type_str = "TIMESTAMP"
                        elif data_type == 'date':
                            type_str = "DATE"
                        elif data_type.startswith('double precision'):
                            type_str = "DOUBLE PRECISION"
                        elif data_type.startswith('json'):
                            type_str = "JSONB"
                        else:
                            type_str = data_type.upper()

                        # NULL/NOT NULL
                        null_str = " NOT NULL" if is_nullable == 'NO' else ""

                        # DEFAULT
                        default_str = ""
                        if col_default:
                            if 'nextval' in col_default:
                                # Это serial/sequence
                                default_str = f" DEFAULT {col_default}"
                            else:
                                default_str = f" DEFAULT {col_default}"

                        col_defs.append(f"  {col_name} {type_str}{null_str}{default_str}")

                    f.write(",\n".join(col_defs))
                    f.write("\n);\n\n")

                    # Получаем данные
                    cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
                    rows = cur.fetchall()

                    if rows:
                        f.write(f"-- Data for {table} ({len(rows)} rows)\n")
                        f.write(f"INSERT INTO {table} VALUES\n")

                        row_strings = []
                        for row in rows:
                            values = []
                            for value in row:
                                if value is None:
                                    values.append("NULL")
                                elif isinstance(value, str):
                                    # Экранирование
                                    escaped = value.replace("'", "''").replace("\\", "\\\\")
                                    values.append(f"'{escaped}'")
                                elif isinstance(value, bool):
                                    values.append("TRUE" if value else "FALSE")
                                elif isinstance(value, (int, float)):
                                    values.append(str(value))
                                elif isinstance(value, datetime):
                                    values.append(f"'{value.isoformat()}'")
                                elif isinstance(value, bytes):
                                    # Для bytea
                                    values.append(f"'\\\\x{value.hex()}'")
                                else:
                                    values.append(f"'{str(value)}'")

                            row_strings.append(f"({', '.join(values)})")

                        # Записываем группами по 100
                        for i in range(0, len(row_strings), 100):
                            chunk = row_strings[i:i + 100]
                            if i > 0:
                                f.write(",\n")
                            f.write(",\n".join(chunk))

                        f.write(";\n\n")

                    # Получаем индексы
                    cur.execute("""
                        SELECT indexname, indexdef 
                        FROM pg_indexes 
                        WHERE tablename = %s AND schemaname = 'public'
                    """, (table,))

                    indexes = cur.fetchall()
                    if indexes:
                        f.write(f"-- Indexes for {table}\n")
                        for index_name, index_def in indexes:
                            if 'pkey' not in index_name.lower():  # Пропускаем первичные ключи (они уже в CREATE)
                                f.write(f"{index_def};\n")
                        f.write("\n")

                # Sequences
                f.write("\n-- Sequences\n")
                cur.execute("""
                    SELECT sequence_name 
                    FROM information_schema.sequences 
                    WHERE sequence_schema = 'public'
                """)
                sequences = [row[0] for row in cur.fetchall()]

                for seq in sequences:
                    cur.execute(f"SELECT last_value FROM {seq}")
                    last_val = cur.fetchone()[0]
                    f.write(f"ALTER SEQUENCE {seq} RESTART WITH {last_val + 1};\n")

                f.write("\nCOMMIT;\n")
                f.write("\n-- Backup completed successfully --\n")

            cur.close()
            conn.close()

            self.stdout.write("✅ Ручной бэкап создан успешно")
            return True

        except Exception as e:
            self.stdout.write(f"❌ Ошибка ручного бэкапа: {str(e)}")
            import traceback
            self.stdout.write(f"📋 Трассировка: {traceback.format_exc()[:500]}")
            return False

    def create_simple_backup(self, backup_path):
        """Создает минимальный бэкап"""
        try:
            self.stdout.write("📄 Создание минимального бэкапа...")

            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(f"-- Minimal Database Backup\n")
                f.write(f"-- Generated: {datetime.now()}\n")
                f.write(f"-- WARNING: This is a minimal backup for emergency use only\n\n")
                f.write("SELECT 'Minimal backup created' as status;\n")

            return True

        except Exception as e:
            self.stdout.write(f"❌ Ошибка минимального бэкапа: {str(e)}")
            return False