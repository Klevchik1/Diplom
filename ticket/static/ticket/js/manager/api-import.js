// API импорт фильмов в панели менеджера

// Переключение выпадающего меню
function toggleAddMenu() {
    const menu = document.getElementById('add-menu');
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

// Закрытие меню при клике вне
document.addEventListener('click', function(e) {
    const menu = document.getElementById('add-menu');
    const btn = document.querySelector('.btn-add-dropdown');
    if (menu && btn && !btn.contains(e.target) && !menu.contains(e.target)) {
        menu.style.display = 'none';
    }
});

// Открыть модалку импорта из API
function openApiImportModal() {
    const menu = document.getElementById('add-menu');
    if (menu) menu.style.display = 'none';

    const modal = document.getElementById('api-import-modal');
    if (modal) {
        modal.style.display = 'flex';
        // Очищаем предыдущие результаты
        document.getElementById('search-results').innerHTML = `
            <div class="search-placeholder">
                <p>🔍 Введите название фильма для поиска в базе Poiskkino.dev</p>
                <p class="hint">Фильмы, уже существующие в вашей базе, будут отмечены</p>
            </div>
        `;
        document.getElementById('api-message').style.display = 'none';
        document.getElementById('api-search-input').value = '';
        document.getElementById('api-search-input').focus();
    }
}

// Закрыть модалку
function closeApiImportModal() {
    const modal = document.getElementById('api-import-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Закрытие по клику вне модалки
window.addEventListener('click', function(e) {
    const modal = document.getElementById('api-import-modal');
    if (e.target === modal) {
        closeApiImportModal();
    }
});

// Обработка Enter в поле поиска
function handleSearchKeyup(event) {
    if (event.key === 'Enter') {
        searchMovie();
    }
}

// Поиск фильма
function searchMovie() {
    const query = document.getElementById('api-search-input').value.trim();
    const resultsDiv = document.getElementById('search-results');
    const loadingDiv = document.getElementById('search-loading');
    const messageDiv = document.getElementById('api-message');

    if (query.length < 2) {
        resultsDiv.innerHTML = `
            <div class="search-placeholder">
                <p>⚠️ Введите минимум 2 символа для поиска</p>
            </div>
        `;
        return;
    }

    // Показываем загрузку
    loadingDiv.style.display = 'flex';
    resultsDiv.innerHTML = '';
    messageDiv.style.display = 'none';

    fetch(`/manager/api/search-movie/?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            loadingDiv.style.display = 'none';

            if (!data.success) {
                resultsDiv.innerHTML = `
                    <div class="search-placeholder">
                        <p>❌ ${data.message || 'Ничего не найдено'}</p>
                    </div>
                `;
                return;
            }

            if (data.movies.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="search-placeholder">
                        <p>😕 По запросу "${query}" ничего не найдено</p>
                        <p class="hint">Попробуйте изменить запрос</p>
                    </div>
                `;
                return;
            }

            // Отображаем результаты
            let html = '';
            data.movies.forEach(movie => {
                const existsClass = movie.exists_in_db ? ' exists' : '';
                const posterHtml = movie.poster
                    ? `<img src="${movie.poster}" alt="${movie.title}" class="movie-result-poster" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">`
                    : '';
                const placeholderHtml = movie.poster
                    ? `<div class="movie-result-poster-placeholder" style="display: none;">🎬</div>`
                    : '<div class="movie-result-poster-placeholder">🎬</div>';

                html += `
                    <div class="movie-result-card${existsClass}">
                        ${posterHtml}
                        ${placeholderHtml}
                        <div class="movie-result-info">
                            <div class="movie-result-title">
                                ${escapeHtml(movie.title)}
                                ${movie.rating_kp ? `<span style="color:#ffcc00; font-size:14px;"> ⭐${movie.rating_kp.toFixed(1)}</span>` : ''}
                            </div>
                            <div class="movie-result-meta">
                                ${movie.year || '—'} год • ${movie.duration || '?'} мин
                            </div>
                            ${movie.description ? `<div class="movie-result-description">${escapeHtml(movie.description)}</div>` : ''}
                            ${movie.genres.length > 0 ? `
                                <div class="movie-result-genres">
                                    ${movie.genres.map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <div class="movie-result-actions">
                            ${movie.exists_in_db ? `
                                <span class="exists-badge">✅ В базе</span>
                            ` : `
                                <button class="btn-import-movie" onclick="importMovie(${movie.id}, '${escapeHtml(movie.title).replace(/'/g, "\\'")}')">
                                    📥 Импортировать
                                </button>
                            `}
                        </div>
                    </div>
                `;
            });

            resultsDiv.innerHTML = html;

            // Обновляем счётчик
            if (typeof updateApiCounter === 'function') {
                updateApiCounter();
            }
        })
        .catch(error => {
            loadingDiv.style.display = 'none';
            resultsDiv.innerHTML = `
                <div class="search-placeholder">
                    <p>❌ Ошибка соединения: ${error.message}</p>
                </div>
            `;
        });
}

// Импорт одного фильма
function importMovie(movieId, title) {
    const messageDiv = document.getElementById('api-message');
    const buttons = document.querySelectorAll('.btn-import-movie');

    // Блокируем все кнопки
    buttons.forEach(btn => btn.disabled = true);

    messageDiv.style.display = 'block';
    messageDiv.className = 'modal-message';
    messageDiv.innerHTML = '⏳ Импортируем фильм...';

    fetch('/manager/api/import-movie/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            movie_id: movieId,
            download_poster: true
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            messageDiv.className = 'modal-message success';
            messageDiv.innerHTML = `
                <strong>${data.message}</strong><br>
                <small>
                    🎭 Жанры: ${data.created.genres.join(', ') || 'нет'}<br>
                    👥 Режиссёры: ${data.created.directors.join(', ') || 'нет'}<br>
                    🎬 Актёры: ${data.created.actors.join(', ') || 'нет'}<br>
                    🖼️ Постер: ${data.created.poster ? '✅ скачан' : '❌ не скачан'}
                </small>
            `;

            // Обновляем кнопку на "В базе"
            const card = document.querySelector(`.btn-import-movie[onclick*="${movieId}"]`)?.closest('.movie-result-card');
            if (card) {
                card.classList.add('exists');
                const actionsDiv = card.querySelector('.movie-result-actions');
                if (actionsDiv) {
                    actionsDiv.innerHTML = '<span class="exists-badge">✅ Импортирован</span>';
                }
            }

            // Обновляем счётчик
            if (typeof updateApiCounter === 'function') {
                updateApiCounter();
            }

            // Автозакрытие через 3 секунды
            setTimeout(() => {
                closeApiImportModal();
                // Обновляем страницу чтобы новый фильм появился в списке
                location.reload();
            }, 3000);

        } else {
            messageDiv.className = 'modal-message error';
            messageDiv.textContent = data.message || 'Ошибка импорта';
        }
    })
    .catch(error => {
        messageDiv.className = 'modal-message error';
        messageDiv.textContent = 'Ошибка соединения: ' + error.message;
    })
    .finally(() => {
        buttons.forEach(btn => btn.disabled = false);
    });
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Получение CSRF токена
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