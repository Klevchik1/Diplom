// Глобальный менеджер мест
window.seatManagers = {};

// Функция для безопасного парсинга цены
function parseTicketPrice(priceText) {
    if (!priceText) return 0;
    const cleanText = priceText.replace(/[^\d.,]/g, '');
    const normalizedText = cleanText.replace(',', '.');
    const price = parseFloat(normalizedText);
    return isNaN(price) ? 0 : price;
}

// Глобальная функция выбора места
window.selectSeat = function(seatElement, screeningId) {
    console.log('🎯 selectSeat called');
    console.log('  screeningId:', screeningId);
    console.log('  seatElement:', seatElement);
    console.log('  seatElement classList:', seatElement.classList);

    if (!seatElement || !screeningId) {
        console.error('❌ Invalid parameters');
        return false;
    }

    if (seatElement.classList.contains('booked')) {
        console.log('🚫 Seat is booked');
        return false;
    }

    const seatId = seatElement.getAttribute('data-seat-id');
    console.log('  seatId:', seatId);

    let manager = window.seatManagers[screeningId];
    console.log('  Manager found:', !!manager);
    console.log('  All managers:', Object.keys(window.seatManagers));

    if (!manager) {
        console.error('❌ Manager not found for screening', screeningId);

        // Пытаемся создать менеджера на лету
        let price = 0;
        const priceElement = document.querySelector('.screening-price');
        if (priceElement) {
            price = parseTicketPrice(priceElement.textContent);
        }

        console.log('  Creating manager on the fly with price:', price);
        window.initSeatManager(screeningId, price, []);
        manager = window.seatManagers[screeningId];

        if (!manager) {
            alert('Ошибка: система бронирования не инициализирована. Пожалуйста, обновите страницу.');
            return false;
        }
    }

    const seatIndex = manager.selectedSeats.indexOf(seatId);
    console.log('  seatIndex:', seatIndex);
    console.log('  current selectedSeats:', manager.selectedSeats);

    if (seatIndex === -1) {
        // Выбираем место
        manager.selectedSeats.push(seatId);
        seatElement.classList.add('selected');
        seatElement.style.backgroundColor = '#2196F3';
        seatElement.style.transform = 'scale(1.1)';
        seatElement.style.boxShadow = '0 0 10px rgba(33, 150, 243, 0.7)';
        console.log('✅ Seat selected:', seatId);
        console.log('  new selectedSeats:', manager.selectedSeats);
    } else {
        // Отменяем выбор
        manager.selectedSeats.splice(seatIndex, 1);
        seatElement.classList.remove('selected');
        seatElement.style.backgroundColor = '#4CAF50';
        seatElement.style.transform = 'scale(1)';
        seatElement.style.boxShadow = 'none';
        console.log('❌ Seat deselected:', seatId);
        console.log('  new selectedSeats:', manager.selectedSeats);
    }

    updateSelectedSeatsInfo(screeningId);
    return true;
};

// Глобальная функция валидации
window.validateBookingForm = function(screeningId) {
    console.log('🔍 validateBookingForm:', screeningId);

    const manager = window.seatManagers[screeningId];

    if (!manager) {
        console.error('❌ Manager not found');
        alert('Ошибка: система бронирования не инициализирована. Пожалуйста, обновите страницу.');
        return false;
    }

    console.log('  selectedSeats:', manager.selectedSeats);
    console.log('  count:', manager.selectedSeats.length);

    if (manager.selectedSeats.length === 0) {
        alert('Пожалуйста, выберите хотя бы одно место!');
        return false;
    }

    console.log('✅ Form validated');
    return true;
};

