(function () {
    'use strict';

    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function placeholderFor(sel) {
        var p = sel.querySelector('option[value=""]');
        if (p) {
            var t = String(p.textContent || '').replace(/^--?\s*|\s*--?$/g, '').trim();
            if (t) return 'Search / ' + t;
        }
        return 'Type to search...';
    }

    function currentLabel(sel) {
        var o = sel.options[sel.selectedIndex];
        if (!o || o.value === '') return '';
        return o.text;
    }

    function ddify(sel) {
        if (sel.dataset.ddDone) return;
        sel.dataset.ddDone = '1';

        var wrap = document.createElement('div');
        wrap.className = 'dd';
        sel.style.cssText += ';display:none';
        sel.parentNode.insertBefore(wrap, sel);
        wrap.appendChild(sel);

        var inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'dd-input';
        inp.autocomplete = 'off';
        inp.spellcheck = false;
        inp.placeholder = placeholderFor(sel);

        var list = document.createElement('div');
        list.className = 'dd-list';

        wrap.appendChild(inp);
        wrap.appendChild(list);

        if (getComputedStyle(sel.parentNode).display === 'flex') {
            wrap.style.flex = '1 1 0';
            wrap.style.width = 'auto';
        } else {
            wrap.style.width = '100%';
        }

        var navIdx = -1;

        function build() {
            var q = inp.value.toLowerCase();
            var items = [];
            Array.prototype.forEach.call(sel.options, function (o) {
                if (q && o.text.toLowerCase().indexOf(q) === -1) return;
                items.push(o);
            });
            list.innerHTML = '';
            navIdx = -1;
            items.forEach(function (o, i) {
                var d = document.createElement('div');
                d.className = 'dd-item' + (o.value === sel.value && !q ? ' active' : '');
                d.textContent = o.text;
                d.dataset.i = i;
                if (o.value === '') d.className += ' dd-ph';
                d.onmousedown = function (e) { e.preventDefault(); };
                d.onclick = function () {
                    pick(o);
                };
                list.appendChild(d);
            });
            if (!items.length) {
                var e = document.createElement('div');
                e.className = 'dd-empty';
                e.textContent = 'No matches';
                list.appendChild(e);
            }
            return items;
        }

        function pick(o) {
            sel.value = o.value;
            inp.value = o.value === '' ? '' : o.text;
            list.style.display = 'none';
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function open() {
            inp.value = currentLabel(sel);
            build();
            list.style.display = 'block';
            list.scrollTop = 0;
        }

        inp.onfocus = function () {
            closeOthers(wrap);
            open();
        };
        inp.oninput = function () {
            build();
            list.style.display = 'block';
        };
        inp.onkeydown = function (e) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                var n = list.querySelectorAll('.dd-item');
                if (!n.length) return;
                navIdx = (navIdx + 1) % n.length;
                highlight(n, navIdx);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                var m = list.querySelectorAll('.dd-item');
                if (!m.length) return;
                navIdx = (navIdx - 1 + m.length) % m.length;
                highlight(m, navIdx);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                var k = list.querySelectorAll('.dd-item');
                if (navIdx >= 0 && k[navIdx]) {
                    pick(sel.options[parseInt(k[navIdx].dataset.i, 10)]);
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                list.style.display = 'none';
                inp.value = currentLabel(sel);
            }
        };

        function highlight(nodes, i) {
            for (var j = 0; j < nodes.length; j++) {
                nodes[j].classList.toggle('active', j === i);
            }
            if (nodes[i]) nodes[i].scrollIntoView({ block: 'nearest' });
        }

        if (window.MutationObserver) {
            new MutationObserver(function () {
                if (list.style.display === 'block') {
                    build();
                } else {
                    setTimeout(function () { inp.value = currentLabel(sel); }, 0);
                }
            }).observe(sel, { childList: true, subtree: true, characterData: true });
        }

        sel.addEventListener('change', function () {
            if (list.style.display !== 'block') inp.value = currentLabel(sel);
        });

        inp.addEventListener('click', function (e) { e.stopPropagation(); });
    }

    function closeOthers(wrap) {
        var all = document.querySelectorAll('.dd-list');
        for (var i = 0; i < all.length; i++) {
            if (all[i].parentNode !== wrap) all[i].style.display = 'none';
        }
    }

    function ddInit(scope) {
        var root = scope || document;
        var sels = root.querySelectorAll ? root.querySelectorAll('select.dd') : document.querySelectorAll('select.dd');
        for (var i = 0; i < sels.length; i++) ddify(sels[i]);
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest || !e.target.closest('.dd')) closeOthers(null);
    });

    window.ddInit = ddInit;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { ddInit(document); });
    } else {
        ddInit(document);
    }
})();