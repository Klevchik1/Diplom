// ============================================
// ФИЛЬТРАЦИЯ И ПАГИНАЦИЯ СЕАНСОВ (AJAX)
// ============================================

let screeningFilters = {
    view_mode: 'upcoming',
    search: '',
    date: '',
    movie: '',
    hall: '',
    page: 1
};

let isScreeningFiltering = false;

document.addEventListener('DOMContentLoaded', function() {
    initScreeningFilters();
    initScreeningPagination();
    loadScreeningFiltersFromURL();
});

function initScreeningFilters() {
    // Вкладки
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const viewMode = this.dataset.view;
            if (viewMode) {
                screeningFilters.view_mode = viewMode;
                screeningFilters.page = 1;
                applyScreeningFilters();
                updateScreeningURL();

                // Обновляем активный класс
                tabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });

    // Поиск
    const searchInput = document.getElementById('screening-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            screeningFilters.search = this.value;
            screeningFilters.page = 1;
            applyScreeningFilters();
            updateScreeningURL();
        }, 500));
    }

    // Дата
    const dateInput = document.getElementById('screening-date');
    if (dateInput) {
        dateInput.addEventListener('change', function() {
            screeningFilters.date = this.value;
            screeningFilters.page = 1;
            applyScreeningFilters();
            updateScreeningURL();
        });
    }

    // Фильм
    const movieSelect = document.getElementById('screening-movie');
    if (movieSelect) {
        // Слушаем событие change на оригинальном select
        movieSelect.addEventListener('change', function() {
            screeningFilters.movie = this.value;
            screeningFilters.page = 1;
            applyScreeningFilters();
            updateScreeningURL();
        });

        // Дополнительно: если используется Select2, также слушаем событие select2:select
        if (typeof jQuery !== 'undefined') {
            jQuery(movieSelect).on('select2:select select2:clear', function(e) {
                screeningFilters.movie = this.value;
                screeningFilters.page = 1;
                applyScreeningFilters();
                updateScreeningURL();
            });
        }
    }

    // Зал
    const hallSelect = document.getElementById('screening-hall');
    if (hallSelect) {
        hallSelect.addEventListener('change', function() {
            screeningFilters.hall = this.value;
            screeningFilters.page = 1;
            applyScreeningFilters();
            updateScreeningURL();
        });
    }

    // Кнопка сброса
    const resetBtn = document.getElementById('reset-screening-filters');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            resetScreeningFilters();
        });
    }

    // Select2 для фильтра фильмов
    if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
        $('#screening-movie').select2({
            width: '100%',
            placeholder: '🔍 Поиск фильма...',
            allowClear: true,
            language: {
                noResults: function() { return "Ничего не найдено"; }
            }
        });
    }
}

