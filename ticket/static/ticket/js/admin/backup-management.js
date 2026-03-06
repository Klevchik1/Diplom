// JavaScript для управления бэкапами
document.addEventListener('DOMContentLoaded', function() {
    console.log('Backup management script loaded');

    // Устанавливаем максимальную дату как сегодня
    const dateInput = document.getElementById('backup_date');
    if (dateInput) {
        dateInput.max = new Date().toISOString().split('T')[0];
    }
});

let currentBackupId = null;
let currentBackupName = '';

// Переключение отображения лога
function toggleLog(backupId) {
    const logElement = document.getElementById('log-' + backupId);
    const toggleElement = logElement.previousElementSibling;

    if (logElement.style.display === 'block') {
        logElement.style.display = 'none';
        toggleElement.textContent = '📋 Показать лог восстановления';
    } else {
        logElement.style.display = 'block';
        toggleElement.textContent = '📋 Скрыть лог восстановления';
    }
}

// Подтверждение восстановления
function confirmRestore(backupId, backupName) {
    currentBackupId = backupId;
    currentBackupName = backupName;

    document.getElementById('backupName').textContent = backupName;
    document.getElementById('confirmModal').style.display = 'block';
}

// Закрытие модального окна
function closeModal() {
    document.getElementById('confirmModal').style.display = 'none';
    currentBackupId = null;
    currentBackupName = '';
}

// Выполнение восстановления
function performRestore() {
    const restoreBtn = document.getElementById('restoreBtn');
    restoreBtn.disabled = true;
    restoreBtn.innerHTML = '⏳ Восстановление...';

    fetch(`/admin/ticket/backupmanager/restore-backup/${currentBackupId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('✅ Восстановление начато. Проверьте статус на странице.');
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        } else {
            alert('❌ Ошибка: ' + data.message);
            restoreBtn.disabled = false;
            restoreBtn.innerHTML = '🔄 Да, восстановить БД';
        }
        closeModal();
    })
    .catch(error => {
        alert('❌ Ошибка сети: ' + error);
        restoreBtn.disabled = false;
        restoreBtn.innerHTML = '🔄 Да, восстановить БД';
        closeModal();
    });
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

// Закрытие модального окна при клике вне его
window.onclick = function(event) {
    const modal = document.getElementById('confirmModal');
    if (event.target == modal) {
        closeModal();
    }
}