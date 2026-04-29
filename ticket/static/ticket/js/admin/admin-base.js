// JavaScript для админки
document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin improvements script loaded');

    // 1. Исправляем выравнивание текста в select
    document.querySelectorAll('select').forEach(select => {
        select.style.height = '38px';
        select.style.lineHeight = '38px';
        select.style.paddingTop = '0';
        select.style.paddingBottom = '0';
        select.style.verticalAlign = 'middle';
    });

    // 2. Настраиваем пропорции поиска
    adjustSearchLayout();

    // 3. Добавляем индикаторы прокрутки для таблиц
    addTableScrollIndicators();

    // 4. Выравниваем элементы в отчетах
    alignReportElements();

    // 5. Исправляем кнопки
    fixButtons();

    // Обновляем при изменении размера окна
    window.addEventListener('resize', function() {
        setTimeout(() => {
            adjustSearchLayout();
            addTableScrollIndicators();
        }, 100);
    });
});

// Настройка поиска
function adjustSearchLayout() {
    const searchInput = document.querySelector('#searchbar');
    const searchButton = document.querySelector('#changelist-search button[type="submit"]');

    if (searchInput && searchButton) {
        if (window.innerWidth >= 768) {
            const container = searchInput.parentElement;
            if (container) {
                searchInput.style.flex = '3';
                searchButton.style.flex = '1';
                searchButton.style.minWidth = '120px';
            }
        }
    }
}

// Индикаторы прокрутки для таблиц
function addTableScrollIndicators() {
    const tables = document.querySelectorAll('#result_list');
    tables.forEach(table => {
        const container = table.closest('.results');
        if (container) {
            const oldIndicators = container.querySelectorAll('.scroll-indicator-right, .scroll-indicator-left');
            oldIndicators.forEach(ind => ind.remove());

            if (table.scrollWidth > container.clientWidth) {
                const indicatorRight = document.createElement('div');
                indicatorRight.className = 'scroll-indicator-right';
                indicatorRight.style.cssText = `
                    position: absolute;
                    top: 0;
                    right: 0;
                    bottom: 0;
                    width: 15px;
                    background: linear-gradient(to right, transparent, rgba(255, 0, 0, 0.05));
                    pointer-events: none;
                    z-index: 2;
                    border-radius: 0 6px 6px 0;
                `;
                container.appendChild(indicatorRight);
            }
        }
    });
}

// Выравнивание элементов отчетов
function alignReportElements() {
    document.querySelectorAll('.report-filters select, .report-filters input').forEach(el => {
        el.style.height = '38px';
        el.style.lineHeight = '38px';
        el.style.minWidth = '220px';
    });
}

// Исправление кнопок
function fixButtons() {
    document.querySelectorAll('.button, input[type="submit"], .btn').forEach(btn => {
        btn.style.display = 'inline-flex';
        btn.style.alignItems = 'center';
        btn.style.justifyContent = 'center';
        btn.style.height = '38px';
        btn.style.lineHeight = '1';
        btn.style.padding = '0 20px';
    });
}

// Наблюдатель за изменениями DOM
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
            setTimeout(() => {
                adjustSearchLayout();
                addTableScrollIndicators();
                alignReportElements();
                fixButtons();

                document.querySelectorAll('select').forEach(select => {
                    select.style.height = '38px';
                    select.style.lineHeight = '38px';
                });
            }, 300);
        }
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});