// Инициализация менеджера для конкретного сеанса
window.initSeatManager = function(screeningId, price, selectedSeats = []) {
    console.log('🚀 initSeatManager called');
    console.log('  screeningId:', screeningId);
    console.log('  price:', price);
    console.log('  selectedSeats:', selectedSeats);

    if (!window.seatManagers) {
        window.seatManagers = {};
    }

    const validPrice = isNaN(price) ? 0 : price;

    const selectedSeatsInfo = document.getElementById('selected-seats-info-' + screeningId);
    const selectedSeatsInput = document.getElementById('selected-seats-input-' + screeningId);
    const bookButton = document.getElementById('book-button-' + screeningId);

    console.log('🔍 Elements found:');
    console.log('  selectedSeatsInfo:', selectedSeatsInfo ? 'found' : 'NOT FOUND');
    console.log('  selectedSeatsInput:', selectedSeatsInput ? 'found' : 'NOT FOUND');
    console.log('  bookButton:', bookButton ? 'found' : 'NOT FOUND');

    window.seatManagers[screeningId] = {
        selectedSeats: selectedSeats,
        selectedSeatsInfo: selectedSeatsInfo,
        selectedSeatsInput: selectedSeatsInput,
        bookButton: bookButton,
        screeningPrice: validPrice
    };

    console.log('✅ Manager created for screening', screeningId);
    console.log('  All managers now:', Object.keys(window.seatManagers));

    updateSelectedSeatsInfo(screeningId);

    // Привязываем обработчики к местам
    attachSeatHandlers(screeningId);
};

// Обновление информации о выбранных местах
function updateSelectedSeatsInfo(screeningId) {
    const manager = window.seatManagers[screeningId];

    if (!manager) {
        console.error('❌ Manager not found for update:', screeningId);
        return;
    }

    const count = manager.selectedSeats.length;
    const price = isNaN(manager.screeningPrice) ? 0 : manager.screeningPrice;
    const totalPrice = count * price;

    console.log('📊 Updating info for screening', screeningId);
    console.log('  count:', count);
    console.log('  totalPrice:', totalPrice);

    if (manager.selectedSeatsInfo) {
        manager.selectedSeatsInfo.textContent = count === 0 ?
            'Выбрано мест: 0' :
            `Выбрано мест: ${count}, Общая стоимость: ${totalPrice} ₽`;
        console.log('  Info text updated');
    } else {
        console.warn('  selectedSeatsInfo element not found');
    }

    if (manager.bookButton) {
        manager.bookButton.disabled = (count === 0);
        manager.bookButton.style.opacity = count === 0 ? '0.6' : '1';
        manager.bookButton.style.cursor = count === 0 ? 'not-allowed' : 'pointer';
        console.log('  Button state updated, disabled:', count === 0);
    }

    if (manager.selectedSeatsInput) {
        manager.selectedSeatsInput.value = JSON.stringify(manager.selectedSeats);
        console.log('  Input value updated:', manager.selectedSeatsInput.value);
    }
}

// Привязка обработчиков к местам
function attachSeatHandlers(screeningId) {
    console.log('🔗 attachSeatHandlers called for screening', screeningId);

    // Находим все места в контейнере selected-screening
    const container = document.getElementById('selected-screening');
    let seats;

    if (container) {
        seats = container.querySelectorAll('.seat');
        console.log('  Found seats in #selected-screening:', seats.length);
    } else {
        seats = document.querySelectorAll('.seat');
        console.log('  Found seats in document:', seats.length);
    }

    const availableSeats = Array.from(seats).filter(seat => !seat.classList.contains('booked'));
    console.log('  Available seats:', availableSeats.length);

    if (seats.length === 0) {
        console.error('❌ NO SEATS FOUND IN DOM!');
        return;
    }

    availableSeats.forEach((seat, index) => {
        // Удаляем старый обработчик
        if (seat._clickHandler) {
            seat.removeEventListener('click', seat._clickHandler);
        }

        // Создаём новый обработчик
        const handler = function(e) {
            console.log('🖱️ SEAT CLICKED!');
            console.log('  event target:', e.target);
            console.log('  seat element:', this);
            console.log('  screeningId:', screeningId);
            e.preventDefault();
            e.stopPropagation();
            window.selectSeat(this, screeningId);
        };

        seat._clickHandler = handler;
        seat.addEventListener('click', handler);

        if (index < 5) {
            console.log('  Handler attached to seat:', seat.getAttribute('data-seat-id'));
        }
    });

    console.log('✅ All handlers attached');
}

// Переключение табов
window.showTab = function(tabName) {
    console.log('📑 Switching tab to:', tabName);

    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });

    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });

    const tabContent = document.getElementById(tabName + '-tab');
    if (tabContent) {
        tabContent.style.display = 'block';
    }

    if (event && event.target) {
        event.target.classList.add('active');
    }
};

