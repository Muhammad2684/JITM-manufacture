(function () {
    var MATH_RE = /^[\d+\-*/().\s]+$/;

    function evalExpr(s) {
        s = (s || '').trim();
        var expr = s.charAt(0) === '=' ? s.slice(1) : s;
        if (!expr || !/[+\-*/]/.test(expr)) return null;
        if (!MATH_RE.test(expr)) return null;
        try {
            var v = Function('"use strict";return (' + expr + ')')();
            if (typeof v !== 'number' || !isFinite(v)) return null;
            return Math.round(v * 1e6) / 1e6;
        } catch (e) { return null; }
    }

    function tryCalc(t) {
        if (!t || t.tagName !== 'INPUT') return;
        var typ = t.type || 'text';
        if (typ === 'date' || typ === 'hidden' || typ === 'checkbox' || typ === 'radio' || typ === 'file' || typ === 'password') return;
        var raw;
        if (typ === 'number') {
            raw = (t.validity && t.validity.badInput) ? (t._raw !== undefined ? t._raw : '') : t.value;
        } else {
            raw = t.value;
        }
        if (!raw || !raw.trim()) return;
        if (typ !== 'number' && raw.charAt(0) !== '=') return;
        var r = evalExpr(raw);
        if (r === null) return;
        if (typ === 'number') { t.value = r; t._raw = String(r); }
        else t.value = String(r);
        t.dispatchEvent(new Event('input', { bubbles: true }));
        t.dispatchEvent(new Event('change', { bubbles: true }));
    }

    document.addEventListener('focus', function (e) {
        var t = e.target;
        if (t && t.tagName === 'INPUT' && t.type === 'number') t._raw = t.value;
    }, true);

    document.addEventListener('blur', function (e) {
        tryCalc(e.target);
    }, true);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.target && e.target.tagName === 'INPUT') tryCalc(e.target);
    });

    document.addEventListener('beforeinput', function (e) {
        var t = e.target;
        if (!t || t.tagName !== 'INPUT' || t.type !== 'number') return;
        var cur = t._raw !== undefined ? t._raw : t.value;
        var pos = t.selectionStart != null ? t.selectionStart : cur.length;
        var end = t.selectionEnd != null ? t.selectionEnd : pos;
        var d = e.data || '';
        if (e.inputType === 'insertText' || e.inputType === 'insertFromPaste' || e.inputType === 'insertFromDrop' || e.inputType === 'insertCompositionText') {
            cur = cur.slice(0, pos) + d + cur.slice(end);
        } else if (e.inputType === 'deleteContentBackward') {
            cur = pos === end ? cur.slice(0, Math.max(0, pos - 1)) + cur.slice(pos) : cur.slice(0, pos) + cur.slice(end);
        } else if (e.inputType === 'deleteContentForward') {
            cur = pos === end ? cur.slice(0, pos) + cur.slice(pos + 1) : cur.slice(0, pos) + cur.slice(end);
        } else {
            return;
        }
        t._raw = cur;
    });

    document.addEventListener('input', function (e) {
        var t = e.target;
        if (t && t.tagName === 'INPUT' && t.type === 'number' && t.validity && !t.validity.badInput) t._raw = t.value;
    });
})();
