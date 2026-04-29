// Общие функции для авторизации
document.addEventListener('DOMContentLoaded', function() {
    console.log('Auth.js loaded');

    // Инициализация переключателей пароля
    initPasswordToggles();

    // Подсветка полей с ошибками
    highlightErrorFields();

    // Инициализация валидации форм
    const registrationForm = document.getElementById('registrationForm');
    if (registrationForm) {
        initializeRegistrationValidation();
    }

    // Инициализация форматирования телефона
    const phoneInput = document.getElementById('id_number');
    if (phoneInput) {
        initPhoneFormatting(phoneInput);
    }

    // Инициализация автофокуса и ограничений для кода
    const codeInput = document.getElementById('id_reset_code');
    if (codeInput) {
        initCodeInput(codeInput);
    }

    const verificationInput = document.getElementById('verification_code');
    if (verificationInput) {
        initCodeInput(verificationInput);
    }
});

// Функция переключения видимости пароля
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

// Инициализация всех переключателей пароля
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

        // Если есть функция валидации, вызываем её
        if (window.validateField) {
            window.validateField(e.target);
        }
    });
}

// Инициализация поля ввода кода
function initCodeInput(input) {
    input.focus();

    input.addEventListener('input', function(e) {
        this.value = this.value.replace(/\D/g, '');

        // Автоматическая отправка при вводе 6 цифр
        if (this.value.length === 6) {
            this.form.submit();
        }
    });
}

// Валидация для формы регистрации
function initializeRegistrationValidation() {
    const form = document.getElementById('registrationForm');
    const submitBtn = document.getElementById('submitBtn');

    if (!form || !submitBtn) return;

    // Изначально блокируем кнопку
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.6';
    submitBtn.style.cursor = 'not-allowed';

    const fields = form.querySelectorAll('[data-validate]');

    // Валидаторы
    const validators = {
        email: function(value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!value.trim()) return 'Email обязателен для заполнения';
            if (!emailRegex.test(value)) return 'Введите корректный email адрес';
            if (value.length > 100) return 'Email не должен превышать 100 символов';
            return null;
        },

        name: function(value) {
            const nameRegex = /^[а-яА-Яa-zA-Z\- ]+$/;
            if (!value.trim()) return 'Имя обязательно для заполнения';
            if (value.length < 2) return 'Имя должно содержать минимум 2 символа';
            if (value.length > 30) return 'Имя не должно превышать 30 символов';
            if (!nameRegex.test(value)) return 'Имя может содержать только буквы и дефисы';
            return null;
        },

        surname: function(value) {
            const surnameRegex = /^[а-яА-Яa-zA-Z\- ]+$/;
            if (!value.trim()) return 'Фамилия обязательна для заполнения';
            if (value.length < 2) return 'Фамилия должна содержать минимум 2 символа';
            if (value.length > 30) return 'Фамилия не должна превышать 30 символов';
            if (!surnameRegex.test(value)) return 'Фамилия может содержать только буквы и дефисы';
            return null;
        },

        phone: function(value) {
            if (!value.trim()) return 'Телефон обязателен для заполнения';

            const phoneRegex = /^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$/;
            if (!phoneRegex.test(value)) {
                return 'Формат: +7 (999) 123-45-67';
            }

            const cleanNumber = value.replace(/\D/g, '');
            if (cleanNumber.length !== 11) {
                return 'Номер должен содержать 11 цифр';
            }

            return null;
        },

        password: function(value) {
            if (!value.trim()) return 'Пароль обязателен для заполнения';
            if (value.length < 8) return 'Пароль должен содержать минимум 8 символов';
            if (/^\d+$/.test(value)) return 'Пароль не должен состоять только из цифр';
            if (value.toLowerCase() === 'password' ||
                value.toLowerCase() === '12345678' ||
                value.toLowerCase() === 'qwertyui') {
                return 'Пароль слишком простой';
            }
            return null;
        },

        confirm: function(value) {
            const password = document.getElementById('id_password1').value;
            if (!value.trim()) return 'Подтвердите пароль';
            if (value !== password) return 'Пароли не совпадают';
            return null;
        }
    };

    // Функция проверки поля
    window.validateField = function(field) {
        const validatorType = field.getAttribute('data-validate');
        const value = field.value;
        const validator = validators[validatorType];
        const errorElement = document.getElementById(field.name + '_error');

        if (!validator) return true;

        const error = validator(value);

        if (error) {
            showFieldError(field, errorElement, error);
            return false;
        } else {
            clearFieldError(field, errorElement);
            return true;
        }
    };

    // Показать ошибку поля
    function showFieldError(field, errorElement, message) {
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
        field.classList.remove('valid-field');
        field.classList.add('error-field');
    }

    // Очистить ошибку поля
    function clearFieldError(field, errorElement) {
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
        field.classList.remove('error-field');
        field.classList.add('valid-field');

        setTimeout(() => {
            field.classList.remove('valid-field');
        }, 2000);
    }

    // Проверить всю форму
    function validateForm() {
        let isValid = true;

        fields.forEach(field => {
            if (!window.validateField(field)) {
                isValid = false;
            }
        });

        submitBtn.disabled = !isValid;
        submitBtn.style.opacity = isValid ? '1' : '0.6';
        submitBtn.style.cursor = isValid ? 'pointer' : 'not-allowed';

        return isValid;
    }

    // Добавляем события валидации
    fields.forEach(field => {
        let timeout;
        field.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                window.validateField(this);
                validateForm();
            }, 300);
        });

        field.addEventListener('blur', function() {
            window.validateField(this);
            validateForm();
        });
    });

    // Особые проверки для паролей
    const passwordField = document.getElementById('id_password1');
    const confirmField = document.getElementById('id_password2');

    if (passwordField && confirmField) {
        passwordField.addEventListener('input', function() {
            window.validateField(passwordField);
            window.validateField(confirmField);
            validateForm();
        });

        confirmField.addEventListener('input', function() {
            window.validateField(confirmField);
            validateForm();
        });
    }

    // Валидация при отправке
    form.addEventListener('submit', function(e) {
        if (!validateForm()) {
            e.preventDefault();

            const firstError = form.querySelector('.error-field');
            if (firstError) {
                firstError.focus();
            }

            return false;
        }
    });

    // Начальная проверка
    validateForm();
}