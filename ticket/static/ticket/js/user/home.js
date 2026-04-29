// Функции для главной страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Home.js loaded');

    // Устанавливаем минимальную дату как сегодня для фильтров даты
    const today = new Date().toISOString().split('T')[0];

    // ИЗМЕНЕНИЕ: Не обновляем дату из URL при загрузке
    // Всегда используем сегодня по умолчанию

    // Инициализируем обработчики для формы
    initFilterForm();
});

// Функция выбора даты
function selectDate(date) {
    // Сохраняем текущие значения фильтров
    const searchValue = document.getElementById('search')?.value || '';
    const hallValue = document.getElementById('hall')?.value || '';
    const genreValue = document.getElementById('genre')?.value || '';
    const ageRatingValue = document.getElementById('age_rating')?.value || '';

    // Устанавливаем выбранную дату
    const selectedDateInput = document.getElementById('selected-date');
    if (selectedDateInput) {
        selectedDateInput.value = date;
    }

    const form = document.getElementById('filter-form');
    if (!form) return;

    // ИЗМЕНЕНИЕ: Не добавляем скрытые поля - они уже есть в форме

    // Обновляем URL без параметра date (чтобы при обновлении не сохранялась дата)
    const url = new URL(window.location);
    url.searchParams.set('date', date);
    window.history.pushState({}, '', url);

    // Отправляем форму
    form.submit();
}

// Функция для применения фильтров с сохранением даты
function applyFilters() {
    const form = document.getElementById('filter-form');
    if (!form) return;

    // ИЗМЕНЕНИЕ: Не добавляем скрытое поле с датой, так как оно уже есть в форме

    form.submit();
}

// Вспомогательная функция для добавления скрытого поля
function addHiddenField(form, name, value) {
    const hiddenField = document.createElement('input');
    hiddenField.type = 'hidden';
    hiddenField.name = name;
    hiddenField.value = value;
    form.appendChild(hiddenField);
}

// Инициализация формы фильтров
function initFilterForm() {
    const applyButton = document.querySelector('.btn-apply');
    if (applyButton) {
        applyButton.addEventListener('click', function(e) {
            e.preventDefault();
            applyFilters();
        });
    }

    // Обработчик для формы (на случай отправки через Enter)
    const form = document.getElementById('filter-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // ИЗМЕНЕНИЕ: Убеждаемся, что дата передается правильно
            const dateValue = document.getElementById('selected-date')?.value;
            const dateInput = this.querySelector('input[name="date"]');
            if (dateInput && dateValue) {
                dateInput.value = dateValue;
            }
        });
    }
}