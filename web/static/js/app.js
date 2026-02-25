/**
 * Routing Engine Management UI - Main JavaScript
 */

// API Helper
const api = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    },

    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    }
};

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Format duration
// Format duration
function formatDuration(minutes) {
    const lang = document.documentElement.getAttribute('data-lang') || 'tr';
    const isEn = lang === 'en';

    if (minutes < 60) return `${Math.round(minutes)} ${isEn ? 'min' : 'dk'}`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}${isEn ? 'h' : 'sa'} ${mins}${isEn ? 'm' : 'dk'}`;
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Add toast container style
    const style = document.createElement('style');
    style.textContent = `
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 20px;
            background: #ffffff;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            color: #1F2937;
            font-size: 14px;
            z-index: 2000;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        .toast-success { border-left: 3px solid #4CAF50; }
        .toast-error { border-left: 3px solid #F44336; }
        .toast-info { border-left: 3px solid #4CAF50; }
    `;
    document.head.appendChild(style);

    const wrapper = document.getElementById('main-wrapper');
    const toggle = document.getElementById('sidebarToggle');
    const collapse = document.getElementById('sidebarCollapse');
    const backdrop = document.getElementById('sidebarBackdrop');

    function toggleSidebar(open) {
        if (!wrapper) return;
        const isDesktop = window.innerWidth >= 992;
        if (isDesktop) {
            if (typeof open === 'boolean') {
                wrapper.classList.toggle('sidebar-collapsed', !open);
            } else {
                wrapper.classList.toggle('sidebar-collapsed');
            }
            return;
        }

        if (typeof open === 'boolean') {
            wrapper.classList.toggle('sidebar-open', open);
        } else {
            wrapper.classList.toggle('sidebar-open');
        }
    }

    if (toggle) {
        toggle.addEventListener('click', () => toggleSidebar());
    }

    if (collapse) {
        collapse.addEventListener('click', () => toggleSidebar(false));
    }

    if (backdrop) {
        backdrop.addEventListener('click', () => toggleSidebar(false));
    }
});
