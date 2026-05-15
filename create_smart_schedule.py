import random
from datetime import datetime, timedelta
from django.utils import timezone
from ticket.models import Movie, Hall, Screening

print("🎬 ГЕНЕРАЦИЯ УМНОГО РАСПИСАНИЯ СЕАНСОВ")
print("=" * 60)

# Удаляем старые сеансы
deleted = Screening.objects.all().delete()
print(f"✅ Удалено старых сеансов: {deleted[0] if deleted else 0}")

# Конфигурация
HALLS = list(Hall.objects.all())
MOVIES = list(Movie.objects.all())
MOVIES_PER_WEEK = 12
DAYS_TO_SCHEDULE = 60

START_HOUR = 8
END_HOUR = 22
INTERVAL_MIN = 45

print(f"🏗️ Залов: {len(HALLS)}")
print(f"🎬 Всего фильмов: {len(MOVIES)}")
print(f"📅 Планируем на {DAYS_TO_SCHEDULE} дней")
print(f"🎯 Фильмов в неделе: {MOVIES_PER_WEEK}")
print("=" * 60)

# Сортируем фильмы по длительности
MOVIES.sort(key=lambda m: m.duration)

# Разбиваем на недельные блоки
weeks = []
for i in range(0, len(MOVIES), MOVIES_PER_WEEK):
    week_movies = MOVIES[i:i + MOVIES_PER_WEEK]
    if week_movies:
        weeks.append(week_movies)

print(f"📆 Недельных блоков: {len(weeks)}")

created = 0
today = timezone.now().date()

for day_offset in range(DAYS_TO_SCHEDULE):
    current_date = today + timedelta(days=day_offset)
    week_index = day_offset // 7
    
    if week_index < len(weeks):
        active_movies = weeks[week_index]
    else:
        active_movies = weeks[-1] if weeks else []
    
    if not active_movies:
        break
    
    # Для каждого зала создаём расписание на день
    for hall in HALLS:
        current_time = datetime(current_date.year, current_date.month, current_date.day, START_HOUR, 0)
        current_time = timezone.make_aware(current_time)
        end_of_day = datetime(current_date.year, current_date.month, current_date.day, END_HOUR, 0)
        end_of_day = timezone.make_aware(end_of_day)
        
        # Копируем список фильмов для этого зала
        hall_movies = active_movies.copy()
        random.shuffle(hall_movies)
        
        while current_time < end_of_day and hall_movies:
            # Берём следующий фильм
            movie = hall_movies.pop(0)
            
            # Определяем количество сеансов для этого фильма в день
            if movie.duration > 150:
                max_per_day = 2
            elif movie.duration > 120:
                max_per_day = 3
            elif movie.duration > 90:
                max_per_day = 4
            else:
                max_per_day = 5
            
            sessions_for_movie = random.randint(2, max_per_day)
            
            for _ in range(sessions_for_movie):
                if current_time >= end_of_day:
                    break
                
                end_time = current_time + timedelta(minutes=movie.duration + INTERVAL_MIN)
                
                # Проверяем, не выходит ли за пределы дня
                if end_time > end_of_day + timedelta(hours=1):
                    current_time += timedelta(minutes=INTERVAL_MIN)
                    continue
                
                # Проверяем пересечение с другими сеансами в этом зале
                conflict = Screening.objects.filter(
                    hall=hall,
                    start_time__lt=end_time,
                    end_time__gt=current_time
                ).exists()
                
                if not conflict:
                    Screening.objects.create(
                        movie=movie,
                        hall=hall,
                        start_time=current_time,
                        end_time=end_time
                    )
                    created += 1
                
                # Переход к следующему временному слоту
                current_time += timedelta(minutes=INTERVAL_MIN)
            
            # Если фильм ещё может показываться в других залах, добавляем обратно в конец
            if sessions_for_movie > 0 and len(hall_movies) < len(active_movies):
                hall_movies.append(movie)
    
    # Прогресс
    if (day_offset + 1) % 7 == 0:
        print(f"  Неделя {(day_offset + 1) // 7}: создано {created} сеансов")

print("\n" + "=" * 60)
print(f"✅ Всего создано сеансов: {created}")
if len(MOVIES) > 0:
    print(f"🎬 Среднее сеансов на фильм: {created / len(MOVIES):.1f}")
print(f"📅 Сеансов в день: {created / DAYS_TO_SCHEDULE:.1f}")
print(f"🏗️ Сеансов на зал в день: {created / DAYS_TO_SCHEDULE / len(HALLS):.1f}")
print("=" * 60)
