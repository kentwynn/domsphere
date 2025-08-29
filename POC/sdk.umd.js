(function (global, factory) {
    typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
    typeof define === 'function' && define.amd ? define(['exports'], factory) :
    (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.DomSphereSDK = {}));
})(this, (function (exports) { 'use strict';

    /******************************************************************************
    Copyright (c) Microsoft Corporation.

    Permission to use, copy, modify, and/or distribute this software for any
    purpose with or without fee is hereby granted.

    THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
    REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
    INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
    LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
    OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
    PERFORMANCE OF THIS SOFTWARE.
    ***************************************************************************** */
    /* global Reflect, Promise, SuppressedError, Symbol, Iterator */


    function __awaiter(thisArg, _arguments, P, generator) {
        function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
        return new (P || (P = Promise))(function (resolve, reject) {
            function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
            function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
            function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
            step((generator = generator.apply(thisArg, _arguments || [])).next());
        });
    }

    typeof SuppressedError === "function" ? SuppressedError : function (error, suppressed, message) {
        var e = new Error(message);
        return e.name = "SuppressedError", e.error = error, e.suppressed = suppressed, e;
    };

    function postJson(baseUrl_1, path_1, body_1) {
        return __awaiter(this, arguments, void 0, function* (baseUrl, path, body, headers = {}) {
            const res = yield fetch(new URL(path, baseUrl).toString(), {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, headers),
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const text = yield res.text().catch(() => '');
                throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
            }
            return (yield res.json());
        });
    }
    function getJson(baseUrl_1, path_1) {
        return __awaiter(this, arguments, void 0, function* (baseUrl, path, headers = {}) {
            const res = yield fetch(new URL(path, baseUrl).toString(), {
                method: 'GET',
                headers: Object.assign({ 'Content-Type': 'application/json' }, headers),
            });
            if (!res.ok) {
                const text = yield res.text().catch(() => '');
                throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
            }
            return (yield res.json());
        });
    }
    function createApi(opts) {
        const { baseUrl = 'http://localhost:4000', contractVersion = null, requestIdFactory, fetchHeaders = {}, } = opts;
        const headers = () => (Object.assign({ 'X-Contract-Version': contractVersion !== null && contractVersion !== void 0 ? contractVersion : undefined, 'X-Request-Id': requestIdFactory === null || requestIdFactory === void 0 ? void 0 : requestIdFactory() }, fetchHeaders));
        return {
            ruleCheck: (body) => postJson(baseUrl, '/rule/check', body, headers()),
            suggestGet: (body) => postJson(baseUrl, '/suggest/get', body, headers()),
            ruleTrackGet: () => getJson(baseUrl, '/rule/track', headers()),
        };
    }

    class Emitter {
        constructor() {
            this.m = new Map();
        }
        on(evt, fn) {
            if (!this.m.has(evt))
                this.m.set(evt, new Set());
            const set = this.m.get(evt);
            if (set)
                set.add(fn);
            else
                this.m.set(evt, new Set([fn]));
            return () => this.off(evt, fn);
        }
        off(evt, fn) {
            var _a;
            (_a = this.m.get(evt)) === null || _a === void 0 ? void 0 : _a.delete(fn);
        }
        emit(evt, ...a) {
            var _a;
            (_a = this.m.get(evt)) === null || _a === void 0 ? void 0 : _a.forEach((fn) => {
                try {
                    fn(...a);
                }
                catch (_a) {
                    /* empty */
                }
            });
        }
    }

    function safeStr(v) {
        if (v == null)
            return null;
        try {
            const t = typeof v;
            if (t === 'string')
                return v;
            if (t === 'number' || t === 'boolean')
                return String(v);
            const s = JSON.stringify(v);
            return s.length > 5000 ? s.slice(0, 5000) : s;
        }
        catch (_a) {
            return null;
        }
    }
    function cssPath(el) {
        try {
            const parts = [];
            let node = el;
            while (node && node.nodeType === 1) {
                const name = node.nodeName.toLowerCase();
                let selector = name;
                if (node.id) {
                    selector += `#${node.id}`;
                    parts.unshift(selector);
                    break;
                }
                else {
                    let sib = node;
                    let nth = 1;
                    while ((sib = sib.previousElementSibling)) {
                        if (sib.nodeName.toLowerCase() === name)
                            nth++;
                    }
                    selector += `:nth-of-type(${nth})`;
                }
                parts.unshift(selector);
                node = node.parentElement;
            }
            return parts.join(' > ');
        }
        catch (_a) {
            return null;
        }
    }
    function xPath(el) {
        try {
            if (document.evaluate) {
                const xpath = (start) => {
                    let node = start;
                    if (node === document.body)
                        return '/html/body';
                    const ix = (sibling, name) => {
                        let i = 1;
                        for (; sibling; sibling = sibling.previousSibling) {
                            if (sibling.nodeName === name)
                                i++;
                        }
                        return i;
                    };
                    const segs = [];
                    for (; node && node.nodeType === 1;) {
                        const cur = node;
                        const name = node.nodeName.toLowerCase();
                        segs.unshift(`${name}[${ix(node, name.toUpperCase())}]`);
                        node = cur.parentElement;
                    }
                    return '/' + segs.join('/');
                };
                return xpath(el);
            }
            return null;
        }
        catch (_a) {
            return null;
        }
    }
    function attrMap(el) {
        var _a;
        const out = {};
        try {
            for (const a of Array.from(el.attributes)) {
                out[a.name] = (_a = a.value) !== null && _a !== void 0 ? _a : null;
            }
        }
        catch (_b) {
            /* empty */
        }
        return out;
    }
    function nearbyText(el) {
        const texts = [];
        try {
            const grab = (node) => {
                if (node.nodeType === Node.TEXT_NODE) {
                    const t = (node.textContent || '').trim();
                    if (t)
                        texts.push(t);
                }
            };
            if (el.parentElement) {
                Array.from(el.parentElement.childNodes).forEach((n) => grab(n));
            }
            return texts.slice(0, 5);
        }
        catch (_a) {
            return [];
        }
    }
    function ancestorBrief(el) {
        const arr = [];
        try {
            let p = el.parentElement;
            let i = 0;
            while (p && i < 6) {
                arr.push({
                    tag: p.tagName || null,
                    id: p.id || null,
                    class: p.getAttribute('class') || null,
                });
                p = p.parentElement;
                i++;
            }
        }
        catch (_a) {
            /* empty */
        }
        return arr;
    }
    function firstInt(text) {
        if (!text)
            return null;
        const m = text.match(/\d+/);
        if (!m)
            return null;
        const n = parseInt(m[0], 10);
        return Number.isFinite(n) ? n : null;
    }

    function renderAskTurn(container, turn, onAction, onSubmitForm) {
        var _a, _b, _c, _d;
        container.innerHTML = '';
        const panel = document.createElement('div');
        panel.style.border = '1px solid #e5e7eb';
        panel.style.borderRadius = '12px';
        panel.style.padding = '12px';
        panel.style.margin = '8px 0';
        if (turn.message) {
            const msg = document.createElement('div');
            msg.textContent = turn.message;
            msg.style.fontWeight = '600';
            panel.appendChild(msg);
        }
        if ((_a = turn.actions) === null || _a === void 0 ? void 0 : _a.length) {
            const row = document.createElement('div');
            row.style.display = 'flex';
            row.style.flexWrap = 'wrap';
            row.style.gap = '8px';
            row.style.marginTop = '10px';
            turn.actions.forEach((a) => {
                const btn = document.createElement('button');
                btn.textContent = a.label;
                btn.onclick = () => onAction(a);
                btn.style.padding = '6px 10px';
                btn.style.borderRadius = '8px';
                btn.style.border = '1px solid #d1d5db';
                row.appendChild(btn);
            });
            panel.appendChild(row);
        }
        if ((_c = (_b = turn.form) === null || _b === void 0 ? void 0 : _b.fields) === null || _c === void 0 ? void 0 : _c.length) {
            const form = document.createElement('form');
            form.style.marginTop = '12px';
            if (turn.form.title) {
                const title = document.createElement('div');
                title.textContent = turn.form.title;
                title.style.fontWeight = '600';
                form.appendChild(title);
            }
            turn.form.fields.forEach((f) => {
                var _a, _b;
                const wrap = document.createElement('div');
                wrap.style.marginTop = '8px';
                const label = document.createElement('label');
                label.textContent = f.label + (f.required ? ' *' : '');
                label.style.display = 'block';
                label.style.marginBottom = '4px';
                wrap.appendChild(label);
                let input;
                switch (f.type) {
                    case 'textarea': {
                        const el = document.createElement('textarea');
                        el.name = f.key;
                        el.required = !!f.required;
                        // Placeholder not part of strict spec; omit to keep types safe
                        input = el;
                        break;
                    }
                    case 'select': {
                        const el = document.createElement('select');
                        el.name = f.key;
                        el.required = !!f.required;
                        ((_a = f.options) !== null && _a !== void 0 ? _a : []).forEach((opt) => {
                            var _a;
                            const o = document.createElement('option');
                            o.value = String(opt.value);
                            o.textContent = (_a = opt.label) !== null && _a !== void 0 ? _a : String(opt.value);
                            el.appendChild(o);
                        });
                        input = el;
                        break;
                    }
                    case 'radio': {
                        const group = document.createElement('div');
                        ((_b = f.options) !== null && _b !== void 0 ? _b : []).forEach((opt) => {
                            var _a;
                            const wrapRadio = document.createElement('label');
                            wrapRadio.style.marginRight = '8px';
                            const r = document.createElement('input');
                            r.type = 'radio';
                            r.name = f.key;
                            r.value = String(opt.value);
                            wrapRadio.appendChild(r);
                            wrapRadio.appendChild(document.createTextNode((_a = opt.label) !== null && _a !== void 0 ? _a : String(opt.value)));
                            group.appendChild(wrapRadio);
                        });
                        input = group;
                        break;
                    }
                    default: {
                        const el = document.createElement('input');
                        el.type = 'text';
                        el.name = f.key;
                        input = el;
                    }
                }
                wrap.appendChild(input);
                form.appendChild(wrap);
            });
            const submit = document.createElement('button');
            submit.type = 'submit';
            submit.textContent = (_d = turn.form.submitLabel) !== null && _d !== void 0 ? _d : 'Continue';
            submit.style.marginTop = '10px';
            submit.style.padding = '6px 10px';
            submit.style.borderRadius = '8px';
            submit.style.border = '1px solid #d1d5db';
            form.appendChild(submit);
            form.onsubmit = (e) => {
                e.preventDefault();
                const fd = new FormData(form);
                onSubmitForm === null || onSubmitForm === void 0 ? void 0 : onSubmitForm(fd);
            };
            panel.appendChild(form);
        }
        container.appendChild(panel);
    }
    function renderFinalSuggestions(container, suggestions, onCta, _turn) {
        container.innerHTML = '';
        if (!(suggestions === null || suggestions === void 0 ? void 0 : suggestions.length)) {
            container.innerHTML = `<div data-testid="assistant-empty">No suggestions</div>`;
            return;
        }
        const frag = document.createDocumentFragment();
        suggestions.forEach((s) => {
            var _a, _b;
            const card = document.createElement('div');
            card.setAttribute('data-testid', 'assistant-card');
            card.style.border = '1px solid #e5e7eb';
            card.style.borderRadius = '12px';
            card.style.padding = '12px';
            card.style.margin = '8px 0';
            const title = document.createElement('div');
            title.textContent = (_a = s.title) !== null && _a !== void 0 ? _a : s.type;
            title.style.fontWeight = '600';
            card.appendChild(title);
            if (s.description) {
                const desc = document.createElement('div');
                desc.textContent = s.description;
                desc.style.opacity = '0.9';
                desc.style.marginTop = '4px';
                card.appendChild(desc);
            }
            const actions = [
                ...((_b = s.actions) !== null && _b !== void 0 ? _b : []),
                ...(s.primaryCta ? [s.primaryCta] : []),
            ].filter(Boolean);
            if (actions.length) {
                const row = document.createElement('div');
                row.style.display = 'flex';
                row.style.flexWrap = 'wrap';
                row.style.gap = '8px';
                row.style.marginTop = '10px';
                actions.forEach((cta, idx) => {
                    const btn = document.createElement('button');
                    btn.textContent = cta.label;
                    btn.setAttribute('data-cta-idx', String(idx));
                    btn.onclick = () => onCta(cta);
                    btn.style.padding = '6px 10px';
                    btn.style.borderRadius = '8px';
                    btn.style.border = '1px solid #d1d5db';
                    row.appendChild(btn);
                });
                card.appendChild(row);
            }
            frag.appendChild(card);
        });
        container.appendChild(frag);
    }

    class AutoAssistant {
        constructor(options) {
            var _a, _b;
            this.bus = new Emitter();
            this.detachFns = [];
            this.inflight = false;
            this.lastContext = {
                matchedRules: [],
                eventType: 'page_load',
            };
            this.cooldownUntil = 0;
            this.trackOn = false;
            this.selClick = [];
            this.selMutation = [];
            this.opts = Object.assign({ debounceMs: (_a = options.debounceMs) !== null && _a !== void 0 ? _a : 150, finalCooldownMs: (_b = options.finalCooldownMs) !== null && _b !== void 0 ? _b : 30000 }, options);
            this.api = createApi(options);
        }
        on(evt, fn) {
            return this.bus.on(evt, fn);
        }
        matchesAny(target, selectors) {
            if (!target)
                return false;
            for (const sel of selectors) {
                try {
                    if (target.closest(sel))
                        return true;
                }
                catch (_a) {
                    /* invalid selector */
                }
            }
            return false;
        }
        start() {
            return __awaiter(this, void 0, void 0, function* () {
                try {
                    const prof = yield this.api.ruleTrackGet();
                    this.trackProfile = prof;
                    this.trackOn = (prof === null || prof === void 0 ? void 0 : prof.status) === 'on';
                    const ev = ((prof === null || prof === void 0 ? void 0 : prof.events) || {});
                    this.selClick = Array.isArray(ev['dom_click']) ? ev['dom_click'] : [];
                    this.selMutation = Array.isArray(ev['mutation']) ? ev['mutation'] : [];
                }
                catch (_a) {
                    this.trackOn = false; // rich mode fallback
                    this.selClick = [];
                    this.selMutation = [];
                }
                if (!this.trackOn) {
                    this.schedule(() => this.handleEvent('page_load', document.body || undefined));
                }
                const onClick = (e) => {
                    const tgt = e.target;
                    if (this.trackOn && !this.matchesAny(tgt, this.selClick))
                        return;
                    this.schedule(() => this.handleEvent('dom_click', tgt));
                };
                document.addEventListener('click', onClick, true);
                this.detachFns.push(() => document.removeEventListener('click', onClick, true));
                const onChange = (e) => {
                    if (this.trackOn)
                        return;
                    this.schedule(() => this.handleEvent('input_change', e.target));
                };
                document.addEventListener('input', onChange, true);
                document.addEventListener('change', onChange, true);
                this.detachFns.push(() => document.removeEventListener('input', onChange, true));
                this.detachFns.push(() => document.removeEventListener('change', onChange, true));
                const onSubmit = (e) => {
                    if (this.trackOn)
                        return;
                    this.schedule(() => this.handleEvent('submit', e.target));
                };
                document.addEventListener('submit', onSubmit, true);
                this.detachFns.push(() => document.removeEventListener('submit', onSubmit, true));
                const _push = history.pushState;
                const _replace = history.replaceState;
                history.pushState = function (data, unused, url) {
                    const r = _push.apply(this, [data, unused, url]);
                    window.dispatchEvent(new Event('agent-route-change'));
                    return r;
                };
                history.replaceState = function (data, unused, url) {
                    const r = _replace.apply(this, [data, unused, url]);
                    window.dispatchEvent(new Event('agent-route-change'));
                    return r;
                };
                const onPop = () => {
                    if (this.trackOn)
                        return;
                    this.schedule(() => this.handleEvent('route_change', undefined));
                };
                window.addEventListener('popstate', onPop);
                window.addEventListener('agent-route-change', onPop);
                this.detachFns.push(() => {
                    window.removeEventListener('popstate', onPop);
                    window.removeEventListener('agent-route-change', onPop);
                    history.pushState = _push;
                    history.replaceState = _replace;
                });
                try {
                    const pickTarget = (n) => {
                        if (!n)
                            return undefined;
                        if (n.nodeType === Node.ELEMENT_NODE)
                            return n;
                        if (n.nodeType === Node.TEXT_NODE)
                            return (n.parentElement || undefined);
                        return undefined;
                    };
                    const mutObserver = new MutationObserver((muts) => {
                        var _a;
                        const raw = (_a = muts[0]) === null || _a === void 0 ? void 0 : _a.target;
                        const tgt = pickTarget(raw);
                        if (this.trackOn && !this.matchesAny(tgt, this.selMutation))
                            return;
                        this.schedule(() => this.handleEvent('dom_click', tgt));
                    });
                    mutObserver.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true,
                    });
                    this.detachFns.push(() => mutObserver.disconnect());
                }
                catch (_b) {
                    // ignore if observer cannot start
                }
            });
        }
        stop() {
            this.detachFns.forEach((f) => {
                try {
                    f();
                }
                catch (_a) {
                    /* empty */
                }
            });
            this.detachFns = [];
            if (this.debTimer)
                window.clearTimeout(this.debTimer);
        }
        answerAsk(turn, action) {
            return __awaiter(this, void 0, void 0, function* () {
                try {
                    const { siteId, sessionId, baseContext } = this.opts;
                    const req = {
                        siteId,
                        sessionId,
                        prevTurnId: turn.turnId,
                        answers: {
                            choice: action.id,
                            value: isActionWithValue(action) ? action.value : undefined,
                        },
                        context: Object.assign({}, (baseContext !== null && baseContext !== void 0 ? baseContext : {})),
                    };
                    const { turn: next } = yield this.api.suggestGet(req);
                    this.setActiveTurn(next);
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
            });
        }
        answerForm(turn, formData) {
            return __awaiter(this, void 0, void 0, function* () {
                try {
                    const { siteId, sessionId, baseContext } = this.opts;
                    const answers = {};
                    const keys = [];
                    formData.forEach((_, key) => {
                        if (!keys.includes(key))
                            keys.push(key);
                    });
                    for (const key of keys) {
                        const values = formData.getAll(key);
                        answers[key] =
                            values.length === 1
                                ? values[0] instanceof File
                                    ? values[0].name
                                    : values[0]
                                : values.map((v) => (v instanceof File ? v.name : v));
                    }
                    const req = {
                        siteId,
                        sessionId,
                        prevTurnId: turn.turnId,
                        answers,
                        context: Object.assign({}, (baseContext !== null && baseContext !== void 0 ? baseContext : {})),
                    };
                    const { turn: next } = yield this.api.suggestGet(req);
                    this.setActiveTurn(next);
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
            });
        }
        schedule(fn) {
            if (this.debTimer)
                window.clearTimeout(this.debTimer);
            this.debTimer = window.setTimeout(fn, this.opts.debounceMs);
        }
        canOpenConversation() {
            if (!this.activeTurn)
                return Date.now() >= this.cooldownUntil;
            if (this.activeTurn.status === 'ask')
                return false;
            return Date.now() >= this.cooldownUntil;
        }
        panelEl() {
            const sel = this.opts.panelSelector;
            return sel ? document.querySelector(sel) : null;
        }
        setActiveTurn(turn) {
            var _a, _b, _c;
            this.activeTurn = turn;
            const panel = this.panelEl();
            if (!panel) {
                if ((turn === null || turn === void 0 ? void 0 : turn.status) === 'ask')
                    this.bus.emit('turn:ask', turn);
                else if ((turn === null || turn === void 0 ? void 0 : turn.status) === 'final') {
                    this.bus.emit('suggest:ready', (_a = turn.suggestions) !== null && _a !== void 0 ? _a : [], turn);
                    this.bus.emit('turn:final', turn);
                    this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
                }
                else {
                    this.bus.emit('turn:cleared');
                }
                return;
            }
            if (!turn) {
                panel.innerHTML = '';
                this.bus.emit('turn:cleared');
                return;
            }
            if (turn.status === 'ask') {
                renderAskTurn(panel, turn, (a) => this.answerAsk(turn, a), (fd) => this.answerForm(turn, fd));
                this.bus.emit('turn:ask', turn);
            }
            else {
                renderFinalSuggestions(panel, (_b = turn.suggestions) !== null && _b !== void 0 ? _b : [], () => undefined);
                this.bus.emit('suggest:ready', (_c = turn.suggestions) !== null && _c !== void 0 ? _c : [], turn);
                this.bus.emit('turn:final', turn);
                this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
            }
        }
        buildTelemetry(target) {
            const el = target && target.nodeType === 1 ? target : null;
            const elementText = el ? (el.textContent || '').trim().slice(0, 400) : null;
            const elementHtml = el ? el.outerHTML.slice(0, 4000) : null; // cap size
            const attributes = el ? attrMap(el) : {};
            try {
                const withAction = el === null || el === void 0 ? void 0 : el.closest('[data-action]');
                const action = withAction === null || withAction === void 0 ? void 0 : withAction.getAttribute('data-action');
                if (action && !('action' in attributes)) {
                    attributes['action'] = action;
                }
            }
            catch (_a) {
                /* empty */
            }
            try {
                const candidates = [];
                if (el) {
                    candidates.push(el);
                    let p = el.parentElement;
                    let hops = 0;
                    while (p && hops < 4) {
                        candidates.push(p);
                        p = p.parentElement;
                        hops++;
                    }
                }
                try {
                    const want = this.selMutation;
                    const isOn = !!this.trackOn;
                    if (isOn && Array.isArray(want) && want.length) {
                        for (const sel of want) {
                            try {
                                document.querySelectorAll(sel).forEach((node) => {
                                    if (node instanceof Element)
                                        candidates.push(node);
                                });
                            }
                            catch (_b) {
                                /* invalid selector from server; ignore */
                            }
                        }
                    }
                }
                catch (_c) {
                    /* ignore */
                }
                const uniq = Array.from(new Set(candidates));
                const pickKey = (cand) => {
                    const id = cand.id || '';
                    if (id)
                        return id;
                    const dataNames = [];
                    for (const a of Array.from(cand.attributes)) {
                        if (a.name.startsWith('data-'))
                            dataNames.push(a.name.replace(/^data-/, ''));
                    }
                    const pref = dataNames.find((n) => /^(name|counter|count|qty|quantity|total|badge|value)$/i.test(n));
                    if (pref)
                        return pref;
                    if (dataNames.length)
                        return dataNames[0];
                    const cls = (cand.getAttribute('class') || '').trim();
                    if (cls)
                        return cls.split(/\s+/)[0];
                    return cand.tagName ? cand.tagName.toLowerCase() : null;
                };
                for (const cand of uniq) {
                    const txt = (cand.textContent || '').trim();
                    const n = firstInt(txt);
                    if (n == null)
                        continue;
                    const key = pickKey(cand);
                    if (!key)
                        continue;
                    const camel = key
                        .replace(/[^a-zA-Z0-9]+(.)/g, (_, c) => (c ? String(c).toUpperCase() : ''))
                        .replace(/^(.)/, (m) => m.toLowerCase());
                    attributes[camel] = String(n);
                }
            }
            catch (_d) {
                /* best-effort only */
            }
            const css = el ? cssPath(el) : null;
            const xp = el ? xPath(el) : null;
            const near = el ? nearbyText(el) : [];
            const ancs = el ? ancestorBrief(el) : [];
            const toStr = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v == null ? null : String(v)]));
            return {
                elementText: safeStr(elementText),
                elementHtml: safeStr(elementHtml),
                attributes: toStr(attributes),
                cssPath: safeStr(css),
                xpath: safeStr(xp),
                nearbyText: near.map((t) => String(t)).slice(0, 5),
                ancestors: ancs.map((a) => Object.fromEntries(Object.entries(a).map(([k, v]) => [k, v == null ? null : String(v)]))),
            };
        }
        handleEvent(kind, target) {
            return __awaiter(this, void 0, void 0, function* () {
                var _a;
                if (this.inflight)
                    return;
                this.inflight = true;
                try {
                    const rcReq = {
                        siteId: this.opts.siteId,
                        sessionId: this.opts.sessionId,
                        event: {
                            type: kind,
                            ts: Date.now(),
                            telemetry: this.buildTelemetry(target),
                        },
                    };
                    const rcRes = yield this.api.ruleCheck(rcReq);
                    this.bus.emit('rule:checked', rcRes);
                    this.lastContext = {
                        matchedRules: rcRes.matchedRules,
                        eventType: rcRes.eventType,
                    };
                    if (!rcRes.shouldProceed || !this.canOpenConversation()) {
                        if (!rcRes.shouldProceed)
                            this.setActiveTurn(undefined);
                        return;
                    }
                    const sgReq = {
                        siteId: this.opts.siteId,
                        sessionId: this.opts.sessionId,
                        context: Object.assign({ matchedRules: rcRes.matchedRules, eventType: rcRes.eventType }, ((_a = this.opts.baseContext) !== null && _a !== void 0 ? _a : {})),
                    };
                    const { turn } = (yield this.api.suggestGet(sgReq));
                    this.setActiveTurn(turn);
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
                finally {
                    this.inflight = false;
                }
            });
        }
    }
    function isActionWithValue(a) {
        return typeof a.value !== 'undefined';
    }

    // Attach a simple UMD-style global for convenience when used via <script>
    if (typeof window !== 'undefined') {
        window.AgentSDK = {
            AutoAssistant,
            renderAskTurn,
            renderFinalSuggestions,
            createApi,
        };
    }

    exports.AutoAssistant = AutoAssistant;
    exports.createApi = createApi;
    exports.renderAskTurn = renderAskTurn;
    exports.renderFinalSuggestions = renderFinalSuggestions;

}));
//# sourceMappingURL=sdk.umd.js.map
