(function () {
    var root = document.documentElement;
    var prefUrl = '/preferences/';

    function applyTheme(theme) {
        if (theme !== 'light' && theme !== 'dark') return;
        root.setAttribute('data-theme', theme);
        localStorage.setItem('site_theme', theme);
        document.querySelectorAll('[data-theme-set]').forEach(function (btn) {
            btn.classList.toggle('active', btn.getAttribute('data-theme-set') === theme);
        });
    }

    document.querySelectorAll('[data-theme-set]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var theme = btn.getAttribute('data-theme-set');
            applyTheme(theme);
            fetch(prefUrl + '?theme=' + theme + '&ajax=1', { credentials: 'same-origin' });
        });
    });

    var stored = localStorage.getItem('site_theme');
    if (stored === 'light' || stored === 'dark') {
        applyTheme(stored);
    }

    var toggle = document.getElementById('navToggle');
    var nav = document.getElementById('mainNav');
    function bindNavToggle(toggleEl, navEl) {
        if (!toggleEl || !navEl) return;
        toggleEl.addEventListener('click', function () {
            var open = navEl.classList.toggle('is-open');
            toggleEl.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        navEl.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                navEl.classList.remove('is-open');
                toggleEl.setAttribute('aria-expanded', 'false');
            });
        });
    }

    bindNavToggle(toggle, nav);

    /* Admin sidebar: toggle is-open on the <aside> (CSS target), close on nav-link click */
    (function () {
        var btn = document.getElementById('adminNavToggle');
        var sidebar = document.getElementById('adminSidebar');
        var navEl = document.getElementById('adminSidebarNav');
        var headerSlot = document.getElementById('adminHeaderToggle');
        var sidebarSlot = btn ? btn.parentNode : null;
        if (!btn || !sidebar || !navEl) return;
        /* Create backdrop overlay for mobile */
        var backdrop = document.createElement('div');
        backdrop.className = 'admin-sidebar-backdrop';
        sidebar.parentNode.insertBefore(backdrop, sidebar.nextSibling);
        function closeSidebar() {
            sidebar.classList.remove('is-open');
            btn.setAttribute('aria-expanded', 'false');
        }
        btn.addEventListener('click', function () {
            var open = sidebar.classList.toggle('is-open');
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        navEl.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', closeSidebar);
        });
        backdrop.addEventListener('click', closeSidebar);
        /* Relocate toggle: header on mobile (always visible), sidebar on desktop */
        function placeToggle() {
            if (window.innerWidth <= 860) {
                if (headerSlot && btn.parentNode !== headerSlot) headerSlot.appendChild(btn);
            } else {
                if (sidebarSlot && btn.parentNode !== sidebarSlot) sidebarSlot.appendChild(btn);
                sidebar.classList.remove('is-open');
                btn.setAttribute('aria-expanded', 'false');
            }
        }
        placeToggle();
        var resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(placeToggle, 100);
        });
    })();

    document.querySelectorAll('[data-confirm]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(btn.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    document.querySelectorAll('.message-dismiss').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var box = btn.closest('.message');
            if (box) box.remove();
        });
    });

    var parentInput = document.getElementById('commentParentId');
    var replyHint = document.getElementById('replyHint');
    var replyTarget = document.getElementById('replyTarget');
    var cancelReply = document.getElementById('cancelReply');
    var commentContent = document.getElementById('commentContent');

    document.querySelectorAll('.comment-reply-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            if (!parentInput) return;
            parentInput.value = btn.getAttribute('data-parent-id') || '';
            if (replyTarget) replyTarget.textContent = '@' + (btn.getAttribute('data-username') || '');
            if (replyHint) replyHint.hidden = false;
            if (commentContent) {
                commentContent.focus();
                commentContent.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });

    if (cancelReply) {
        cancelReply.addEventListener('click', function () {
            if (parentInput) parentInput.value = '';
            if (replyHint) replyHint.hidden = true;
        });
    }

    // QR lightbox
    var qrLightbox = document.getElementById('qrLightbox');
    if (!qrLightbox) {
        qrLightbox = document.createElement('div');
        qrLightbox.id = 'qrLightbox';
        qrLightbox.className = 'qr-lightbox';
        qrLightbox.setAttribute('role', 'dialog');
        qrLightbox.setAttribute('aria-label', '二维码放大');
        var closeBtn = document.createElement('button');
        closeBtn.className = 'qr-lightbox-close';
        closeBtn.setAttribute('aria-label', '关闭');
        closeBtn.textContent = '×';
        qrLightbox.appendChild(closeBtn);
        document.body.appendChild(qrLightbox);
    }

    document.querySelectorAll('[data-qr-trigger]').forEach(function (card) {
        card.addEventListener('click', function () {
            var img = card.querySelector('img');
            if (!img) return;
            var clone = img.cloneNode(true);
            clone.removeAttribute('loading');
            clone.style.maxWidth = 'min(360px,85vw)';
            clone.style.maxHeight = 'min(360px,80vh)';
            qrLightbox.querySelectorAll('img').forEach(function (el) { el.remove(); });
            qrLightbox.insertBefore(clone, qrLightbox.firstChild);
            qrLightbox.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        });
    });

    qrLightbox.addEventListener('click', function (e) {
        if (e.target === qrLightbox || e.target.classList.contains('qr-lightbox-close')) {
            qrLightbox.classList.remove('is-open');
            document.body.style.overflow = '';
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && qrLightbox.classList.contains('is-open')) {
            qrLightbox.classList.remove('is-open');
            document.body.style.overflow = '';
        }
    });
})();