// Выбор сеанса (AJAX)
window.selectScreening = function(screeningId) {
    console.log('🔄 selectScreening called with id:', screeningId);

    // Активируем карточку
    document.querySelectorAll('.screening-card').forEach(card => {
        card.classList.remove('active');
    });

    const selectedCard = document.getElementById('screening-' + screeningId);
    if (selectedCard) {
        selectedCard.classList.add('active');
        console.log('  Card activated:', selectedCard.id);
    }

    // Показываем индикатор загрузки
    const container = document.getElementById('selected-screening');
    if (container) {
        container.innerHTML = '<div style="text-align: center; padding: 50px;">Загрузка информации о сеансе...</div>';
        console.log('  Loading indicator shown');
    }

    // Загружаем partial view
    const url = `/screening/${screeningId}/partial/`;
    console.log('  Fetching URL:', url);

    fetch(url)
        .then(response => {
            console.log('  Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            if (!container) return;

            console.log('  HTML received, length:', html.length);
            container.innerHTML = html;
            console.log('  Container updated');

            // Проверяем наличие мест в загруженном HTML
            const hasSeats = html.includes('class="seat');
            console.log('  HTML contains seats:', hasSeats);

            // Инициализируем после загрузки
            setTimeout(() => {
                const isGuest = document.querySelector('.guest-notification') !== null;

                if (isGuest) {
                    console.log('👤 Guest user after AJAX');
                    return;
                }

                // Получаем цену из загруженного контента
                let price = 0;
                const priceElement = container.querySelector('.screening-price');
                if (priceElement) {
                    price = parseTicketPrice(priceElement.textContent);
                    console.log('  Price found:', price);
                } else {
                    console.warn('  Price element not found');
                }

                console.log('✅ AJAX load complete - Initializing manager');
                window.initSeatManager(screeningId, price, []);

            }, 100);
        })
        .catch(error => {
            console.error('❌ AJAX error:', error);
            if (container) {
                container.innerHTML = '<div style="text-align: center; padding: 50px; color: red;">Ошибка загрузки информации о сеансе. Пожалуйста, обновите страницу.</div>';
            }
        });
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 Screenings.js DOMContentLoaded - Starting initialization');

    const screeningInput = document.querySelector('input[name="screening_id"]');
    const isScreeningDetail = window.location.pathname.includes('/screening/');
    const isMovieDetail = window.location.pathname.includes('/movie/');

    console.log('  isScreeningDetail:', isScreeningDetail);
    console.log('  isMovieDetail:', isMovieDetail);
    console.log('  screeningInput:', screeningInput ? screeningInput.value : 'not found');

    if (isScreeningDetail && screeningInput) {
        // Страница деталей сеанса
        const screeningId = screeningInput.value;
        const isGuest = document.querySelector('.guest-notification') !== null;

        console.log('  Screening detail page, screeningId:', screeningId);
        console.log('  isGuest:', isGuest);

        if (!isGuest) {
            let price = 0;
            const priceElement = document.querySelector('.screening-price');
            if (priceElement) {
                price = parseTicketPrice(priceElement.textContent);
            }

            console.log('  Initializing with price:', price);

            // Небольшая задержка для полного рендеринга DOM
            setTimeout(function() {
                const seats = document.querySelectorAll('.seat');
                console.log('  Seats found in DOM:', seats.length);
                window.initSeatManager(screeningId, price, []);
            }, 100);
        }
    } else if (isMovieDetail) {
        // Страница деталей фильма
        console.log('  Movie detail page');

        setTimeout(function() {
            const firstScreeningCard = document.querySelector('.screening-card.active');
            if (firstScreeningCard) {
                const screeningId = firstScreeningCard.id.replace('screening-', '');
                console.log('  First screening card found:', screeningId);

                // Проверяем, есть ли уже контент в selected-screening
                const container = document.getElementById('selected-screening');
                const hasContent = container && container.querySelector('.seat');

                if (hasContent) {
                    console.log('  Content already loaded, just initializing manager');
                    let price = 0;
                    const priceElement = container.querySelector('.screening-price');
                    if (priceElement) {
                        price = parseTicketPrice(priceElement.textContent);
                    }
                    window.initSeatManager(screeningId, price, []);
                } else {
                    console.log('  Content not loaded, calling selectScreening');
                    window.selectScreening(screeningId);
                }
            } else {
                console.warn('  No screening card found');
            }
        }, 100);
    }

    console.log('🎬 Screenings.js initialization complete');
});