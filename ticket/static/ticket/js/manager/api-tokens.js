// Управление API токенами в панели менеджера

function openTokenManager() {
    const modal = document.getElementById('token-manager-modal');
    if (modal) {
        modal.style.display = 'flex';
        loadTokenList();
    }
}

function closeTokenManager() {
    const modal = document.getElementById('token-manager-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Закрытие по клику вне модалки
window.addEventListener('click', function(e) {
    const modal = document.getElementById('token-manager-modal');
    if (e.target === modal) {
        closeTokenManager();
    }
});

// Загрузка списка токенов
function loadTokenList() {
    const listDiv = document.getElementById('token-list');
    const requestsDiv = document.getElementById('last-requests');

    fetch('/manager/api/tokens/info/')
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                listDiv.innerHTML = `<p class="error">❌ ${data.message}</p>`;
                return;
            }

            // Список токенов
            if (data.tokens.length === 0) {
                listDiv.innerHTML = `
                    <div class="no-tokens">
                        <p>😕 Нет добавленных токенов</p>
                        <p class="hint">Добавьте токен выше или проверьте .env файл</p>
                    </div>
                `;
            } else {
                let html = '';
                data.tokens.forEach(token => {
                    const statusColor = token.is_active ? '#4CAF50' : '#F44336';
                    const statusText = token.is_active ? 'Активен' : 'Отключён';
                    const isCurrent = token.is_current;

                   html += `
                        <div class="token-card ${isCurrent ? 'current' : ''}">
                            <div class="token-card-header">
                                <span class="token-card-label">${escapeHtml(token.label)}</span>
                                ${isCurrent ? '<span class="badge badge-current">✅ Текущий</span>' : ''}
                                <span class="badge" style="background: ${statusColor};">${statusText}</span>
                            </div>
                            <div class="token-card-body">
                                <div class="token-card-key">🔑 ${token.token_preview}</div>
                                <div class="token-card-stats">
                                    <span>📊 Сегодня: <strong>${token.requests_today}</strong>/${token.limit}</span>
                                    <span>⭐ Осталось: <strong>${token.remaining}</strong></span>
                                    <span>📈 Всего: ${token.total_requests}</span>
                                </div>
                            </div>
                            <div class="token-card-actions">
                                ${!isCurrent ? `<button class="btn btn-sm" style="background:#4CAF50;" onclick="setCurrentToken(${token.id})">⭐ Сделать текущим</button>` : ''}
                                <button class="btn btn-sm ${token.is_active ? 'btn-warning' : 'btn-success'}" 
                                        onclick="toggleToken(${token.id}, '${token.is_active ? 'deactivate' : 'activate'}')">
                                    ${token.is_active ? '🔴 Отключить' : '🟢 Включить'}
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="deleteToken(${token.id})">
                                    🗑️ Удалить
                                </button>
                            </div>
                        </div>
                    `;
                });
                listDiv.innerHTML = html;
            }

            // Последние запросы
            if (data.last_requests.length > 0) {
                let reqHtml = '<div class="requests-list">';
                data.last_requests.forEach(req => {
                    const icon = req.success ? '✅' : '❌';
                    const time = new Date(req.created_at).toLocaleTimeString('ru-RU');
                    reqHtml += `
                        <div class="request-item">
                            <span>${icon}</span>
                            <span class="request-endpoint">${escapeHtml(req.endpoint || '—')}</span>
                            <span class="request-status">${req.status_code || '—'}</span>
                            <span class="request-token">${escapeHtml(req.token__label || '—')}</span>
                            <span class="request-time">${time}</span>
                        </div>
                    `;
                });
                reqHtml += '</div>';
                requestsDiv.innerHTML = reqHtml;
            } else {
                requestsDiv.innerHTML = '<p class="text-muted">Нет запросов</p>';
            }

            // Обновляем счётчик в шапке
            if (typeof updateApiCounter === 'function') {
                updateApiCounter();
            }
        })
        .catch(error => {
            listDiv.innerHTML = `<p class="error">❌ Ошибка загрузки: ${error.message}</p>`;
        });
}

// Добавить новый токен
function addNewToken() {
    const tokenValue = document.getElementById('new-token-value').value.trim();
    const tokenLabel = document.getElementById('new-token-label').value.trim();
    const messageDiv = document.getElementById('token-message');

    if (!tokenValue) {
        showTokenMessage('Введите значение токена', 'error');
        return;
    }

    messageDiv.style.display = 'block';
    messageDiv.className = 'modal-message';
    messageDiv.textContent = '⏳ Добавляем токен...';

    fetch('/manager/api/tokens/add/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            token: tokenValue,
            label: tokenLabel || undefined
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showTokenMessage(data.message, 'success');
            document.getElementById('new-token-value').value = '';
            document.getElementById('new-token-label').value = '';
            loadTokenList();
        } else {
            showTokenMessage(data.message || 'Ошибка', 'error');
        }
    })
    .catch(error => {
        showTokenMessage('Ошибка соединения: ' + error.message, 'error');
    });
}

// Включить/выключить токен
function toggleToken(tokenId, action) {
    fetch('/manager/api/tokens/toggle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            token_id: tokenId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showTokenMessage(data.message, 'success');
            loadTokenList();
        } else {
            showTokenMessage(data.message || 'Ошибка', 'error');
        }
    })
    .catch(error => {
        showTokenMessage('Ошибка: ' + error.message, 'error');
    });
}

// Удалить токен
function deleteToken(tokenId) {
    if (!confirm('Вы уверены, что хотите удалить этот токен?')) return;

    fetch('/manager/api/tokens/delete/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ token_id: tokenId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showTokenMessage(data.message, 'success');
            loadTokenList();
        } else {
            showTokenMessage(data.message || 'Ошибка', 'error');
        }
    })
    .catch(error => {
        showTokenMessage('Ошибка: ' + error.message, 'error');
    });
}

function showTokenMessage(message, type) {
    const div = document.getElementById('token-message');
    div.style.display = 'block';
    div.className = 'modal-message ' + type;
    div.textContent = message;

    if (type === 'success') {
        setTimeout(() => {
            div.style.display = 'none';
        }, 3000);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

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

function setCurrentToken(tokenId) {
    fetch('/manager/api/tokens/set-current/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ token_id: tokenId })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showTokenMessage(data.message, 'success');
            loadTokenList();
            updateApiCounter();
        }
    });
}