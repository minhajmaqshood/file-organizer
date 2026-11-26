/* File Organizer UI — talks only to the local Python service. */
(function () {
    'use strict';

    var $ = function (id) { return document.getElementById(id); };
    var state = { browsePath: '', plan: null, filter: 'all' };

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) { node.className = className; }
        if (text !== undefined && text !== null) { node.textContent = String(text); }
        return node;
    }

    async function api(method, url, body) {
        var opts = { method: method, headers: { Accept: 'application/json' } };
        if (body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        var response = await fetch(url, opts);
        var data;
        try { data = await response.json(); } catch (error) { throw new Error('The local service returned an invalid response.'); }
        if (!response.ok || data.ok === false) { throw new Error(data.message || 'Request failed.'); }
        return data;
    }

    function setStatus(message, isError, busy) {
        var box = $('status');
        if (!message) { box.hidden = true; box.innerHTML = ''; return; }
        box.hidden = false;
        box.className = 'status' + (isError ? ' is-error' : '');
        box.innerHTML = '';
        if (busy) { box.appendChild(el('span', 'spinner')); }
        box.appendChild(el('span', '', message));
    }

    function formatBytes(bytes) {
        var n = Number(bytes) || 0;
        if (n < 1024) { return n + ' B'; }
        var units = ['KB', 'MB', 'GB', 'TB'];
        var i = -1;
        do { n = n / 1024; i += 1; } while (n >= 1024 && i < units.length - 1);
        return n.toFixed(n >= 10 ? 0 : 1) + ' ' + units[i];
    }

    function options() {
        var chosen = document.querySelector('input[name="mode"]:checked');
        return {
            path: $('folderPath').value.trim(),
            mode: chosen ? chosen.value : 'type',
            recursive: $('recursiveInput').checked,
            include_hidden: $('hiddenInput').checked,
            exclude: $('excludeInput').value.trim()
        };
    }

    // ---- folder browser ---------------------------------------------------

    function openBrowser() {
        $('browserModal').hidden = false;
        var current = $('folderPath').value.trim();
        gotoBrowse(current || '');
    }

    function closeBrowser() { $('browserModal').hidden = true; }

    async function gotoBrowse(path) {
        try {
            var data = await api('GET', '/api/browse?path=' + encodeURIComponent(path));
            state.browsePath = data.path;
            $('browserPath').textContent = data.path;
            $('modalPath').value = data.path;
            $('upBtn').disabled = !data.parent;
            $('upBtn').dataset.parent = data.parent || '';
            $('browserInfo').textContent = data.file_count + ' file(s) in this folder';

            var list = $('dirList');
            list.innerHTML = '';
            if (!data.dirs.length) {
                list.appendChild(el('p', 'empty', 'No subfolders here.'));
                return;
            }
            data.dirs.forEach(function (dir) {
                var button = el('button', 'dir-item' + (dir.hidden ? ' is-hidden' : ''));
                button.type = 'button';
                button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l2 2.5h7A2.5 2.5 0 0 1 21 10v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17V7.5Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>';
                button.appendChild(el('span', '', dir.name));
                button.addEventListener('click', function () { gotoBrowse(dir.path); });
                list.appendChild(button);
            });
        } catch (error) {
            setStatus(error.message, true, false);
        }
    }

    // ---- preview ----------------------------------------------------------

    async function preview() {
        $('organizeBtn').disabled = true;
        setStatus('Reading the folder and building the move plan…', false, true);
        try {
            var data = await api('POST', '/api/preview', options());
            state.plan = data;
            state.filter = 'all';
            renderPreview(data);
            $('organizeBtn').disabled = data.count === 0;
            setStatus('');
        } catch (error) {
            state.plan = null;
            $('previewBox').hidden = true;
            setStatus(error.message, true, false);
        }
    }

    function renderPreview(data) {
        $('previewBox').hidden = false;
        $('previewSource').textContent = data.root + ' · grouped ' + data.mode.replace('_', ' + ');

        var summary = $('summary');
        summary.innerHTML = '';
        var cards = [
            { value: data.count, label: 'files will move' },
            { value: formatBytes(data.total_size), label: 'total size' },
            { value: Object.keys(data.by_category).length, label: 'categories used' }
        ];
        cards.forEach(function (card) {
            var item = el('div', 'summary__item');
            item.appendChild(el('strong', '', card.value));
            item.appendChild(el('span', '', card.label));
            summary.appendChild(item);
        });

        var warnings = $('previewWarnings');
        warnings.hidden = !data.warnings || !data.warnings.length;
        warnings.innerHTML = '';
        if (data.warnings && data.warnings.length) {
            warnings.appendChild(el('strong', '', 'Notes'));
            var list = el('ul');
            data.warnings.forEach(function (warning) { list.appendChild(el('li', '', warning)); });
            warnings.appendChild(list);
        }

        var chips = $('categoryChips');
        chips.innerHTML = '';
        var entries = [{ key: 'all', label: 'All files', count: data.count }];
        Object.keys(data.by_category).forEach(function (key) {
            entries.push({ key: key, label: key, count: data.by_category[key] });
        });
        entries.forEach(function (entry) {
            var chip = el('button', 'chip' + (state.filter === entry.key ? ' is-active' : ''));
            chip.type = 'button';
            chip.appendChild(el('span', '', entry.label));
            chip.appendChild(el('span', '', entry.count));
            chip.addEventListener('click', function () {
                state.filter = entry.key;
                Array.prototype.forEach.call(chips.children, function (node, index) {
                    node.classList.toggle('is-active', entries[index].key === state.filter);
                });
                renderRows();
            });
            chips.appendChild(chip);
        });
        renderRows();
    }

    function renderRows() {
        var body = $('planRows');
        body.innerHTML = '';
        var items = (state.plan ? state.plan.items : []).filter(function (item) {
            return state.filter === 'all' || item.category === state.filter;
        });
        items.forEach(function (item) {
            var row = el('tr');
            row.appendChild(el('td', '', item.name));
            var tagCell = el('td');
            tagCell.appendChild(el('span', 'tag', item.category));
            row.appendChild(tagCell);
            row.appendChild(el('td', 'path-cell', item.source));
            row.appendChild(el('td', 'path-cell', item.destination));
            row.appendChild(el('td', 'num', formatBytes(item.size)));
            body.appendChild(row);
        });
        $('planEmpty').hidden = items.length !== 0;
    }

    // ---- organise, history, undo -----------------------------------------

    async function organize() {
        if (!state.plan || !state.plan.count) { return; }
        if (!window.confirm('Move ' + state.plan.count + ' file(s) into new folders now?\n\nYou can undo the whole run from the Recent runs panel.')) { return; }
        setStatus('Moving files…', false, true);
        try {
            var payload = options();
            payload.confirm = true;
            var data = await api('POST', '/api/organize', payload);
            $('resultBox').hidden = false;
            $('resultTitle').textContent = 'Organised ' + data.moved + ' file(s)';
            $('resultText').textContent = 'Folder: ' + data.root + ' · grouped by ' + data.mode.replace('_', ' + ') + ' · undo ID ' + data.log_id;
            var errors = $('resultErrors');
            errors.hidden = !data.failed;
            errors.innerHTML = '';
            if (data.failed) {
                errors.appendChild(el('strong', '', data.failed + ' file(s) could not be moved'));
                var list = el('ul');
                data.errors.forEach(function (error) { list.appendChild(el('li', '', error.name + ': ' + error.error)); });
                errors.appendChild(list);
            }
            $('organizeBtn').disabled = true;
            setStatus('');
            loadHistory();
        } catch (error) {
            setStatus(error.message, true, false);
        }
    }

    async function loadHistory() {
        try {
            var data = await api('GET', '/api/history');
            var entries = data.entries || [];
            $('historyBox').hidden = entries.length === 0;
            var list = $('historyList');
            list.innerHTML = '';
            entries.forEach(function (entry) {
                var item = el('div', 'history-item');
                var info = el('div');
                info.appendChild(el('strong', '', entry.created || entry.id));
                info.appendChild(el('small', '', entry.moved + ' file(s) · ' + (entry.mode || 'type') + ' · ' + entry.root));
                item.appendChild(info);
                var button = el('button', 'small-btn', entry.undone ? 'Undone' : 'Undo this run');
                button.type = 'button';
                button.disabled = entry.undone;
                button.addEventListener('click', function () { undoRun(entry.id); });
                item.appendChild(button);
                list.appendChild(item);
            });
        } catch (error) { /* keep the page usable if history cannot load */ }
    }

    async function undoRun(logId) {
        if (!window.confirm('Put every file from this run back where it was?')) { return; }
        setStatus('Restoring files…', false, true);
        try {
            var data = await api('POST', '/api/undo', { log_id: logId });
            setStatus('Restored ' + data.restored + ' file(s).', false, false);
            loadHistory();
        } catch (error) {
            setStatus(error.message, true, false);
        }
    }

    // ---- wiring -----------------------------------------------------------

    document.addEventListener('DOMContentLoaded', function () {
        $('browseBtn').addEventListener('click', openBrowser);
        $('closeBrowser').addEventListener('click', closeBrowser);
        $('browserModal').querySelector('.modal__backdrop').addEventListener('click', closeBrowser);
        $('upBtn').addEventListener('click', function () { gotoBrowse(this.dataset.parent || ''); });
        $('goBtn').addEventListener('click', function () { gotoBrowse($('modalPath').value.trim()); });
        $('modalPath').addEventListener('keydown', function (event) {
            if (event.key === 'Enter') { gotoBrowse($('modalPath').value.trim()); }
        });
        $('selectFolderBtn').addEventListener('click', function () {
            $('folderPath').value = state.browsePath;
            closeBrowser();
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !$('browserModal').hidden) { closeBrowser(); }
        });

        $('previewBtn').addEventListener('click', preview);
        $('organizeBtn').addEventListener('click', organize);

        api('GET', '/api/status').then(function (data) {
            $('quickRoots').hidden = !data.suggestions.length;
            var list = $('quickList');
            data.suggestions.forEach(function (path) {
                var button = el('button', '', path);
                button.type = 'button';
                button.addEventListener('click', function () { $('folderPath').value = path; });
                list.appendChild(button);
            });
            loadHistory();
        }).catch(function (error) { setStatus(error.message, true, false); });
    });
})();
