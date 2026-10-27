/**
 * MessMate Frontend Core Scripts
 * Handles mobile navigation, sidebar toggle, password visibility, and flash dismissals.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Mobile Navigation for Landing Page
    const navToggleBtn = document.getElementById('nav-toggle-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    if (navToggleBtn && mobileMenu) {
        navToggleBtn.addEventListener('click', function () {
            const isExpanded = navToggleBtn.getAttribute('aria-expanded') === 'true';
            navToggleBtn.setAttribute('aria-expanded', !isExpanded);
            mobileMenu.classList.toggle('open');
        });
    }

    // 2. Flash Messages Auto Dismiss after 6 seconds
    const flashAlerts = document.querySelectorAll('.alert');
    flashAlerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function () {
                if (alert.parentElement) {
                    alert.remove();
                }
            }, 400);
        }, 6000);
    });
});

/**
 * Close mobile dropdown menu upon link selection
 */
function closeMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    const navToggleBtn = document.getElementById('nav-toggle-btn');
    if (mobileMenu && navToggleBtn) {
        mobileMenu.classList.remove('open');
        navToggleBtn.setAttribute('aria-expanded', 'false');
    }
}

/**
 * Toggle Mobile Sidebar Drawer for Dashboard
 */
function toggleSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar && overlay) {
        const isOpen = sidebar.classList.contains('sidebar-open');
        if (isOpen) {
            sidebar.classList.remove('sidebar-open');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        } else {
            sidebar.classList.add('sidebar-open');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }
}

/**
 * Toggle password input field visibility (password <-> text)
 * @param {string} inputId
 */
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';

    // Find sibling toggle button if present to update visual state
    const parentWrapper = input.closest('.input-wrapper');
    if (parentWrapper) {
        const toggleBtn = parentWrapper.querySelector('.password-toggle-btn');
        if (toggleBtn) {
            toggleBtn.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
            if (isPassword) {
                // Slashed eye icon
                toggleBtn.innerHTML = `
                    <svg class="eye-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>
                `;
            } else {
                // Open eye icon
                toggleBtn.innerHTML = `
                    <svg class="eye-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                `;
            }
        }
    }
}
