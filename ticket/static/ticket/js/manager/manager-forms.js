// Скрипты для форм в панели менеджера

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех форм
    initForms();

    // Инициализация price calculation для сеансов
    initPriceCalculation();

    // Инициализация preview изображений
    initImagePreview();

    // Инициализация валидации форм
    initFormValidation();
});

function initForms() {
    // Добавляем класс required для обязательных полей
    const requiredFields = document.querySelectorAll('[required]');
    requiredFields.forEach(field => {
        const label = document.querySelector(`label[for="${field.id}"]`);
        if (label) {
            label.classList.add('required');
        }
    });

    // Подсветка полей с ошибками
    const errorFields = document.querySelectorAll('.error-field');
    errorFields.forEach(field => {
        field.addEventListener('input', function() {
            this.classList.remove('error-field');
        });
    });
}

function initPriceCalculation() {
    const hallSelect = document.getElementById('id_hall');
    const startTimeInput = document.getElementById('id_start_time');
    const priceField = document.getElementById('id_ticket_price');

    if (!hallSelect || !startTimeInput || !priceField) return;

    function updatePrice() {
        if (!hallSelect.value || !startTimeInput.value) {
            priceField.value = '';
            return;
        }

        const date = new Date(startTimeInput.value);
        const hour = date.getHours();

        // Показываем индикатор загрузки
        priceField.disabled = true;
        priceField.style.opacity = '0.5';

        fetch('/admin/screening/calculate-price/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                hall_id: hallSelect.value,
                time: hour + ':00'
            })
        })
        .then(response => response.json())
        .then(data => {
            priceField.disabled = false;
            priceField.style.opacity = '1';

            if (data.success) {
                priceField.value = data.price;

                // Добавляем визуальный эффект
                priceField.style.transition = 'background-color 0.3s';
                priceField.style.backgroundColor = '#c6f6d5';
                setTimeout(() => {
                    priceField.style.backgroundColor = '';
                }, 500);
            } else {
                console.error('Price calculation error:', data.error);
            }
        })
        .catch(error => {
            priceField.disabled = false;
            priceField.style.opacity = '1';
            console.error('Fetch error:', error);
        });
    }

    hallSelect.addEventListener('change', updatePrice);
    startTimeInput.addEventListener('change', updatePrice);
}

function initImagePreview() {
    const imageInput = document.getElementById('id_poster');
    const previewContainer = document.getElementById('image-preview');

    if (!imageInput || !previewContainer) return;

    imageInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();

            reader.onload = function(e) {
                previewContainer.innerHTML = `
                    <div class="image-preview">
                        <img src="${e.target.result}" alt="Preview">
                        <p style="margin: 5px 0 0; font-size: 12px; color: #666;">
                            ${file.name} (${(file.size / 1024).toFixed(2)} KB)
                        </p>
                    </div>
                `;
            };

            reader.readAsDataURL(file);
        } else {
            previewContainer.innerHTML = '';
        }
    });
}

function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate="true"]');

    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            const requiredFields = form.querySelectorAll('[required]');

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error-field');

                    // Показываем сообщение об ошибке
                    let errorMsg = field.parentNode.querySelector('.field-error');
                    if (!errorMsg) {
                        errorMsg = document.createElement('small');
                        errorMsg.className = 'field-error';
                        errorMsg.style.color = '#f56565';
                        errorMsg.style.display = 'block';
                        errorMsg.style.marginTop = '5px';
                        field.parentNode.appendChild(errorMsg);
                    }
                    errorMsg.textContent = 'Это поле обязательно для заполнения';
                }
            });

            if (!isValid) {
                e.preventDefault();

                // Прокручиваем к первому полю с ошибкой
                const firstError = form.querySelector('.error-field');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    });
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

// Функция для подтверждения действий
function confirmAction(message, element) {
    return function(e) {
        if (!confirm(message)) {
            e.preventDefault();
            return false;
        }
        return true;
    };
}

// Применяем confirm ко всем кнопкам с data-confirm
document.querySelectorAll('[data-confirm]').forEach(element => {
    const message = element.dataset.confirm || 'Вы уверены?';
    element.addEventListener('click', confirmAction(message, element));
});

// Функция для форматирования дат в формах
function formatDateTimeForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');

    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Устанавливаем минимальную дату для полей даты
const dateInputs = document.querySelectorAll('input[type="datetime-local"]');
if (dateInputs.length > 0) {
    const now = new Date();
    const minDateTime = formatDateTimeForInput(now);

    dateInputs.forEach(input => {
        input.min = minDateTime;
    });
}