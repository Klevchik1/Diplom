// Функции для главной страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Home.js loaded');

    // Устанавливаем минимальную дату как сегодня для фильтров даты
    const today = new Date().toISOString().split('T')[0];

    // Обновляем активную дату в URL при загрузке
    const urlParams = new URLSearchParams(window.location.search);
    const currentDate = urlParams.get('date') || today;
    const selectedDateInput = document.getElementById('selected-date');
    if (selectedDateInput) {
        selectedDateInput.value = currentDate;
    }

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

    // Создаем скрытые поля для сохранения фильтров
    const form = document.getElementById('filter-form');
    if (!form) return;

    // Удаляем старые скрытые поля если есть
    const oldHiddenFields = form.querySelectorAll('input[type="hidden"][name="search"], input[type="hidden"][name="hall"], input[type="hidden"][name="genre"], input[type="hidden"][name="age_rating"]');
    oldHiddenFields.forEach(field => field.remove());

    // Добавляем скрытые поля с текущими значениями фильтров
    if (searchValue) {
        addHiddenField(form, 'search', searchValue);
    }
    if (hallValue) {
        addHiddenField(form, 'hall', hallValue);
    }
    if (genreValue) {
        addHiddenField(form, 'genre', genreValue);
    }
    if (ageRatingValue) {
        addHiddenField(form, 'age_rating', ageRatingValue);
    }

    // Отправляем форму
    form.submit();
}

// Функция для применения фильтров с сохранением даты
function applyFilters() {
    const form = document.getElementById('filter-form');
    if (!form) return;

    const dateValue = document.getElementById('selected-date')?.value || '';

    // Добавляем скрытое поле с датой
    addHiddenField(form, 'date', dateValue);

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
            // Убедимся, что дата сохраняется
            const dateValue = document.getElementById('selected-date')?.value;
            if (dateValue) {
                addHiddenField(this, 'date', dateValue);
            }
        });
    }
}