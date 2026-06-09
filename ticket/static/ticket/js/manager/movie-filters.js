// ============================================
// ФИЛЬТРАЦИЯ И ПАГИНАЦИЯ ФИЛЬМОВ (AJAX)
// ============================================

let currentFilters = {
    search: '',
    genre: '',
    age_rating: '',
    country: '',
    year_min: '',
    year_max: '',
    page: 1
};

let isFiltering = false;

document.addEventListener('DOMContentLoaded', function() {
    initMovieFilters();
    loadFiltersFromURL();
    updateFilterValuesFromURL();
});

function initMovieFilters() {
    const searchInput = document.getElementById('movie-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            currentFilters.search = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        }, 500));
    }

    const genreSelect = document.getElementById('filter-genre');
    if (genreSelect) {
        genreSelect.addEventListener('change', function() {
            currentFilters.genre = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        });
    }

    const ageRatingSelect = document.getElementById('filter-age-rating');
    if (ageRatingSelect) {
        ageRatingSelect.addEventListener('change', function() {
            currentFilters.age_rating = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        });
    }

    const countrySelect = document.getElementById('filter-country');
    if (countrySelect) {
        countrySelect.addEventListener('change', function() {
            currentFilters.country = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        });
    }

    const yearMinInput = document.getElementById('filter-year-min');
    if (yearMinInput) {
        yearMinInput.addEventListener('change', function() {
            currentFilters.year_min = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        });
    }

    const yearMaxInput = document.getElementById('filter-year-max');
    if (yearMaxInput) {
        yearMaxInput.addEventListener('change', function() {
            currentFilters.year_max = this.value;
            currentFilters.page = 1;
            applyFilters();
            updateURL();
        });
    }

    const resetBtn = document.getElementById('reset-filters');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            resetFilters();
        });
    }

    const paginationContainer = document.getElementById('movies-pagination');
    if (paginationContainer) {
        paginationContainer.addEventListener('click', function(e) {
            const pageBtn = e.target.closest('.page-btn');
            if (pageBtn && !pageBtn.classList.contains('disabled')) {
                const page = pageBtn.dataset.page;
                if (page && !isFiltering) {
                    currentFilters.page = parseInt(page);
                    applyFilters();
                    updateURL();
                    document.querySelector('.table-container')?.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    }
}

function applyFilters() {
    if (isFiltering) return;
    isFiltering = true;

    showLoadingIndicator();

    const formData = new FormData();
    formData.append('search', currentFilters.search);
    formData.append('genre', currentFilters.genre);
    formData.append('age_rating', currentFilters.age_rating);
    formData.append('country', currentFilters.country);
    formData.append('year_min', currentFilters.year_min);
    formData.append('year_max', currentFilters.year_max);
    formData.append('page', currentFilters.page);

    fetch('/manager/api/movies/filter/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateMoviesTable(data);
            updatePagination(data);
        } else {
            showError(data.message || 'Ошибка загрузки фильмов');
        }
    })
    .catch(error => {
        console.error('Filter error:', error);
        showError('Ошибка при загрузке данных');
    })
    .finally(() => {
        isFiltering = false;
    });
}

function updateMoviesTable(data) {
    const tbody = document.getElementById('movies-table-body');
    if (!tbody) return;

    if (!data.movies || data.movies.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center">
                    😕 Фильмы не найдены. Попробуйте изменить параметры поиска.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    for (const movie of data.movies) {
        html += `
            <tr>
                <td class="poster-cell">
                    ${movie.poster_url ?
                        `<img src="${movie.poster_url}" alt="${escapeHtml(movie.title)}" class="poster-preview">` :
                        '<span class="no-poster">—</span>'
                    }
                </td>
                <td class="title-cell"><strong>${escapeHtml(movie.title)}</strong></td>
                <td class="genres-cell">
                    ${movie.genres.map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`).join('')}
                </td>
                <td class="countries-cell">
                    ${movie.countries.map(c => `<span class="country-tag">${escapeHtml(c)}</span>`).join('') || '—'}
                </td>
                <td class="year-cell">${movie.release_year}</td>
                <td class="age-cell"><span class="age-badge">${escapeHtml(movie.age_rating)}</span></td>
                <td class="duration-cell">${movie.duration_display}</td>
                <td class="actions-cell">
                    <div class="action-buttons">
                        <a href="/manager/movies/${movie.id}/edit/" class="btn btn-sm btn-warning">✏️</a>
                        <a href="/manager/movies/${movie.id}/delete/" class="btn btn-sm btn-danger" data-confirm="Удалить фильм?">❌</a>
                    </div>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

function updatePagination(data) {
    const paginationContainer = document.getElementById('movies-pagination');
    if (!paginationContainer) return;

    if (data.total_pages <= 1) {
        paginationContainer.innerHTML = '';
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
            html += `<button class="page-btn active" data-page="${i}" disabled>${i}</button>`;
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

    html += `<span class="page-info">Страница ${data.current_page} из ${data.total_pages} (всего ${data.total_count} фильмов)</span>`;
    html += '</div>';

    paginationContainer.innerHTML = html;
}

function resetFilters() {
    const searchInput = document.getElementById('movie-search');
    if (searchInput) searchInput.value = '';

    const genreSelect = document.getElementById('filter-genre');
    if (genreSelect) genreSelect.value = '';

    const ageRatingSelect = document.getElementById('filter-age-rating');
    if (ageRatingSelect) ageRatingSelect.value = '';

    const countrySelect = document.getElementById('filter-country');
    if (countrySelect) countrySelect.value = '';

    const yearMinInput = document.getElementById('filter-year-min');
    if (yearMinInput) yearMinInput.value = '';

    const yearMaxInput = document.getElementById('filter-year-max');
    if (yearMaxInput) yearMaxInput.value = '';

    currentFilters = {
        search: '',
        genre: '',
        age_rating: '',
        country: '',
        year_min: '',
        year_max: '',
        page: 1
    };

    applyFilters();
    updateURL();
}

function loadFiltersFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) currentFilters.search = urlParams.get('search');
    if (urlParams.get('genre')) currentFilters.genre = urlParams.get('genre');
    if (urlParams.get('age_rating')) currentFilters.age_rating = urlParams.get('age_rating');
    if (urlParams.get('country')) currentFilters.country = urlParams.get('country');
    if (urlParams.get('year_min')) currentFilters.year_min = urlParams.get('year_min');
    if (urlParams.get('year_max')) currentFilters.year_max = urlParams.get('year_max');
    if (urlParams.get('page')) currentFilters.page = parseInt(urlParams.get('page'));
    applyFilters();
}

function updateFilterValuesFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('search')) document.getElementById('movie-search').value = urlParams.get('search');
    if (urlParams.get('genre')) document.getElementById('filter-genre').value = urlParams.get('genre');
    if (urlParams.get('age_rating')) document.getElementById('filter-age-rating').value = urlParams.get('age_rating');
    if (urlParams.get('country')) document.getElementById('filter-country').value = urlParams.get('country');
    if (urlParams.get('year_min')) document.getElementById('filter-year-min').value = urlParams.get('year_min');
    if (urlParams.get('year_max')) document.getElementById('filter-year-max').value = urlParams.get('year_max');
}

function updateURL() {
    const urlParams = new URLSearchParams();
    if (currentFilters.search) urlParams.set('search', currentFilters.search);
    if (currentFilters.genre) urlParams.set('genre', currentFilters.genre);
    if (currentFilters.age_rating) urlParams.set('age_rating', currentFilters.age_rating);
    if (currentFilters.country) urlParams.set('country', currentFilters.country);
    if (currentFilters.year_min) urlParams.set('year_min', currentFilters.year_min);
    if (currentFilters.year_max) urlParams.set('year_max', currentFilters.year_max);
    if (currentFilters.page > 1) urlParams.set('page', currentFilters.page);
    const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
    window.history.pushState({}, '', newUrl);
}

function showLoadingIndicator() {
    const tbody = document.getElementById('movies-table-body');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center">
                    <div class="loading-spinner"></div>
                    <span>Загрузка...</span>
                </td>
            </tr>
        `;
    }
}

function showError(message) {
    const tbody = document.getElementById('movies-table-body');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center" style="color: #ff4444;">
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
