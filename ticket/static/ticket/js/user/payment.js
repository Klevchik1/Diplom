// ===== ЛОГИКА СТРАНИЦЫ ОПЛАТЫ =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('💳 Payment page initialized');

    const cardNumberInput = document.getElementById('card-number');
    const cardExpiryInput = document.getElementById('card-expiry');
    const cardCvcInput = document.getElementById('card-cvc');
    const cardDisplay = document.getElementById('card-number-display');
    const cardExpiryDisplay = document.getElementById('card-expiry-display');
    const cardBrand = document.getElementById('card-brand');
    const payButton = document.getElementById('pay-button');
    const paymentForm = document.getElementById('payment-form');
    const errorMessage = document.getElementById('error-message');
    const successOverlay = document.getElementById('success-overlay');
    const timerElement = document.getElementById('timer');

    // Таймер обратного отсчёта
    if (timerElement) {
        let timeLeft = parseInt(timerElement.dataset.timeLeft);

        const timerInterval = setInterval(function() {
            timeLeft--;

            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                window.location.reload();
                return;
            }

            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

            // Предупреждение когда осталось меньше 5 минут
            if (timeLeft <= 300) {
                timerElement.parentElement.classList.add('warning');
            }
        }, 1000);
    }

    // Форматирование номера карты
    if (cardNumberInput) {
        cardNumberInput.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, '');

            // Ограничение 16 цифр
            if (value.length > 16) {
                value = value.slice(0, 16);
            }

            // Форматирование с пробелами
            const formatted = value.replace(/(\d{4})(?=\d)/g, '$1 ');
            this.value = formatted;

            // Обновление отображения на карте
            if (cardDisplay) {
                if (value.length > 0) {
                    cardDisplay.textContent = formatted.padEnd(19, '•');
                } else {
                    cardDisplay.textContent = '•••• •••• •••• ••••';
                }
            }

            // Определение типа карты
            if (cardBrand) {
                if (value.startsWith('4')) {
                    cardBrand.textContent = '💳 Visa';
                } else if (value.startsWith('5')) {
                    cardBrand.textContent = '💳 Mastercard';
                } else if (value.startsWith('2')) {
                    cardBrand.textContent = '💳 МИР';
                } else if (value.length > 0) {
                    cardBrand.textContent = '💳';
                } else {
                    cardBrand.textContent = '';
                }
            }
        });
    }

    // Форматирование срока действия
    if (cardExpiryInput) {
        cardExpiryInput.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, '');

            if (value.length > 4) {
                value = value.slice(0, 4);
            }

            if (value.length > 2) {
                value = value.slice(0, 2) + '/' + value.slice(2);
            }

            this.value = value;

            if (cardExpiryDisplay) {
                cardExpiryDisplay.textContent = value || 'ММ/ГГ';
            }
        });
    }

    // Валидация и отправка формы
    if (paymentForm) {
        paymentForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Сброс ошибок
            if (errorMessage) {
                errorMessage.style.display = 'none';
            }

            // Валидация номера карты
            const cardNumber = cardNumberInput.value.replace(/\s/g, '');
            if (cardNumber.length !== 16) {
                showError('Введите корректный номер карты (16 цифр)');
                cardNumberInput.classList.add('error');
                return;
            }
            cardNumberInput.classList.remove('error');

            // Валидация срока действия
            const cardExpiry = cardExpiryInput.value;
            if (!/^\d{2}\/\d{2}$/.test(cardExpiry)) {
                showError('Введите срок действия в формате ММ/ГГ');
                cardExpiryInput.classList.add('error');
                return;
            }

            const [month, year] = cardExpiry.split('/');
            const currentYear = new Date().getFullYear() % 100;
            const currentMonth = new Date().getMonth() + 1;

            if (parseInt(month) < 1 || parseInt(month) > 12) {
                showError('Неверный месяц');
                cardExpiryInput.classList.add('error');
                return;
            }

            if (parseInt(year) < currentYear ||
                (parseInt(year) === currentYear && parseInt(month) < currentMonth)) {
                showError('Срок действия карты истёк');
                cardExpiryInput.classList.add('error');
                return;
            }
            cardExpiryInput.classList.remove('error');

            // Валидация CVC
            const cardCvc = cardCvcInput.value;
            if (!/^\d{3}$/.test(cardCvc)) {
                showError('Введите CVC код (3 цифры)');
                cardCvcInput.classList.add('error');
                return;
            }
            cardCvcInput.classList.remove('error');

            // Отправка формы
            payButton.classList.add('loading');
            payButton.disabled = true;

            const formData = new FormData(paymentForm);

            fetch(paymentForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Показываем анимацию успеха
                    if (successOverlay) {
                        successOverlay.classList.add('show');
                    }

                    // Редирект через 1.5 секунды
                    setTimeout(function() {
                        window.location.href = data.redirect_url;
                    }, 1500);
                } else {
                    showError(data.message || 'Ошибка оплаты');
                    payButton.classList.remove('loading');
                    payButton.disabled = false;
                }
            })
            .catch(error => {
                console.error('Payment error:', error);
                showError('Произошла ошибка. Попробуйте еще раз.');
                payButton.classList.remove('loading');
                payButton.disabled = false;
            });
        });
    }

    function showError(message) {
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.style.display = 'block';
        }
    }
});