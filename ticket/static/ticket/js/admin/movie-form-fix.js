/**
 * Улучшение формы фильма в админке
 * - Исправляет проблемы с inline-формами
 * - Добавляет возможность быстрого создания режиссёров/актёров/жанров
 */

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        fixInlineForms();
        addQuickCreateButtons();
        highlightValidationErrors();
    }, 100);
});

/**
 * Исправление проблем с inline-формами
 */
function fixInlineForms() {
    // Находим все inline-группы
    const inlineGroups = document.querySelectorAll('.inline-group');

    inlineGroups.forEach(group => {
        // Проверяем наличие management форм
        const totalFormsInput = group.querySelector('input[name$="-TOTAL_FORMS"]');
        const initialFormsInput = group.querySelector('input[name$="-INITIAL_FORMS"]');

        if (!totalFormsInput || !initialFormsInput) {
            console.warn('Management forms missing, will try to fix');

            // Определяем тип инлайна по заголовку
            let prefix = '';
            const header = group.querySelector('h2, h3');
            if (header) {
                const headerText = header.textContent;
                if (headerText.includes('Жанр')) {
                    prefix = 'moviegenre_set';
                } else if (headerText.includes('Режиссёр')) {
                    prefix = 'moviedirector_set';
                } else if (headerText.includes('Актёр')) {
                    prefix = 'movieactor_set';
                }
            }

            // Если нашли префикс, создаём management поля
            if (prefix) {
                // Создаём скрытые поля, если их нет
                if (!totalFormsInput) {
                    const newTotalForms = document.createElement('input');
                    newTotalForms.type = 'hidden';
                    newTotalForms.name = `${prefix}-TOTAL_FORMS`;
                    newTotalForms.value = '1';
                    group.appendChild(newTotalForms);
                }

                if (!initialFormsInput) {
                    const newInitialForms = document.createElement('input');
                    newInitialForms.type = 'hidden';
                    newInitialForms.name = `${prefix}-INITIAL_FORMS`;
                    newInitialForms.value = '0';
                    group.appendChild(newInitialForms);
                }

                // Добавляем MIN_NUM_FORMS и MAX_NUM_FORMS
                const minNumInput = group.querySelector(`input[name$="-MIN_NUM_FORMS"]`);
                if (!minNumInput) {
                    const newMinNum = document.createElement('input');
                    newMinNum.type = 'hidden';
                    newMinNum.name = `${prefix}-MIN_NUM_FORMS`;
                    newMinNum.value = '0';
                    group.appendChild(newMinNum);
                }

                const maxNumInput = group.querySelector(`input[name$="-MAX_NUM_FORMS"]`);
                if (!maxNumInput) {
                    const newMaxNum = document.createElement('input');
                    newMaxNum.type = 'hidden';
                    newMaxNum.name = `${prefix}-MAX_NUM_FORMS`;
                    newMaxNum.value = '10';
                    group.appendChild(newMaxNum);
                }
            }
        }
    });

    // Добавляем обработчики для кнопок "Добавить ещё"
    const addButtons = document.querySelectorAll('.add-row a');
    addButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            setTimeout(fixInlineForms, 50);
        });
    });
}

/**
 * Добавление кнопок быстрого создания
 */
function addQuickCreateButtons() {
    // Добавляем кнопку для режиссёров
    addQuickCreateButtonForInline('director', 'Режиссёра', '/admin/ticket/director/add/');

    // Добавляем кнопку для актёров
    addQuickCreateButtonForInline('actor', 'Актёра', '/admin/ticket/actor/add/');

    // Добавляем кнопку для жанров
    addQuickCreateButtonForInline('genre', 'Жанр', '/admin/ticket/genre/add/');
}

function addQuickCreateButtonForInline(type, label, addUrl) {
    // Ищем инлайн по заголовку
    let inlineHeader = null;
    let targetInline = null;

    const inlineGroups = document.querySelectorAll('.inline-group');

    for (let group of inlineGroups) {
        const header = group.querySelector('h2, h3');
        if (header) {
            const headerText = header.textContent;
            if (type === 'director' && headerText.includes('Режиссёр')) {
                inlineHeader = header;
                targetInline = group;
                break;
            } else if (type === 'actor' && headerText.includes('Актёр')) {
                inlineHeader = header;
                targetInline = group;
                break;
            } else if (type === 'genre' && headerText.includes('Жанр')) {
                inlineHeader = header;
                targetInline = group;
                break;
            }
        }
    }

    if (!inlineHeader || !targetInline) return;

    // Проверяем, есть ли уже кнопка
    if (targetInline.querySelector('.quick-add-btn')) return;

    // Создаём кнопку
    const button = document.createElement('a');
    button.href = addUrl + '?_popup=1';
    button.className = 'button quick-add-btn';
    button.textContent = `➕ Быстрое добавление ${label}`;
    button.style.cssText = `
        display: inline-block;
        margin-left: 15px;
        background: #4a00e0;
        color: white;
        padding: 4px 10px;
        border-radius: 4px;
        text-decoration: none;
        font-size: 11px;
        vertical-align: middle;
        cursor: pointer;
    `;

    button.addEventListener('click', function(e) {
        e.preventDefault();

        const width = 800;
        const height = 600;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;

        const popup = window.open(
            addUrl + '?_popup=1',
            'quickAddPopup',
            `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
        );

        const checkPopup = setInterval(function() {
            if (popup.closed) {
                clearInterval(checkPopup);
                location.reload();
            }
        }, 500);
    });

    inlineHeader.appendChild(button);
}

/**
 * Подсветка полей с ошибками валидации
 */
function highlightValidationErrors() {
    const errorList = document.querySelector('.errorlist');
    if (!errorList) return;

    const errors = errorList.querySelectorAll('li');
    errors.forEach(error => {
        const errorText = error.textContent;

        const fieldMappings = {
            'название': 'title',
            'год': 'release_year',
            'длительность': 'duration',
            'описание': 'description',
            'рейтинг': 'age_rating',
            'постер': 'poster',
            'жанр': 'genre'
        };

        for (const [keyword, fieldName] of Object.entries(fieldMappings)) {
            if (errorText.toLowerCase().includes(keyword)) {
                const fieldElement = document.querySelector(`.field-${fieldName}`);
                if (fieldElement) {
                    fieldElement.style.border = '2px solid #f44336';
                    fieldElement.style.backgroundColor = 'rgba(244, 67, 54, 0.1)';
                }
                break;
            }
        }
    });
}

// Добавляем обработчик для отправки формы, чтобы убедиться, что management поля на месте
const form = document.querySelector('form');
if (form) {
    form.addEventListener('submit', function() {
        fixInlineForms();
    });
}