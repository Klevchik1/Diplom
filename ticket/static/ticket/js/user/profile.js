// Скрипты для личного кабинета
document.addEventListener('DOMContentLoaded', function() {
    console.log('Profile.js loaded');

    // Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_number');
    if (phoneInput) {
        initPhoneFormatting(phoneInput);
    }

    // Инициализация переключателей пароля
    initPasswordToggles();

    // Подсветка полей с ошибками
    highlightErrorFields();
});

// Форматирование телефона
function initPhoneFormatting(phoneInput) {
    phoneInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');

        if (value.startsWith('7') || value.startsWith('8')) {
            value = value.substring(1);
        }

        if (value.length > 0) {
            value = '+7 (' + value;

            if (value.length > 7) {
                value = value.substring(0, 7) + ') ' + value.substring(7);
            }
            if (value.length > 12) {
                value = value.substring(0, 12) + '-' + value.substring(12);
            }
            if (value.length > 15) {
                value = value.substring(0, 15) + '-' + value.substring(15);
            }
        }

        e.target.value = value;
    });
}

// Переключение видимости пароля
function togglePassword(inputId, button) {
    const passwordInput = document.getElementById(inputId);
    if (passwordInput) {
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            button.textContent = '🔒';
        } else {
            passwordInput.type = 'password';
            button.textContent = '👁️';
        }
    }
}

// Инициализация переключателей пароля
function initPasswordToggles() {
    const passwordFields = document.querySelectorAll('input[type="password"]');
    passwordFields.forEach(field => {
        if (!field.parentNode.querySelector('.password-toggle')) {
            const toggleButton = document.createElement('button');
            toggleButton.type = 'button';
            toggleButton.className = 'password-toggle';
            toggleButton.innerHTML = '👁️';
            toggleButton.onclick = function() {
                togglePassword(field.id, this);
            };

            const inputContainer = document.createElement('div');
            inputContainer.className = 'input-with-icon';
            field.parentNode.insertBefore(inputContainer, field);
            inputContainer.appendChild(field);
            inputContainer.appendChild(toggleButton);
        }
    });
}

// Подсветка полей с ошибками
function highlightErrorFields() {
    const errorFields = document.querySelectorAll('.error-field');
    errorFields.forEach(field => {
        field.style.borderColor = '#ff6b6b';
        field.style.boxShadow = '0 0 10px rgba(255, 107, 107, 0.5)';
    });
}

// Подтверждение возврата билета
function confirmRefund() {
    return confirm("Вы уверены, что хотите вернуть билет?\n\n✅ Возвращается полная стоимость\n⚠️ После возврата билет станет недействительным\n\nДля продолжения нажмите OK");
}

// Подтверждение отмены возврата
function confirmCancelRefund() {
    return confirm("Вы уверены, что хотите отменить запрос на возврат?\n\nБилет снова станет активным и действительным");
}

// Проверка времени для возврата
function checkRefundTime(startTimeStr, ticketId) {
    const startTime = new Date(startTimeStr);
    const now = new Date();
    const timeDiff = startTime - now;
    const minutesDiff = Math.floor(timeDiff / (1000 * 60));

    if (minutesDiff < 30) {
        alert(`Возврат невозможен!\n\nДо сеанса осталось ${minutesDiff} минут.\nВозврат возможен только за 30 минут до начала.`);
        return false;
    }

    return confirmRefund();
}