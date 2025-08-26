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

    /**
     * Auto Assistant SDK (POC)
     * - Self-detects cart changes (clicks + MutationObserver)
     * - Calls /rule/check then /suggest/get (returns { turn })
     * - Supports ask -> final micro-conversation via answerAsk()
     * - Minimal render helpers for ask + final turns
     *
     * Build-ready for Nx + Rollup. Only type-imports from api-client.
     */
    /* =========================
     * Small utils
     * ========================= */
    const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
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
    function createApi(opts) {
        const { baseUrl, contractVersion = null, requestIdFactory, fetchHeaders = {}, } = opts;
        const headers = () => (Object.assign({ 'X-Contract-Version': contractVersion !== null && contractVersion !== void 0 ? contractVersion : undefined, 'X-Request-Id': requestIdFactory === null || requestIdFactory === void 0 ? void 0 : requestIdFactory() }, fetchHeaders));
        return {
            ruleCheck: (body) => postJson(baseUrl, '/rule/check', body, headers()),
            suggestGet: (body) => postJson(baseUrl, '/suggest/get', body, headers()),
        };
    }
    class Emitter {
        constructor() {
            this.m = new Map();
        }
        on(evt, fn) {
            if (!this.m.has(evt))
                this.m.set(evt, new Set());
            this.m.get(evt).add(fn);
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
    class AutoAssistant {
        constructor(options) {
            var _a, _b, _c;
            this.bus = new Emitter();
            this.detachFns = [];
            this.inflight = 0;
            this.lastCount = 0;
            this.opts = Object.assign(Object.assign({}, options), { minCountToProceed: (_a = options.minCountToProceed) !== null && _a !== void 0 ? _a : 2, debounceMs: (_b = options.debounceMs) !== null && _b !== void 0 ? _b : 250, selectors: Object.assign({ addButton: "[data-testid='add']", removeButton: "[data-testid='remove']", cartCounter: '#cart-count', cartItem: "[data-testid='cart-item']", panelSelector: '#suggestions' }, ((_c = options.selectors) !== null && _c !== void 0 ? _c : {})) });
            this.api = createApi(options);
        }
        on(evt, fn) {
            return this.bus.on(evt, fn);
        }
        /** Start auto-detection */
        start() {
            const { addButton, removeButton, cartCounter, cartItem } = this.opts.selectors;
            if (addButton)
                this.attach('click', addButton, () => this.bumpCount(1));
            if (removeButton)
                this.attach('click', removeButton, () => this.bumpCount(-1));
            this.mo = new MutationObserver(() => this.scheduleProcess());
            const observeTargets = [];
            if (cartCounter) {
                const el = document.querySelector(cartCounter);
                if (el)
                    observeTargets.push(el);
            }
            if (cartItem) {
                document
                    .querySelectorAll(cartItem)
                    .forEach((el) => observeTargets.push(el));
            }
            observeTargets.forEach((el) => this.mo.observe(el, {
                childList: true,
                characterData: true,
                subtree: true,
            }));
            this.scheduleProcess(true);
        }
        stop() {
            var _a;
            this.detachFns.forEach((f) => {
                try {
                    f();
                }
                catch (_a) {
                    /* empty */
                }
            });
            this.detachFns = [];
            (_a = this.mo) === null || _a === void 0 ? void 0 : _a.disconnect();
            if (this.debTimer)
                window.clearTimeout(this.debTimer);
        }
        /** Continue the ask flow: send the chosen action back to /suggest/get */
        answerAsk(turn, action) {
            return __awaiter(this, void 0, void 0, function* () {
                var _a, _b;
                const { siteId, sessionId, baseContext } = this.opts;
                const req = {
                    siteId,
                    sessionId,
                    prevTurnId: turn.turnId,
                    answers: { choice: action.id, value: action.value },
                    context: Object.assign({}, ((_a = this.opts.baseContext) !== null && _a !== void 0 ? _a : {})),
                };
                try {
                    const { turn: next } = yield this.api.suggestGet(req);
                    this.lastTurn = next;
                    if (next.status === 'ask') {
                        this.bus.emit('turn:ask', next);
                        const panel = this.panelEl();
                        if (panel)
                            renderAskTurn(panel, next, (a) => this.answerAsk(next, a));
                    }
                    else {
                        const suggestions = (_b = next.suggestions) !== null && _b !== void 0 ? _b : [];
                        this.bus.emit('suggest:ready', suggestions, next);
                        this.bus.emit('turn:final', next);
                        const panel = this.panelEl();
                        if (panel)
                            renderFinalSuggestions(panel, suggestions, (cta) => this.bus.emit('sdk:action', cta), next);
                    }
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
            });
        }
        /* ---------------- internals ---------------- */
        attach(evt, selector, handler) {
            const fn = (e) => {
                const t = e.target;
                if (!t)
                    return;
                if (t.closest(selector))
                    handler(e);
            };
            document.addEventListener(evt, fn, true);
            this.detachFns.push(() => document.removeEventListener(evt, fn, true));
        }
        readCount() {
            const { cartCounter, cartItem } = this.opts.selectors;
            if (cartCounter) {
                const el = document.querySelector(cartCounter);
                if (el) {
                    const n = parseInt((el.textContent || '0').replace(/\D+/g, ''), 10);
                    if (!Number.isNaN(n))
                        return n;
                }
            }
            if (cartItem) {
                const n = document.querySelectorAll(cartItem).length;
                if (n >= 0)
                    return n;
            }
            return this.lastCount;
        }
        bumpCount(delta) {
            this.lastCount = clamp(this.lastCount + delta, 0, 9999);
            this.scheduleProcess(true);
        }
        scheduleProcess(force = false) {
            if (this.debTimer)
                window.clearTimeout(this.debTimer);
            this.debTimer = window.setTimeout(() => this.process(force), this.opts.debounceMs);
        }
        process() {
            return __awaiter(this, arguments, void 0, function* (force = false) {
                const count = this.readCount();
                const changed = force || count !== this.lastCount;
                this.lastCount = count;
                if (!changed)
                    return;
                this.bus.emit('cart:changed', count);
                if (count < this.opts.minCountToProceed) {
                    this.bus.emit('turn:cleared');
                    const panel = this.panelEl();
                    if (panel)
                        panel.innerHTML = '';
                    return;
                }
                if (this.inflight > 0)
                    return;
                this.inflight++;
                try {
                    yield this.runFlow(count);
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
                finally {
                    this.inflight = 0;
                }
            });
        }
        runFlow(count) {
            return __awaiter(this, void 0, void 0, function* () {
                var _a, _b;
                const { siteId, sessionId } = this.opts;
                // 1) /rule/check
                const rcReq = {
                    siteId,
                    sessionId,
                    event: {
                        type: 'dom_click',
                        ts: Date.now(),
                        telemetry: {
                            attributes: { cartCount: String(count) },
                        },
                    },
                };
                const rcRes = yield this.api.ruleCheck(rcReq);
                this.bus.emit('rule:checked', rcRes);
                if (!rcRes.shouldProceed) {
                    this.bus.emit('turn:cleared');
                    const panel = this.panelEl();
                    if (panel)
                        panel.innerHTML = '';
                    return;
                }
                // 2) /suggest/get (first turn)
                const sgReq = {
                    siteId,
                    sessionId,
                    context: Object.assign({ matchedRules: rcRes.matchedRules, eventType: rcRes.eventType }, ((_a = this.opts.baseContext) !== null && _a !== void 0 ? _a : {})),
                };
                const { turn } = yield this.api.suggestGet(sgReq);
                this.lastTurn = turn;
                if (turn.status === 'ask') {
                    this.bus.emit('turn:ask', turn);
                    const panel = this.panelEl();
                    if (panel)
                        renderAskTurn(panel, turn, (a) => this.answerAsk(turn, a));
                }
                else {
                    const suggestions = (_b = turn.suggestions) !== null && _b !== void 0 ? _b : [];
                    this.bus.emit('suggest:ready', suggestions, turn);
                    this.bus.emit('turn:final', turn);
                    const panel = this.panelEl();
                    if (panel)
                        renderFinalSuggestions(panel, suggestions, (cta) => this.bus.emit('sdk:action', cta));
                }
            });
        }
        panelEl() {
            var _a;
            const sel = (_a = this.opts.selectors) === null || _a === void 0 ? void 0 : _a.panelSelector;
            return sel ? document.querySelector(sel) : null;
        }
    }
    /* =========================
     * Render helpers (optional)
     * ========================= */
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
                btn.setAttribute('data-action-id', a.id);
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
                        el.rows = 3;
                        input = el;
                        break;
                    }
                    case 'select': {
                        const el = document.createElement('select');
                        el.name = f.key;
                        ((_a = f.options) !== null && _a !== void 0 ? _a : []).forEach((opt) => {
                            const o = document.createElement('option');
                            o.value = String(opt.value);
                            o.textContent = opt.label;
                            el.appendChild(o);
                        });
                        input = el;
                        break;
                    }
                    case 'checkbox': {
                        const el = document.createElement('input');
                        el.type = 'checkbox';
                        el.name = f.key;
                        input = el;
                        break;
                    }
                    case 'radio': {
                        const group = document.createElement('div');
                        ((_b = f.options) !== null && _b !== void 0 ? _b : []).forEach((opt, i) => {
                            const lbl = document.createElement('label');
                            lbl.style.marginRight = '10px';
                            const r = document.createElement('input');
                            r.type = 'radio';
                            r.name = f.key;
                            r.value = String(opt.value);
                            lbl.appendChild(r);
                            lbl.append(' ' + opt.label);
                            group.appendChild(lbl);
                        });
                        input = group;
                        break;
                    }
                    case 'number':
                    case 'range':
                    case 'toggle':
                    case 'text':
                    default: {
                        const el = document.createElement('input');
                        el.type = f.type === 'number' ? 'number' : 'text';
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
    function renderFinalSuggestions(container, suggestions, onCta, turn) {
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
            if (typeof s.price === 'number') {
                const price = document.createElement('div');
                price.textContent = s.currency
                    ? `${s.price} ${s.currency}`
                    : `${s.price}`;
                price.style.marginTop = '6px';
                card.appendChild(price);
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
