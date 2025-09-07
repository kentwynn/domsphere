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
            suggestGet: (body) => postJson(baseUrl, '/suggest', body, headers()),
            ruleListGet: (siteId) => getJson(baseUrl, `/rule?siteId=${encodeURIComponent(siteId)}`, headers()),
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

    function renderFinalSuggestions(container, suggestions, onCta) {
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

    class AutoAssistant {
        constructor(options) {
            var _a, _b;
            this.bus = new Emitter();
            this.detachFns = [];
            this.inflight = false;
            this.cooldownUntil = 0;
            this.trackOn = false;
            this.allow = new Set();
            this.focus = new Map();
            this.lastSuggestions = [];
            this.currentStep = 1;
            this.opts = Object.assign({ debounceMs: (_a = options.debounceMs) !== null && _a !== void 0 ? _a : 150, finalCooldownMs: (_b = options.finalCooldownMs) !== null && _b !== void 0 ? _b : 30000 }, options);
            this.api = createApi(options);
        }
        on(evt, fn) {
            return this.bus.on(evt, fn);
        }
        start() {
            return __awaiter(this, void 0, void 0, function* () {
                var _a, _b, _c;
                // 1) Load rules to choose focus vs rich tracking
                try {
                    const res = (yield this.api.ruleListGet(this.opts.siteId));
                    const rules = ((_a = res === null || res === void 0 ? void 0 : res.rules) !== null && _a !== void 0 ? _a : []);
                    const tracked = rules.filter((r) => !!r.tracking);
                    this.trackOn = tracked.length > 0;
                    if (this.trackOn) {
                        const kinds = new Set();
                        this.focus.clear();
                        for (const r of tracked) {
                            const triggers = ((_b = r.triggers) !== null && _b !== void 0 ? _b : []);
                            for (const t of triggers) {
                                const k = String(t.eventType || '').trim();
                                if (k &&
                                    [
                                        'dom_click',
                                        'input_change',
                                        'submit',
                                        'page_load',
                                        'route_change',
                                    ].includes(k))
                                    kinds.add(k);
                                const ek = k;
                                if (!this.focus.has(ek))
                                    this.focus.set(ek, { paths: new Set(), elementIds: new Set() });
                                const f = this.focus.get(ek);
                                if (!f)
                                    continue;
                                for (const cond of (_c = t.when) !== null && _c !== void 0 ? _c : []) {
                                    const field = String(cond.field || '');
                                    const op = String(cond.op || '').toLowerCase();
                                    const val = cond.value;
                                    if (op !== 'equals')
                                        continue;
                                    if (field === 'telemetry.attributes.path' &&
                                        typeof val === 'string')
                                        f.paths.add(normalizePath(val));
                                    if (field === 'telemetry.attributes.id' &&
                                        typeof val === 'string')
                                        f.elementIds.add(val);
                                }
                            }
                        }
                        this.allow = kinds.size ? kinds : new Set(['page_load']);
                    }
                    else {
                        this.allow = new Set([
                            'dom_click',
                            'input_change',
                            'submit',
                            'page_load',
                            'route_change',
                        ]);
                    }
                    this.bus.emit('rule:ready');
                }
                catch (e) {
                    this.trackOn = false;
                    this.allow = new Set([
                        'dom_click',
                        'input_change',
                        'submit',
                        'page_load',
                        'route_change',
                    ]);
                    this.bus.emit('error', e);
                }
                // 2) Register listeners
                if (this.trackOn) {
                    this.setupListenersFocusMode();
                }
            });
        }
        // Focused tracking: only emit allowed events and only for allowed selectors
        setupListenersFocusMode() {
            // page_load
            if (this.allow.has('page_load')) {
                this.schedule(() => {
                    const target = this.pickFocusTarget('page_load') || (document.body || undefined);
                    if (this.pathMatches('page_load'))
                        this.handleEvent('page_load', target);
                });
            }
            // clicks
            const onClick = (e) => {
                const tgt = e.target;
                if (!this.allow.has('dom_click'))
                    return;
                const focusTgt = this.pickFocusTarget('dom_click') || tgt;
                if (!this.pathMatches('dom_click'))
                    return;
                // In focus mode, only emit when the actual event target (or its ancestors)
                // matches a configured element id, if any ids are specified.
                if (!this.idMatches('dom_click', tgt))
                    return;
                this.schedule(() => this.handleEvent('dom_click', focusTgt));
            };
            document.addEventListener('click', onClick, true);
            this.detachFns.push(() => document.removeEventListener('click', onClick, true));
            // input/change
            const onChange = (e) => {
                const tgt = e.target;
                if (!this.allow.has('input_change'))
                    return;
                const focusTgt = this.pickFocusTarget('input_change') || tgt;
                if (!this.pathMatches('input_change'))
                    return;
                if (!this.idMatches('input_change', tgt))
                    return;
                this.schedule(() => this.handleEvent('input_change', focusTgt));
            };
            document.addEventListener('input', onChange, true);
            document.addEventListener('change', onChange, true);
            this.detachFns.push(() => document.removeEventListener('input', onChange, true));
            this.detachFns.push(() => document.removeEventListener('change', onChange, true));
            // submit
            const onSubmit = (e) => {
                if (!this.allow.has('submit'))
                    return;
                const tgt = e.target;
                const focusTgt = this.pickFocusTarget('submit') || tgt;
                if (!this.pathMatches('submit'))
                    return;
                if (!this.idMatches('submit', tgt))
                    return;
                this.schedule(() => this.handleEvent('submit', focusTgt));
            };
            document.addEventListener('submit', onSubmit, true);
            this.detachFns.push(() => document.removeEventListener('submit', onSubmit, true));
            // route change
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
                if (!this.allow.has('route_change'))
                    return;
                if (!this.pathMatches('route_change'))
                    return;
                const target = this.pickFocusTarget('route_change');
                this.schedule(() => this.handleEvent('route_change', target));
            };
            window.addEventListener('popstate', onPop);
            window.addEventListener('agent-route-change', onPop);
            this.detachFns.push(() => {
                window.removeEventListener('popstate', onPop);
                window.removeEventListener('agent-route-change', onPop);
                history.pushState = _push;
                history.replaceState = _replace;
            });
            // No mutation observer in focus mode without selectors
        }
        pickFocusTarget(kind) {
            const f = this.focus.get(kind);
            if (!f || f.elementIds.size === 0)
                return undefined;
            for (const id of f.elementIds) {
                const el = document.getElementById(id);
                if (el)
                    return el;
            }
            return undefined;
        }
        pathMatches(kind) {
            const f = this.focus.get(kind);
            if (!f)
                return true;
            if (f.paths.size === 0)
                return true;
            try {
                const cur = normalizePath(window.location.pathname || '/');
                return f.paths.has(cur);
            }
            catch (_a) {
                return true;
            }
        }
        idMatches(kind, target) {
            const f = this.focus.get(kind);
            if (!f)
                return true;
            if (f.elementIds.size === 0)
                return true;
            if (!target)
                return false;
            let el = target;
            let hops = 0;
            while (el && hops < 5) {
                const id = el.id || '';
                if (id && f.elementIds.has(id))
                    return true;
                el = el.parentElement;
                hops++;
            }
            return false;
        }
        // Only gate by path in focus mode; for DOM events we will send telemetry anchored
        // to the focused element (if configured) to satisfy id-based rule conditions.
        shouldEmit(kind) {
            return this.pathMatches(kind);
        }
        // TODO: setupListenersRichMode removed. Reintroduce when we support rich tracking heuristics.
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
        // No ask/form flows in stateless mode
        schedule(fn) {
            if (this.debTimer)
                window.clearTimeout(this.debTimer);
            this.debTimer = window.setTimeout(fn, this.opts.debounceMs);
        }
        canOpenPanel() {
            return Date.now() >= this.cooldownUntil;
        }
        panelEl() {
            const sel = this.opts.panelSelector;
            return sel ? document.querySelector(sel) : null;
        }
        renderSuggestions(suggestions) {
            const panel = this.panelEl();
            if (!panel)
                return;
            this.lastSuggestions = suggestions;
            // Determine the initial step to render
            const steps = suggestions
                .map((s) => {
                var _a;
                const m = (s.meta || {});
                const step = Number((_a = m['step']) !== null && _a !== void 0 ? _a : 1);
                return Number.isFinite(step) ? step : 1;
            })
                .filter((n) => n > 0);
            this.currentStep = steps.length ? Math.min(...steps) : 1;
            this.renderStep();
        }
        renderStep() {
            const panel = this.panelEl();
            if (!panel)
                return;
            const toShow = this.lastSuggestions.filter((s) => {
                var _a;
                const m = (s.meta || {});
                const step = Number((_a = m['step']) !== null && _a !== void 0 ? _a : 1);
                return (Number.isFinite(step) ? step : 1) === this.currentStep;
            });
            renderFinalSuggestions(panel, toShow, (cta) => this.executeCta(cta));
            this.bus.emit('suggest:ready', toShow);
            this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
        }
        executeCta(cta) {
            try {
                const kind = String(cta.kind || '').toLowerCase();
                // Prefer app-provided CTA executor to avoid SDK-level hardcoding
                if (typeof this.opts.ctaExecutor === 'function') {
                    this.opts.ctaExecutor(cta);
                    return;
                }
                const handlers = {
                    dom_fill: (c) => {
                        var _a, _b;
                        const p = ((_a = c.payload) !== null && _a !== void 0 ? _a : {});
                        const sel = String(p['selector'] || '');
                        const val = String((_b = p['value']) !== null && _b !== void 0 ? _b : '');
                        const el = sel
                            ? document.querySelector(sel)
                            : null;
                        if (!el)
                            return;
                        if ('value' in el) {
                            el.value = val;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        else {
                            el.textContent = val;
                        }
                    },
                    click: (c) => {
                        var _a;
                        const p = ((_a = c.payload) !== null && _a !== void 0 ? _a : {});
                        const sel = String(p['selector'] || '');
                        const el = sel
                            ? document.querySelector(sel)
                            : null;
                        el === null || el === void 0 ? void 0 : el.click();
                    },
                    open: (c) => {
                        const url = typeof c.url === 'string' && c.url ? c.url : '';
                        if (url)
                            window.location.href = url;
                    },
                };
                if (handlers[kind])
                    handlers[kind](cta);
                // After executing a CTA, advance to the next step if available
                const allSteps = this.lastSuggestions
                    .map((s) => { var _a; return Number((_a = (s.meta || {})['step']) !== null && _a !== void 0 ? _a : 1); })
                    .filter((n) => Number.isFinite(n));
                const maxStep = allSteps.length ? Math.max(...allSteps) : 1;
                if (this.currentStep < maxStep) {
                    this.currentStep += 1;
                    this.renderStep();
                }
            }
            catch (e) {
                this.bus.emit('error', e);
            }
        }
        buildTelemetry(target) {
            const el = target && target.nodeType === 1 ? target : null;
            const elementText = el ? (el.textContent || '').trim().slice(0, 400) : null;
            const elementHtml = el ? el.outerHTML.slice(0, 4000) : null; // cap size
            const attributes = el ? attrMap(el) : {};
            // Always include current path so rules can filter on it
            try {
                const p = window.location ? window.location.pathname : '/';
                attributes['path'] = normalizePath(p);
            }
            catch (_a) {
                /* ignore */
            }
            try {
                const withAction = el === null || el === void 0 ? void 0 : el.closest('[data-action]');
                const action = withAction === null || withAction === void 0 ? void 0 : withAction.getAttribute('data-action');
                if (action && !('action' in attributes)) {
                    attributes['action'] = action;
                }
            }
            catch (_b) {
                /* empty */
            }
            try {
                // Candidate elements (start with event target and ancestors)
                const candidates = [];
                if (el) {
                    // In rich mode, consider target and ancestors (heuristic)
                    candidates.push(el);
                    let p = el.parentElement;
                    let hops = 0;
                    while (p && hops < 4) {
                        candidates.push(p);
                        p = p.parentElement;
                        hops++;
                    }
                }
                const uniq = Array.from(new Set(candidates));
                // Heuristic key picker used only in rich mode
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
                    const camel = toCamel(key);
                    attributes[camel] = String(n);
                }
            }
            catch (_c) {
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
                    if (!rcRes.shouldProceed || !this.canOpenPanel()) {
                        return;
                    }
                    const sgReq = {
                        siteId: this.opts.siteId,
                        url: window.location.origin + window.location.pathname,
                        ruleId: rcRes.matchedRules[0],
                    };
                    const { suggestions } = (yield this.api.suggestGet(sgReq));
                    this.renderSuggestions(suggestions);
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
    function normalizePath(p) {
        let s = String(p || '/').trim();
        if (!s.startsWith('/'))
            s = '/' + s;
        if (s.length > 1 && s.endsWith('/'))
            s = s.slice(0, -1);
        return s;
    }
    // Convert identifiers like cart-count or total_qty to cartCount / totalQty
    function toCamel(key) {
        return key
            .replace(/[^a-zA-Z0-9]+(.)/g, (_, c) => (c ? c.toUpperCase() : ''))
            .replace(/^(.)/, (m) => m.toLowerCase());
    }

    // Attach a simple UMD-style global for convenience when used via <script>
    if (typeof window !== 'undefined') {
        window.AgentSDK = {
            AutoAssistant,
            renderFinalSuggestions,
            createApi,
        };
    }

    exports.AutoAssistant = AutoAssistant;
    exports.createApi = createApi;
    exports.renderFinalSuggestions = renderFinalSuggestions;

}));
//# sourceMappingURL=sdk.umd.js.map
