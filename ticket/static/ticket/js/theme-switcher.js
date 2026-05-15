// Переключатель тем — единый для всего проекта
(function() {
    const THEME_KEY = 'cinema-theme';

    function getSystemTheme() {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }

    function getTheme() {
        const saved = localStorage.getItem(THEME_KEY);
        if (saved === 'light' || saved === 'dark') return saved;
        return getSystemTheme();
    }

    function applyTheme(theme) {
        if (theme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        localStorage.setItem(THEME_KEY, theme);
    }

    function toggleTheme() {
        const current = getTheme();
        const next = current === 'light' ? 'dark' : 'light';
        applyTheme(next);
    }

    // Применяем тему при загрузке
    applyTheme(getTheme());

    // Слушаем изменения localStorage из других вкладок
    window.addEventListener('storage', function(e) {
        if (e.key === THEME_KEY && e.newValue) {
            applyTheme(e.newValue);
        }
    });

    window.toggleTheme = toggleTheme;
    window.getTheme = getTheme;
    window.applyTheme = applyTheme;
})();