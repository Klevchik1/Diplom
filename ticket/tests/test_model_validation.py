"""
FUNC-NEG-3-тест-валидации
Тест с намеренными ошибками валидации моделей
"""
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from ticket.models import User, Movie, Hall, Screening, Genre, AgeRating


class ModelValidationNegativeTest(TestCase):
    """Тест с намеренными ошибками валидации (ожидается провал)"""

    def setUp(self):
        """Настройка тестовых данных"""
        print("\nНастройка тестовых данных для тестов валидации...")

        # Создаем базовые объекты
        self.genre = Genre.objects.create(name='Тестовый жанр')
        self.age_rating = AgeRating.objects.create(name='12+', description='Тест')
        self.hall = Hall.objects.create(name='Тестовый зал', rows=5, seats_per_row=10)
        self.movie = Movie.objects.create(
            title='Тестовый фильм',
            description='Описание',
            duration=timedelta(hours=2),
            genre=self.genre,
            age_rating=self.age_rating
        )

    def test_func_neg_3_intentional_validation_failures(self):
        """FUNC-NEG-3: Тест с намеренными ошибками валидации (ожидается провал)"""
        print("\n" + "=" * 60)
        print("FUNC-NEG-3-тест-валидации")
        print("Тест: Намеренные ошибки валидации моделей")
        print("ОЖИДАЕТСЯ: несколько проверок должны провалиться")
        print("=" * 60)

        failures = []
        passed = []

        # Шаг 1: Создание пользователя с некорректным email
        print("\n1. Попытка создания пользователя с некорректным email...")
        try:
            user = User(
                email='некорректный-email',  # Неправильный формат
                name='Тест',
                surname='Тестов',
                number='+79123456789'
            )
            user.full_clean()  # Должно вызвать ValidationError
            failures.append("✓ НЕПРАВИЛЬНО: Некорректный email принят")
        except ValidationError as e:
            if 'email' in str(e):
                passed.append("✓ ПРАВИЛЬНО: Некорректный email отклонен")
            else:
                failures.append(f"⚠ Неожиданная ошибка: {e}")

        # Шаг 2: Создание пользователя с существующим email
        print("\n2. Попытка создания пользователя с существующим email...")
        User.objects.create_user(
            email='duplicate@example.com',
            password='test123',
            name='Первый',
            surname='Пользователь',
            number='+79123456780'
        )

        try:
            user2 = User(
                email='duplicate@example.com',  # Дубликат
                name='Второй',
                surname='Пользователь',
                number='+79123456781'
            )
            user2.save()  # Должно вызвать ошибку
            failures.append("✓ НЕПРАВИЛЬНО: Дубликат email принят")
        except Exception as e:
            if 'уже существует' in str(e):
                passed.append("✓ ПРАВИЛЬНО: Дубликат email отклонен")
            else:
                failures.append(f"⚠ Неожиданная ошибка: {e}")

        # Шаг 3: Создание фильма без обязательных полей
        print("\n3. Попытка создания фильма без обязательных полей...")
        try:
            movie = Movie()  # Все поля пустые
            movie.full_clean()
            failures.append("✓ НЕПРАВИЛЬНО: Фильм без данных принят")
        except ValidationError as e:
            error_fields = list(e.message_dict.keys())
            required_fields = ['title', 'description', 'duration', 'genre', 'age_rating']
            missing_fields = [f for f in required_fields if f in error_fields]

            if len(missing_fields) >= 3:  # Хотя бы 3 обязательных поля
                passed.append("✓ ПРАВИЛЬНО: Обязательные поля проверяются")
            else:
                failures.append(f"⚠ Проверка обязательных полей недостаточна: {error_fields}")

        # Шаг 4: Создание сеанса с пересечением времени
        print("\n4. Попытка создания пересекающихся сеансов...")
        try:
            # Первый сеанс
            screening1 = Screening.objects.create(
                movie=self.movie,
                hall=self.hall,
                start_time=timezone.now() + timedelta(hours=2),
                price=500.00
            )

            # Второй сеанс, пересекающийся с первым
            screening2 = Screening(
                movie=self.movie,
                hall=self.hall,
                start_time=timezone.now() + timedelta(hours=2, minutes=30),  # Пересекается
                price=600.00
            )
            screening2.clean()  # Должно вызвать ValidationError
            screening2.save()

            failures.append("✓ НЕПРАВИЛЬНО: Пересекающиеся сеансы приняты")

        except ValidationError as e:
            if 'пересекается' in str(e).lower() or 'пересекается' in str(e):
                passed.append("✓ ПРАВИЛЬНО: Пересекающиеся сеансы отклонены")
            else:
                failures.append(f"⚠ Неожиданная ошибка пересечения: {e}")
        except Exception as e:
            failures.append(f"⚠ Исключение при создании сеанса: {e}")

        # Шаг 5: Создание сеанса в нерабочее время
        print("\n5. Попытка создания сеанса в нерабочее время...")
        try:
            # Пытаемся создать сеанс в 3:00 ночи
            night_time = timezone.now().replace(hour=3, minute=0, second=0, microsecond=0)
            if night_time < timezone.now():
                night_time += timedelta(days=1)

            screening = Screening(
                movie=self.movie,
                hall=self.hall,
                start_time=night_time,  # 3:00 ночи
                price=400.00
            )
            screening.clean()  # Должно вызвать ValidationError

            failures.append("✓ НЕПРАВИЛЬНО: Сеанс в нерабочее время принят")

        except ValidationError as e:
            if '8:00' in str(e) or '23:00' in str(e) or 'рабочее' in str(e).lower():
                passed.append("✓ ПРАВИЛЬНО: Сеанс в нерабочее время отклонен")
            else:
                failures.append(f"⚠ Неожиданная ошибка времени: {e}")
        except Exception as e:
            failures.append(f"⚠ Исключение при проверке времени: {e}")

        # Шаг 6: Создание жанра с дублирующимся именем
        print("\n6. Попытка создания дублирующего жанра...")
        try:
            genre2 = Genre(name='Тестовый жанр')  # То же имя
            genre2.save()
            failures.append("✓ НЕПРАВИЛЬНО: Дублирующий жанр создан")
        except ValidationError as e:
            if 'уже существует' in str(e):
                passed.append("✓ ПРАВИЛЬНО: Дублирующий жанр отклонен")
            else:
                failures.append(f"⚠ Неожиданная ошибка дублирования: {e}")
        except Exception as e:
            failures.append(f"⚠ Исключение при создании жанра: {e}")

        # Шаг 7: Создание зала с некорректным количеством мест
        print("\n7. Попытка создания зала с некорректными параметрами...")
        try:
            hall = Hall(name='Некорректный зал', rows=0, seats_per_row=0)  # Нулевые значения
            hall.full_clean()
            failures.append("✓ НЕПРАВИЛЬНО: Зал с 0 мест принят")
        except ValidationError as e:
            if 'rows' in str(e) or 'seats_per_row' in str(e):
                passed.append("✓ ПРАВИЛЬНО: Некорректный зал отклонен")
            else:
                failures.append(f"⚠ Неожиданная ошибка зала: {e}")
        except Exception as e:
            failures.append(f"⚠ Исключение при создании зала: {e}")

        # Итоги
        print("\n" + "=" * 60)
        print("ИТОГИ ТЕСТА ВАЛИДАЦИИ:")
        print("=" * 60)

        if passed:
            print("\nУСПЕШНЫЕ ПРОВЕРКИ (ожидаемое поведение):")
            for p in passed:
                print(f"  {p}")

        if failures:
            print("\nНЕУДАЧНЫЕ ПРОВЕРКИ (неожиданное поведение):")
            for f in failures:
                print(f"  {f}")

        total_tests = len(passed) + len(failures)
        print(f"\nВсего проверок: {total_tests}")
        print(f"Успешно: {len(passed)}")
        print(f"Неудачно: {len(failures)}")

        # Этот тест НАМЕРЕННО должен иметь неудачные проверки
        # Это демонстрирует работу системы валидации
        if len(failures) > 0:
            print("\n" + "=" * 60)
            print("РЕЗУЛЬТАТ: ТЕСТ ПРОВАЛЕН ❌ (ожидаемо)")
            print("Некоторые проверки валидации не сработали как ожидалось")
            print("Это демонстрирует граничные случаи системы")
            print("=" * 60)

            # Намеренно вызываем assert для провала теста
            self.fail(f"Намеренный провал теста: {len(failures)} проверок не прошли")
        else:
            print("\n" + "=" * 60)
            print("РЕЗУЛЬТАТ: ТЕСТ ПРОЙДЕН ✅ (неожиданно)")
            print("Все проверки валидации прошли успешно")
            print("Система валидации работает идеально")
            print("=" * 60)