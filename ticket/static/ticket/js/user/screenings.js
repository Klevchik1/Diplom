// Глобальный менеджер мест
window.seatManagers = {};

// Инициализация страницы сеанса
document.addEventListener('DOMContentLoaded', function() {
    console.log('Screenings.js loaded');

    // Получаем ID сеанса из скрытого поля
    const screeningInput = document.querySelector('input[name="screening_id"]');
    if (screeningInput) {
        const screeningId = screeningInput.value;
        const priceElement = document.querySelector('.screening-price');
        const price = priceElement ? parseFloat(priceElement.textContent.replace(/[^\d.,]/g, '').replace(',', '.')) : 0;

        // Проверяем, авторизован ли пользователь
        const isGuest = document.querySelector('.guest-notification') !== null;

        if (!isGuest) {
            initSeatManager(screeningId, price);
        }
    }
});

// Инициализация менеджера мест
function initSeatManager(screeningId, price) {
    if (!window.seatManagers) {
        window.seatManagers = {};
    }

    if (!window.seatManagers[screeningId]) {
        window.seatManagers[screeningId] = {
            selectedSeats: [],
            selectedSeatsInfo: document.getElementById('selected-seats-info-' + screeningId),
            selectedSeatsInput: document.getElementById('selected-seats-input-' + screeningId),
            bookButton: document.getElementById('book-button-' + screeningId),
            screeningPrice: parseFloat(price) || 0
        };
        console.log('Initialized seat manager for screening:', screeningId, 'with price:', window.seatManagers[screeningId].screeningPrice);
    }
    updateSelectedSeatsInfo(screeningId);
}

// Выбор места
function selectSeat(seatElement, screeningId) {
    if (seatElement.classList.contains('booked')) {
        return;
    }

    const seatId = seatElement.getAttribute('data-seat-id');
    const manager = window.seatManagers ? window.seatManagers[screeningId] : null;

    if (!manager) {
        console.error('Manager not found for screening:', screeningId);
        return;
    }

    const seatIndex = manager.selectedSeats.indexOf(seatId);

    if (seatIndex === -1) {
        manager.selectedSeats.push(seatId);
        seatElement.classList.add('selected');
        seatElement.style.backgroundColor = '#2196F3';
        seatElement.style.transform = 'scale(1.1)';
        seatElement.style.boxShadow = '0 0 10px rgba(33, 150, 243, 0.7)';
    } else {
        manager.selectedSeats.splice(seatIndex, 1);
        seatElement.classList.remove('selected');
        seatElement.style.backgroundColor = '#4CAF50';
        seatElement.style.transform = 'scale(1)';
        seatElement.style.boxShadow = 'none';
    }

    updateSelectedSeatsInfo(screeningId);
}

// Обновление информации о выбранных местах
function updateSelectedSeatsInfo(screeningId) {
    const manager = window.seatManagers ? window.seatManagers[screeningId] : null;

    if (!manager) {
        console.error('Cannot update info - manager not found for screening:', screeningId);
        return;
    }

    const count = manager.selectedSeats.length;
    const totalPrice = count * manager.screeningPrice;

    if (manager.selectedSeatsInfo) {
        manager.selectedSeatsInfo.textContent = count === 0 ?
            'Выбрано мест: 0' :
            `Выбрано мест: ${count}, Общая стоимость: ${totalPrice} ₽`;
    }

    if (manager.bookButton) {
        if (count === 0) {
            manager.bookButton.disabled = true;
            manager.bookButton.style.opacity = '0.6';
            manager.bookButton.style.cursor = 'not-allowed';
        } else {
            manager.bookButton.disabled = false;
            manager.bookButton.style.opacity = '1';
            manager.bookButton.style.cursor = 'pointer';
        }
    }

    if (manager.selectedSeatsInput) {
        manager.selectedSeatsInput.value = JSON.stringify(manager.selectedSeats);
        console.log('Form input updated with:', manager.selectedSeats);
    }
}

// Валидация формы бронирования
function validateBookingForm(screeningId) {
    const manager = window.seatManagers ? window.seatManagers[screeningId] : null;

    if (!manager) {
        alert('Ошибка: менеджер мест не инициализирован!');
        return false;
    }

    if (manager.selectedSeats.length === 0) {
        alert('Пожалуйста, выберите хотя бы одно место!');
        return false;
    }

    console.log('Form validated successfully. Seats:', manager.selectedSeats);
    return true;
}

// Переключение табов
function showTab(tabName) {
    // Скрываем все табы
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });

    // Убираем активный класс со всех кнопок
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });

    // Показываем выбранный таб
    const tabContent = document.getElementById(tabName + '-tab');
    if (tabContent) {
        tabContent.style.display = 'block';
    }

    // Активируем кнопку
    event.target.classList.add('active');
}

// Выбор сеанса на странице фильма
function selectScreening(screeningId) {
    // Убираем активный класс со всех карточек
    document.querySelectorAll('.screening-card').forEach(card => {
        card.classList.remove('active');
    });

    // Активируем выбранную карточку
    const selectedCard = document.getElementById('screening-' + screeningId);
    if (selectedCard) {
        selectedCard.classList.add('active');
    }

    // Загружаем информацию о сеансе
    fetch(`/screening/${screeningId}/partial/`)
        .then(response => response.text())
        .then(html => {
            const selectedScreeningDiv = document.getElementById('selected-screening');
            if (selectedScreeningDiv) {
                selectedScreeningDiv.innerHTML = html;

                // Инициализируем менеджер для нового сеанса после загрузки
                setTimeout(() => {
                    const priceElement = document.querySelector('.screening-price');
                    const price = priceElement ? parseFloat(priceElement.textContent.replace(/[^\d.,]/g, '').replace(',', '.')) : 0;
                    const isGuest = document.querySelector('.guest-notification') !== null;

                    if (!isGuest) {
                        initSeatManager(screeningId, price);
                    }
                }, 100);
            }
        })
        .catch(error => {
            console.error('Error loading screening partial:', error);
        });
}

// Инициализация сеанса после AJAX загрузки
function initScreeningAfterLoad(screeningId, price, isGuest) {
    console.log('Initializing screening after AJAX load:', screeningId, 'Price:', price, 'Is guest:', isGuest);

    if (isGuest) {
        console.log('User is guest, disabling booking functionality for screening:', screeningId);
        const bookButton = document.getElementById('book-button-' + screeningId);
        if (bookButton) {
            bookButton.style.display = 'none';
        }
        const seats = document.querySelectorAll('.seat:not(.booked)');
        seats.forEach(seat => {
            seat.style.cursor = 'not-allowed';
            seat.style.opacity = '0.6';
            seat.onclick = null;
        });
    } else {
        initSeatManager(screeningId, price);
    }
}