(function () {
    var dataEl = document.getElementById('wheel-data');
    if (!dataEl) return;

    var allItems = JSON.parse(dataEl.textContent);
    var n = allItems.length;
    if (n < 1) return;

    var titleEl = document.getElementById('slotTitle');
    var metaEl = document.getElementById('slotMeta');
    var displayEl = document.getElementById('slotDisplay');
    var screenEl = document.getElementById('slotScreen');
    var scanLine = document.getElementById('scanLine');
    var spinBtn = document.getElementById('spinBtn');
    var resultBox = document.getElementById('wheelResult');
    var resultTitle = document.getElementById('resultTitle');
    var resultMeta = document.getElementById('resultMeta');
    var resultLink = document.getElementById('resultLink');
    var spinAgainBtn = document.getElementById('spinAgainBtn');
    var activeCountEl = document.getElementById('activeCount');
    var excludeToggle = document.getElementById('excludeToggle');
    var excludeList = document.getElementById('excludeList');
    var excludeArrow = document.querySelector('.exclude-arrow');
    var excludeLabels = document.querySelectorAll('.exclude-item');

    var spinning = false;
    var excludedIds = loadExcluded();
    var activeItems = [];

    // ---------- Excluded persistence ----------
    function loadExcluded() {
        try {
            var raw = localStorage.getItem('wheel_excluded');
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function saveExcluded() {
        localStorage.setItem('wheel_excluded', JSON.stringify(excludedIds));
    }

    // ---------- Active items ----------
    function updateActiveItems() {
        activeItems = allItems.filter(function (item) {
            return excludedIds.indexOf(item.id) === -1;
        });
        var count = activeItems.length;
        activeCountEl.textContent = count;

        // Disable spin if fewer than 2 active items
        if (count < 2 && !spinning) {
            spinBtn.disabled = true;
            spinBtn.title = '至少需要保留 2 个选项';
        } else if (!spinning) {
            spinBtn.disabled = false;
            spinBtn.title = '';
        }
    }

    // ---------- Exclude UI ----------
    function syncExcludeUI() {
        excludeLabels.forEach(function (label) {
            var id = parseInt(label.getAttribute('data-id'), 10);
            var cb = label.querySelector('.exclude-checkbox');
            var excluded = excludedIds.indexOf(id) !== -1;
            cb.checked = excluded;
            label.classList.toggle('excluded', excluded);
        });
        updateActiveItems();
    }

    function toggleExclude(id) {
        var idx = excludedIds.indexOf(id);
        if (idx !== -1) {
            excludedIds.splice(idx, 1);
        } else {
            excludedIds.push(id);
        }
        saveExcluded();
        syncExcludeUI();
    }

    // Exclude panel toggle
    var excludeOpen = false;
    excludeToggle.addEventListener('click', function () {
        excludeOpen = !excludeOpen;
        excludeList.classList.toggle('open', excludeOpen);
        excludeArrow.classList.toggle('open', excludeOpen);
    });

    // Bind checkbox changes
    excludeLabels.forEach(function (label) {
        var cb = label.querySelector('.exclude-checkbox');
        cb.addEventListener('change', function () {
            var id = parseInt(label.getAttribute('data-id'), 10);
            var idx = excludedIds.indexOf(id);
            if (cb.checked) {
                if (idx === -1) excludedIds.push(id);
            } else {
                if (idx !== -1) excludedIds.splice(idx, 1);
            }
            saveExcluded();
            syncExcludeUI();

            // Auto-close panel once something is excluded
            if (excludedIds.length > 0 && excludeOpen) {
                excludeOpen = false;
                excludeList.classList.remove('open');
                excludeArrow.classList.remove('open');
            }
        });
    });

    // ---------- Display ----------
    function displayItem(index) {
        var item = activeItems[index];
        if (!item) return;
        titleEl.textContent = item.title || '未知美食';
        metaEl.textContent = (item.location ? '📍 ' + item.location : '') +
            (item.price ? ' · 💰 ' + item.price : '');
    }

    function displayItemByObj(item) {
        if (!item) return;
        titleEl.textContent = item.title || '未知美食';
        metaEl.textContent = (item.location ? '📍 ' + item.location : '') +
            (item.price ? ' · 💰 ' + item.price : '');
    }

    function clearSpinStyles() {
        titleEl.classList.remove('slot-blur', 'slot-landed');
        metaEl.classList.remove('slot-blur', 'slot-landed');
        displayEl.classList.remove('slot-cycling');
        screenEl.classList.remove('loading-shake');
        scanLine.classList.remove('active', 'landed');
    }

    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    // ---------- Spin ----------
    function spin() {
        if (spinning) return;
        // Must have at least 2 active items
        if (activeItems.length < 2) {
            return;
        }

        spinning = true;
        spinBtn.disabled = true;
        resultBox.hidden = true;
        clearSpinStyles();

        var duration = 3200;
        var startTime = performance.now();

        scanLine.classList.add('active');

        function cycle() {
            var now = performance.now();
            var elapsed = now - startTime;
            var progress = Math.min(elapsed / duration, 1);

            var eased = easeOutCubic(progress);
            var interval = 35 + 380 * eased;

            var idx = Math.floor(Math.random() * activeItems.length);
            displayItem(idx);

            if (progress < 0.85) {
                titleEl.classList.add('slot-blur');
                metaEl.classList.add('slot-blur');
                displayEl.classList.add('slot-cycling');
            } else {
                titleEl.classList.remove('slot-blur');
                metaEl.classList.remove('slot-blur');
                displayEl.classList.remove('slot-cycling');
            }

            if (progress > 0.2 && progress < 0.7) {
                screenEl.classList.add('loading-shake');
            } else {
                screenEl.classList.remove('loading-shake');
            }

            if (progress < 1) {
                setTimeout(cycle, interval);
            } else {
                var targetIndex = Math.floor(Math.random() * activeItems.length);
                var picked = activeItems[targetIndex];

                displayItemByObj(picked);
                clearSpinStyles();
                titleEl.classList.add('slot-landed');
                metaEl.classList.add('slot-landed');
                scanLine.classList.remove('active');
                scanLine.classList.add('landed');

                resultTitle.textContent = picked.title || '未知美食';
                resultMeta.textContent = (picked.location ? '📍 ' + picked.location : '') +
                    (picked.price ? ' · 💰 ' + picked.price : '');
                resultLink.href = '/post/' + picked.id + '/';
                resultBox.hidden = false;

                spinning = false;
                spinBtn.disabled = false;

                setTimeout(function () {
                    scanLine.classList.remove('landed');
                }, 800);
            }
        }

        cycle();
    }

    // ---------- Init ----------
    syncExcludeUI();

    // Show a random active item initially
    if (activeItems.length > 0) {
        displayItem(Math.floor(Math.random() * activeItems.length));
    }

    spinBtn.addEventListener('click', spin);
    spinAgainBtn.addEventListener('click', spin);
})();
