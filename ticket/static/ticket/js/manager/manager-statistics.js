// Скрипты для страницы статистики

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация графиков
    initSalesChart();
    initOccupancyCharts();

    // Обработчики для экспорта
    setupExportHandlers();

    // Обработчики для периода
    setupPeriodHandlers();
});

function initSalesChart() {
    const chartCanvas = document.getElementById('sales-chart');
    if (!chartCanvas) return;

    const data = JSON.parse(chartCanvas.dataset.sales || '[]');
    const maxRevenue = Math.max(...data.map(d => d.revenue), 1);

    const chartContainer = document.createElement('div');
    chartContainer.className = 'sales-chart';

    data.forEach(item => {
        const barHeight = (item.revenue / maxRevenue) * 100;
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        bar.style.height = barHeight + '%';

        const value = document.createElement('span');
        value.className = 'bar-value';
        value.textContent = formatCurrency(item.revenue);

        const label = document.createElement('span');
        label.className = 'bar-label';
        label.textContent = formatDateShort(item.day);

        bar.appendChild(value);
        bar.appendChild(label);
        chartContainer.appendChild(bar);
    });

    chartCanvas.appendChild(chartContainer);
}

function initOccupancyCharts() {
    const occupancyBars = document.querySelectorAll('.occupancy-progress');
    occupancyBars.forEach(bar => {
        const percent = bar.dataset.percent || 0;
        const fill = document.createElement('div');
        fill.className = 'progress-bar-fill';
        fill.style.width = percent + '%';
        bar.appendChild(fill);
    });
}

function setupExportHandlers() {
    const exportButtons = document.querySelectorAll('.export-btn');
    exportButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            const format = this.dataset.format;
            const period = document.querySelector('select[name="period"]')?.value;
            const startDate = document.querySelector('input[name="start_date"]')?.value;
            const endDate = document.querySelector('input[name="end_date"]')?.value;

            try {
                const response = await fetch('/manager/export-statistics/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        format: format,
                        period: period,
                        start_date: startDate,
                        end_date: endDate
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `statistics_${formatDateForFile(new Date())}.${format}`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                } else {
                    alert('Ошибка при экспорте данных');
                }
            } catch (error) {
                console.error('Export error:', error);
                alert('Ошибка при экспорте данных');
            }
        });
    });
}

function setupPeriodHandlers() {
    const periodSelect = document.querySelector('select[name="period"]');
    const startDateInput = document.querySelector('input[name="start_date"]');
    const endDateInput = document.querySelector('input[name="end_date"]');

    if (periodSelect) {
        periodSelect.addEventListener('change', function() {
            const today = new Date();
            const endDate = today.toISOString().split('T')[0];

            switch(this.value) {
                case 'day':
                    startDateInput.value = endDate;
                    endDateInput.value = endDate;
                    break;
                case 'week':
                    const weekAgo = new Date(today);
                    weekAgo.setDate(today.getDate() - 7);
                    startDateInput.value = weekAgo.toISOString().split('T')[0];
                    endDateInput.value = endDate;
                    break;
                case 'month':
                    const monthAgo = new Date(today);
                    monthAgo.setMonth(today.getMonth() - 1);
                    startDateInput.value = monthAgo.toISOString().split('T')[0];
                    endDateInput.value = endDate;
                    break;
            }
        });
    }
}

// Вспомогательные функции
function formatDateShort(dateString) {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${day}.${month}`;
}

function formatDateForFile(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}${month}${day}_${hours}${minutes}`;
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}