// Улучшенная форма для фильмов с быстрым добавлением режиссёров и актёров

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация select2 для красивого выбора
    initSelect2();

    // Обработчики для модальных окон
    initModalHandlers();

    // Предпросмотр изображения
    initImagePreview();
});

function initSelect2() {
    // Подключаем Select2 для красивого выбора с поиском
    if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
        $('#id_directors, #id_actors').select2({
            width: '100%',
            placeholder: 'Выберите из списка',
            allowClear: true,
            language: {
                noResults: function() {
                    return "Ничего не найдено";
                },
                searching: function() {
                    return "Поиск...";
                }
            }
        });
    } else {
        // Если Select2 не подключен, просто увеличиваем размер поля
        const directorsField = document.getElementById('id_directors');
        const actorsField = document.getElementById('id_actors');

        if (directorsField) directorsField.size = 8;
        if (actorsField) actorsField.size = 8;
    }
}

function initModalHandlers() {
    // Кнопки "Быстрое добавление"
    const addDirectorBtn = document.getElementById('quick-add-director');
    const addActorBtn = document.getElementById('quick-add-actor');

    if (addDirectorBtn) {
        addDirectorBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openQuickAddModal('director');
        });
    }

    if (addActorBtn) {
        addActorBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openQuickAddModal('actor');
        });
    }

    // Закрытие модальных окон
    const closeButtons = document.querySelectorAll('.modal-close, .modal-cancel');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            closeModal();
        });
    });

    // Клик вне модального окна
    window.addEventListener('click', function(e) {
        const modal = document.getElementById('quick-add-modal');
        if (e.target === modal) {
            closeModal();
        }
    });
}

function openQuickAddModal(type) {
    // Удаляем существующее модальное окно, если есть
    const existingModal = document.getElementById('quick-add-modal');
    if (existingModal) {
        existingModal.remove();
    }

    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.id = 'quick-add-modal';
    modal.className = 'modal';

    const title = type === 'director' ? 'Быстрое добавление режиссёра' : 'Быстрое добавление актёра';
    const apiUrl = type === 'director' ? '/manager/api/quick-add-director/' : '/manager/api/quick-add-actor/';

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <form id="quick-add-form" data-type="${type}" data-url="${apiUrl}">
                    <div class="form-group">
                        <label for="modal-name">Имя *</label>
                        <input type="text" id="modal-name" name="name" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label for="modal-surname">Фамилия *</label>
                        <input type="text" id="modal-surname" name="surname" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label for="modal-birth_date">Дата рождения</label>
                        <input type="date" id="modal-birth_date" name="birth_date" class="form-control">
                    </div>
                    <div class="form-group">
                        <label for="modal-country">Страна</label>
                        <select id="modal-country" name="country" class="form-control">
                            <option value="">-- Выберите страну --</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="modal-biography">Биография</label>
                        <textarea id="modal-biography" name="biography" class="form-control" rows="3"></textarea>
                    </div>
                    <div class="modal-actions">
                        <button type="button" class="btn btn-secondary modal-cancel">Отмена</button>
                        <button type="submit" class="btn">Добавить</button>
                    </div>
                </form>
                <div id="modal-message" class="modal-message" style="display: none;"></div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Загружаем список стран
    loadCountries();

    // Добавляем обработчики
    document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
        btn.addEventListener('click', closeModal);
    });

    // Обработка отправки формы
    document.getElementById('quick-add-form').addEventListener('submit', function(e) {
        e.preventDefault();
        submitQuickAddForm(this);
    });
}

function loadCountries() {
    fetch('/manager/api/countries/')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('modal-country');
            if (select && data.countries) {
                data.countries.forEach(country => {
                    const option = document.createElement('option');
                    option.value = country.id;
                    option.textContent = country.name;
                    select.appendChild(option);
                });
            }
        })
        .catch(error => console.error('Error loading countries:', error));
}

function submitQuickAddForm(form) {
    const formData = new FormData(form);
    const url = form.dataset.url;
    const messageDiv = document.getElementById('modal-message');
    const submitBtn = form.querySelector('button[type="submit"]');

    // Показываем загрузку
    submitBtn.disabled = true;
    submitBtn.textContent = 'Добавление...';

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Показываем успех
            messageDiv.style.display = 'block';
            messageDiv.className = 'modal-message success';
            messageDiv.textContent = data.message;

            // Добавляем новый элемент в select
            addToSelect(form.dataset.type, data.id, data.name);

            // Закрываем модальное окно через 1.5 секунды
            setTimeout(() => {
                closeModal();
            }, 1500);
        } else {
            // Показываем ошибку
            messageDiv.style.display = 'block';
            messageDiv.className = 'modal-message error';
            messageDiv.textContent = data.message;
            submitBtn.disabled = false;
            submitBtn.textContent = 'Добавить';
        }
    })
    .catch(error => {
        messageDiv.style.display = 'block';
        messageDiv.className = 'modal-message error';
        messageDiv.textContent = 'Ошибка при добавлении: ' + error;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Добавить';
    });
}

function addToSelect(type, id, name) {
    const selectId = type === 'director' ? 'id_directors' : 'id_actors';
    const select = document.getElementById(selectId);

    if (select) {
        // Создаем новую опцию
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        option.selected = true;

        // Добавляем в select
        select.appendChild(option);

        // Обновляем Select2 если используется
        if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
            $(select).trigger('change');
        }
    }
}

function closeModal() {
    const modal = document.getElementById('quick-add-modal');
    if (modal) {
        modal.remove();
    }
}

function initImagePreview() {
    const posterInput = document.getElementById('id_poster');
    const previewDiv = document.getElementById('image-preview');

    if (posterInput && previewDiv) {
        posterInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewDiv.innerHTML = `
                        <h4>Предпросмотр:</h4>
                        <img src="${e.target.result}" style="max-width: 200px; max-height: 300px; border-radius: 8px; border: 3px solid #ffcc00;">
                    `;
                };
                reader.readAsDataURL(file);
            } else {
                previewDiv.innerHTML = '';
            }
        });
    }
}

// Вспомогательная функция для получения CSRF токена
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}