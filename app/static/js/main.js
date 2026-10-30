// AutoVault Main JavaScript Module — Luxury Dark Automotive & Cyber Security Cockpit

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 2. Chart.js Executive Electric Blue & Cyan Cockpit Theme Defaults
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = '#9EADC2';
        Chart.defaults.borderColor = 'rgba(50, 139, 255, 0.12)';
        Chart.defaults.font.family = "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif";
        Chart.defaults.plugins.tooltip.backgroundColor = '#111C2B';
        Chart.defaults.plugins.tooltip.titleColor = '#39D5F2';
        Chart.defaults.plugins.tooltip.bodyColor = '#F4F7FC';
        Chart.defaults.plugins.tooltip.borderColor = 'rgba(50, 139, 255, 0.35)';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.padding = 12;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.boxPadding = 6;
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
    }

    // 3. Mobile Sidebar Toggle & Drawer Backdrop
    const mobileToggle = document.getElementById('mobileNavToggle');
    const sidebar = document.querySelector('.sidebar');
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('open');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 1024 && sidebar.classList.contains('open')) {
                if (!sidebar.contains(e.target) && e.target !== mobileToggle) {
                    sidebar.classList.remove('open');
                }
            }
        });
    }

    // 4. Modal Handlers
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    };

    // Close modal when clicking on backdrop
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            });
        }
    });

    // 5. Alert notification dismissal
    document.querySelectorAll('.alert-close').forEach(btn => {
        btn.addEventListener('click', function() {
            const alert = this.closest('.alert');
            if (alert) {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-6px)';
                alert.style.transition = 'all 0.22s ease';
                setTimeout(() => alert.remove(), 220);
            }
        });
    });

    // 6. Smooth counter animation for metrics
    const counters = document.querySelectorAll('.animate-counter');
    if (counters.length > 0 && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const target = entry.target;
                    const finalVal = parseFloat(target.getAttribute('data-target') || target.innerText.replace(/[^0-9.]/g, ''));
                    if (!isNaN(finalVal) && finalVal > 0) {
                        animateValue(target, 0, finalVal, 1000);
                    }
                    observer.unobserve(target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(c => observer.observe(c));
    }

    function animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const current = Math.floor(progress * (end - start) + start);
            obj.innerText = current.toLocaleString();
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                obj.innerText = end.toLocaleString();
            }
        };
        window.requestAnimationFrame(step);
    }
});