function initScreeningPagination() {
    const paginationContainer = document.getElementById('screenings-pagination');
    if (paginationContainer) {
        paginationContainer.addEventListener('click', function(e) {
            const pageBtn = e.target.closest('.page-btn');
            if (pageBtn && !pageBtn.classList.contains('disabled')) {
                const page = pageBtn.dataset.page;
                if (page && !isScreeningFiltering) {
                    screeningFilters.page = parseInt(page);
                    applyScreeningFilters();
                    updateScreeningURL();
                    document.querySelector('.table-container')?.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    }
}

function applyScreeningFilters() {
    if (isScreeningFiltering) return;
    isScreeningFiltering = true;

    showScreeningLoading();

    const formData = new FormData();
    formData.append('view_mode', screeningFilters.view_mode);
    formData.append('search', screeningFilters.search);
    formData.append('date', screeningFilters.date);
    formData.append('movie', screeningFilters.movie);
    formData.append('hall', screeningFilters.hall);
    formData.append('page', screeningFilters.page);

    fetch('/manager/api/screenings/filter/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateScreeningsTable(data);
            updateScreeningPagination(data);
        } else {
            showScreeningError(data.message || 'Ошибка загрузки');
        }
    })
    .catch(error => {
        console.error('Filter error:', error);
        showScreeningError('Ошибка при загрузке данных');
    })
    .finally(() => {
        isScreeningFiltering = false;
    });
}

function updateScreeningsTable(data) {
    const tbody = document.getElementById('screenings-table-body');
    if (!tbody) return;

    if (!data.screenings || data.screenings.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">
                    😕 Сеансы не найдены. Попробуйте изменить параметры поиска.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    for (const s of data.screenings) {
        const occupancyPercent = s.occupancy_percent;
        let fillColor = '#4CAF50';
        if (occupancyPercent > 80) fillColor = '#f44336';
        else if (occupancyPercent > 50) fillColor = '#FF9800';

        html += `
            <tr>
                <td><strong>${escapeHtml(s.movie_title)}</strong></td>
                <td>${escapeHtml(s.hall_name)}</td>
                <td>${escapeHtml(s.start_time)}</td>
                <td>${s.ticket_price} ₽</td>
                <td>${s.tickets_count} / ${s.total_seats}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 12px;">${occupancyPercent}%</span>
                        <div class="occupancy-bar">
                            <div class="occupancy-fill" style="width: ${occupancyPercent}%; background: ${fillColor};"></div>
                        </div>
                    </div>
                </td>
                <td class="actions-cell">
                    <a href="/manager/screenings/${s.id}/edit/" class="btn btn-sm btn-warning">✏️ Ред.</a>
                    <a href="/manager/screenings/${s.id}/delete/" class="btn btn-sm btn-danger" onclick="return confirm('Удалить сеанс?')">❌ Уд.</a>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

function updateScreeningPagination(data) {
    const container = document.getElementById('screenings-pagination');
    if (!container) return;

    if (data.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '<div class="pagination">';

    if (data.has_previous) {
        html += `<button class="page-btn" data-page="${data.previous_page}">← Назад</button>`;
    } else {
        html += `<button class="page-btn disabled" disabled>← Назад</button>`;
    }

    const startPage = Math.max(1, data.current_page - 2);
    const endPage = Math.min(data.total_pages, data.current_page + 2);

    if (startPage > 1) {
        html += `<button class="page-btn" data-page="1">1</button>`;
        if (startPage > 2) html += `<span class="page-dots">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === data.current_page) {
            html += `<button class="page-btn active" disabled>${i}</button>`;
        } else {
            html += `<button class="page-btn" data-page="${i}">${i}</button>`;
        }
    }

    if (endPage < data.total_pages) {
        if (endPage < data.total_pages - 1) html += `<span class="page-dots">...</span>`;
        html += `<button class="page-btn" data-page="${data.total_pages}">${data.total_pages}</button>`;
    }

    if (data.has_next) {
        html += `<button class="page-btn" data-page="${data.next_page}">Вперёд →</button>`;
    } else {
        html += `<button class="page-btn disabled" disabled>Вперёд →</button>`;
    }

    html += `<span class="page-info">Страница ${data.current_page} из ${data.total_pages} (всего ${data.total_count} сеансов)</span>`;
    html += '</div>';

    container.innerHTML = html;
}

function resetScreeningFilters() {
    document.getElementById('screening-search').value = '';
    document.getElementById('screening-date').value = '';
    document.getElementById('screening-movie').value = '';
    document.getElementById('screening-hall').value = '';

    if (typeof jQuery !== 'undefined') {
        $('#screening-movie').val('').trigger('change');
    }

    screeningFilters = {
        view_mode: screeningFilters.view_mode,
        search: '',
        date: '',
        movie: '',
        hall: '',
        page: 1
    };

    applyScreeningFilters();
    updateScreeningURL();
}

function loadScreeningFiltersFromURL() {
    const urlParams = new URLSearchParams(window.location.search);

    const view_mode = urlParams.get('view');
    if (view_mode === 'upcoming' || view_mode === 'all') {
        screeningFilters.view_mode = view_mode;
        const tabs = document.querySelectorAll('.tab-btn');
        tabs.forEach(tab => {
            if (tab.dataset.view === view_mode) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
    }

    const search = urlParams.get('search');
    if (search) screeningFilters.search = search;

    const date = urlParams.get('date');
    if (date) screeningFilters.date = date;

    const movie = urlParams.get('movie');
    if (movie) screeningFilters.movie = movie;

    const hall = urlParams.get('hall');
    if (hall) screeningFilters.hall = hall;

    const page = urlParams.get('page');
    if (page && !isNaN(parseInt(page))) screeningFilters.page = parseInt(page);

    // Заполняем поля формы
    if (search) document.getElementById('screening-search').value = search;
    if (date) document.getElementById('screening-date').value = date;
    if (movie && typeof jQuery !== 'undefined') $('#screening-movie').val(movie).trigger('change');
    if (hall) document.getElementById('screening-hall').value = hall;

    if (search || date || movie || hall || page !== 1) {
        applyScreeningFilters();
    }
}

function updateScreeningURL() {
    const urlParams = new URLSearchParams();

    if (screeningFilters.view_mode !== 'upcoming') urlParams.set('view', screeningFilters.view_mode);
    if (screeningFilters.search) urlParams.set('search', screeningFilters.search);
    if (screeningFilters.date) urlParams.set('date', screeningFilters.date);
    if (screeningFilters.movie) urlParams.set('movie', screeningFilters.movie);
    if (screeningFilters.hall) urlParams.set('hall', screeningFilters.hall);
    if (screeningFilters.page > 1) urlParams.set('page', screeningFilters.page);

    const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
    window.history.pushState({}, '', newUrl);
}

function showScreeningLoading() {
    const tbody = document.getElementById('screenings-table-body');
    if (tbody && !isScreeningFiltering) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">
                    <div class="loading-spinner"></div>
                    <span>Загрузка...</span>
                </td>
            </tr>
        `;
    }
}

function showScreeningError(message) {
    const tbody = document.getElementById('screenings-table-body');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center" style="color: #ff4444;">
                    ❌ ${escapeHtml(message)}
                </td>
            </tr>
        `;
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}