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
            suggestNext: (body) => postJson(baseUrl, '/suggest/next', body, headers()),
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

    function ensureBucket(focus, kind) {
        if (!focus.has(kind))
            focus.set(kind, {
                paths: new Set(),
                elementIds: new Set(),
                cssPaths: new Set(),
                cssPatterns: [],
                timeConditions: [],
                sessionConditions: [],
            });
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        return focus.get(kind);
    }
    function collectFocusFromRules(rules) {
        var _a, _b;
        const kinds = new Set();
        const focus = new Map();
        for (const r of rules) {
            const triggers = ((_a = r.triggers) !== null && _a !== void 0 ? _a : []);
            for (const t of triggers) {
                const k = String(t.eventType || '').trim();
                if (k &&
                    [
                        'dom_click',
                        'input_change',
                        'submit',
                        'page_load',
                        'route_change',
                        'scroll',
                        'time_spent',
                        'visibility_change',
                    ].includes(k))
                    kinds.add(k);
                const ek = k;
                const bucket = ensureBucket(focus, ek);
                // Process all conditions
                for (const cond of (_b = t.when) !== null && _b !== void 0 ? _b : []) {
                    const field = String(cond.field || '');
                    const op = String(cond.op || '').toLowerCase();
                    const val = cond.value;
                    // Path conditions (equals only)
                    if (field === 'telemetry.attributes.path' &&
                        op === 'equals' &&
                        typeof val === 'string') {
                        bucket.paths.add(normalizePath(val));
                    }
                    // Element ID conditions (equals only)
                    if (field === 'telemetry.attributes.id' &&
                        op === 'equals' &&
                        typeof val === 'string') {
                        bucket.elementIds.add(val);
                    }
                    // Time-based conditions
                    if ((field === 'session.timeOnPage' ||
                        field === 'telemetry.attributes.timeOnPage') &&
                        ['gt', 'gte', 'lt', 'lte'].includes(op) &&
                        typeof val === 'number') {
                        bucket.timeConditions.push({ op, value: val });
                    }
                    // Session conditions (clickCount, scrollDepth, etc.)
                    if (field.startsWith('session.') && field !== 'session.timeOnPage') {
                        bucket.sessionConditions.push({ field, op, value: val });
                    }
                    // CSS Path patterns for advanced selectors
                    if (field === 'telemetry.cssPath' &&
                        op === 'regex' &&
                        typeof val === 'string') {
                        try {
                            bucket.cssPatterns.push(new RegExp(val));
                        }
                        catch (_c) {
                            // Invalid regex, skip
                        }
                    }
                }
            }
        }
        return { focus, kinds };
    }
    function idMatches(focus, kind, target) {
        const f = focus.get(kind);
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
    function targetMatches(focus, kind, target) {
        const f = focus.get(kind);
        if (!f)
            return true;
        const hasAny = f.elementIds.size > 0;
        if (!hasAny)
            return true;
        return idMatches(focus, kind, target);
    }
    // Advanced condition evaluation helpers
    function evaluateTimeConditions(focus, kind, timeOnPage) {
        const f = focus.get(kind);
        if (!f || f.timeConditions.length === 0)
            return true;
        return f.timeConditions.every(({ op, value }) => {
            switch (op) {
                case 'gt':
                    return timeOnPage > value;
                case 'gte':
                    return timeOnPage >= value;
                case 'lt':
                    return timeOnPage < value;
                case 'lte':
                    return timeOnPage <= value;
                default:
                    return true;
            }
        });
    }
    function evaluateSessionConditions(focus, kind, sessionData) {
        const f = focus.get(kind);
        if (!f || f.sessionConditions.length === 0)
            return true;
        return f.sessionConditions.every(({ field, op, value }) => {
            const sessionValue = sessionData[field.replace('session.', '')];
            switch (op) {
                case 'equals':
                    return sessionValue === value;
                case 'gt':
                    return (typeof sessionValue === 'number' && sessionValue > value);
                case 'gte':
                    return (typeof sessionValue === 'number' && sessionValue >= value);
                case 'lt':
                    return (typeof sessionValue === 'number' && sessionValue < value);
                case 'lte':
                    return (typeof sessionValue === 'number' && sessionValue <= value);
                case 'contains':
                    return (typeof sessionValue === 'string' &&
                        sessionValue.includes(String(value)));
                case 'in':
                    return Array.isArray(value) && value.includes(sessionValue);
                default:
                    return true;
            }
        });
    }
    function evaluateAdvancedConditions(focus, kind, context) {
        // Evaluate time conditions
        if (context.timeOnPage !== undefined &&
            !evaluateTimeConditions(focus, kind, context.timeOnPage)) {
            return false;
        }
        // Evaluate session conditions
        if (context.sessionData &&
            !evaluateSessionConditions(focus, kind, context.sessionData)) {
            return false;
        }
        return true;
    }

    const ACCENT_VAR_CANDIDATES = [
        '--accent-color',
        '--accent',
        '--brand-color',
        '--primary-color',
        '--color-primary',
        '--primary',
        '--link-color',
        '--bs-primary',
    ];
    const CARD_RADIUS_CANDIDATES = [
        '--radius-md',
        '--radius',
        '--border-radius',
        '--border-radius-md',
        '--bs-border-radius',
        'border-radius',
    ];
    const CONTROL_RADIUS_CANDIDATES = [
        '--radius-sm',
        '--control-radius',
        '--button-radius',
        '--bs-border-radius-sm',
        '--radius-md',
        '--border-radius',
        'border-radius',
    ];
    let resolverEl = null;
    function ensureResolver() {
        var _a;
        if (typeof document === 'undefined') {
            return null;
        }
        if (resolverEl) {
            return resolverEl;
        }
        const el = document.createElement('span');
        el.style.position = 'fixed';
        el.style.top = '-9999px';
        el.style.width = '0';
        el.style.height = '0';
        el.style.visibility = 'hidden';
        el.style.pointerEvents = 'none';
        (_a = document.body) === null || _a === void 0 ? void 0 : _a.appendChild(el);
        resolverEl = el;
        return resolverEl;
    }
    function resolveColorValue(input) {
        if (!input || typeof window === 'undefined') {
            return null;
        }
        const resolver = ensureResolver();
        if (!resolver) {
            return null;
        }
        resolver.style.color = '';
        resolver.style.color = input;
        const color = window.getComputedStyle(resolver).color;
        if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
            return color;
        }
        resolver.style.backgroundColor = '';
        resolver.style.backgroundColor = input;
        const bg = window.getComputedStyle(resolver).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
            return bg;
        }
        return color || bg || null;
    }
    function parseCssColor(input) {
        if (!input) {
            return null;
        }
        let value = input.trim();
        if (!value) {
            return null;
        }
        if (value === 'transparent') {
            return { r: 0, g: 0, b: 0, a: 0 };
        }
        if (!/^rgb/i.test(value)) {
            const resolved = resolveColorValue(value);
            if (!resolved) {
                return null;
            }
            value = resolved;
        }
        const modernMatch = value.match(/^rgba?\(\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)(?:\s*\/\s*(\d+(?:\.\d+)?))?\s*\)$/i);
        if (modernMatch) {
            const [, r, g, b, a] = modernMatch;
            return toRgba(r, g, b, a);
        }
        const classicMatch = value.match(/^rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*(\d+(?:\.\d+)?))?\s*\)$/i);
        if (classicMatch) {
            const [, r, g, b, a] = classicMatch;
            return toRgba(r, g, b, a);
        }
        return null;
    }
    function toRgba(rStr, gStr, bStr, aStr) {
        const r = Number(rStr);
        const g = Number(gStr);
        const b = Number(bStr);
        const a = aStr === undefined ? 1 : Number(aStr);
        if ([r, g, b, a].some((n) => Number.isNaN(n))) {
            return null;
        }
        return {
            r: clamp255(r),
            g: clamp255(g),
            b: clamp255(b),
            a: clampUnit(a),
        };
    }
    function clamp255(value) {
        return Math.min(255, Math.max(0, value));
    }
    function clampUnit(value) {
        return Math.min(1, Math.max(0, value));
    }
    function rgbaToCss({ r, g, b, a }) {
        const alpha = Math.round(a * 1000) / 1000;
        if (alpha >= 1) {
            return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
        }
        return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;
    }
    function mixColors(base, other, weight) {
        const t = clampUnit(weight);
        return {
            r: base.r + (other.r - base.r) * t,
            g: base.g + (other.g - base.g) * t,
            b: base.b + (other.b - base.b) * t,
            a: base.a + (other.a - base.a) * t,
        };
    }
    function getRelativeLuminance({ r, g, b }) {
        const toLin = (channel) => {
            const c = channel / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        };
        return 0.2126 * toLin(r) + 0.7152 * toLin(g) + 0.0722 * toLin(b);
    }
    function contrastRatio(a, b) {
        const L1 = getRelativeLuminance(a);
        const L2 = getRelativeLuminance(b);
        const lighter = Math.max(L1, L2);
        const darker = Math.min(L1, L2);
        return (lighter + 0.05) / (darker + 0.05);
    }
    const WHITE = { r: 255, g: 255, b: 255, a: 1 };
    const BLACK = { r: 0, g: 0, b: 0, a: 1 };
    function pickContrastingText(base) {
        return contrastRatio(base, WHITE) >= contrastRatio(base, BLACK) ? WHITE : BLACK;
    }
    function readFirstStyleValue(style, candidates) {
        const anyStyle = style;
        for (const name of candidates) {
            const value = style.getPropertyValue(name);
            if (value && value.trim() && value.trim() !== '0px') {
                return value.trim();
            }
            const camel = toCamelCase(name);
            const direct = anyStyle[camel];
            if (typeof direct === 'string' && direct.trim() && direct.trim() !== '0px') {
                return direct.trim();
            }
        }
        return undefined;
    }
    function toCamelCase(value) {
        return value.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    }
    function deriveAccentCandidate(node, style) {
        var _a;
        for (const name of ACCENT_VAR_CANDIDATES) {
            const raw = style.getPropertyValue(name);
            const color = parseCssColor(raw);
            if (color) {
                return color;
            }
        }
        const attr = node.getAttribute('data-accent-color');
        const attrColor = parseCssColor(attr !== null && attr !== void 0 ? attr : undefined);
        if (attrColor) {
            return attrColor;
        }
        const linkColor = pickLinkColor(node);
        if (linkColor) {
            return linkColor;
        }
        return (_a = parseCssColor(style.color)) !== null && _a !== void 0 ? _a : null;
    }
    function pickLinkColor(root) {
        if (typeof window === 'undefined') {
            return null;
        }
        const link = root.querySelector('a[href]');
        if (link) {
            const color = window.getComputedStyle(link).color;
            const parsed = parseCssColor(color);
            if (parsed) {
                return parsed;
            }
        }
        if (root !== document.body && document.body) {
            const fallbackLink = document.body.querySelector('a[href]');
            if (fallbackLink) {
                const color = window.getComputedStyle(fallbackLink).color;
                const parsed = parseCssColor(color);
                if (parsed) {
                    return parsed;
                }
            }
        }
        return null;
    }
    function getReferenceElement(container) {
        const explicit = container.closest('[data-assistant-theme-root]');
        if (explicit instanceof HTMLElement) {
            return explicit;
        }
        return container;
    }
    function deriveHostTheme(container) {
        var _a, _b, _c, _d, _e, _f, _g, _h;
        const reference = getReferenceElement(container);
        const style = window.getComputedStyle(reference);
        const bodyStyle = document.body
            ? window.getComputedStyle(document.body)
            : null;
        const textColor = (_b = (_a = parseCssColor(style.color)) !== null && _a !== void 0 ? _a : parseCssColor(bodyStyle === null || bodyStyle === void 0 ? void 0 : bodyStyle.color)) !== null && _b !== void 0 ? _b : { r: 17, g: 24, b: 39, a: 1 };
        const backgroundColor = (_d = (_c = parseCssColor(style.backgroundColor)) !== null && _c !== void 0 ? _c : parseCssColor(bodyStyle === null || bodyStyle === void 0 ? void 0 : bodyStyle.backgroundColor)) !== null && _d !== void 0 ? _d : { r: 255, g: 255, b: 255, a: 1 };
        const accentColor = (_f = (_e = deriveAccentCandidate(reference, style)) !== null && _e !== void 0 ? _e : parseCssColor(style.color)) !== null && _f !== void 0 ? _f : textColor;
        const accentText = pickContrastingText(accentColor);
        const surfaceMix = mixColors(backgroundColor, accentColor, 0.06);
        surfaceMix.a = Math.max(surfaceMix.a, backgroundColor.a);
        const surface = rgbaToCss(surfaceMix);
        const borderMix = mixColors(backgroundColor, textColor, 0.7);
        borderMix.a = Math.max(borderMix.a, 0.45);
        const border = rgbaToCss(borderMix);
        const subtleTextMix = mixColors(textColor, backgroundColor, 0.4);
        subtleTextMix.a = textColor.a;
        const subtleText = rgbaToCss(subtleTextMix);
        const secondaryBorderMix = mixColors(backgroundColor, textColor, 0.55);
        secondaryBorderMix.a = Math.max(secondaryBorderMix.a, 0.5);
        const secondaryBorder = rgbaToCss(secondaryBorderMix);
        const containerRadius = (_g = readFirstStyleValue(style, CARD_RADIUS_CANDIDATES)) !== null && _g !== void 0 ? _g : '0.75rem';
        const controlRadius = (_h = readFirstStyleValue(style, CONTROL_RADIUS_CANDIDATES)) !== null && _h !== void 0 ? _h : containerRadius;
        return {
            accent: rgbaToCss(accentColor),
            accentText: rgbaToCss(accentText),
            border,
            surface,
            text: rgbaToCss(textColor),
            subtleText,
            secondaryBorder,
            containerRadius,
            controlRadius,
        };
    }
    function createButton(label, theme, variant) {
        var _a;
        const btn = document.createElement('button');
        btn.type = 'button';
        const finalLabel = (label !== null && label !== void 0 ? label : '').trim() || 'Action';
        btn.textContent = finalLabel;
        btn.setAttribute('aria-label', finalLabel);
        btn.dataset['assistantVariant'] = variant;
        btn.style.font = 'inherit';
        btn.style.cursor = 'pointer';
        btn.style.lineHeight = '1.4';
        btn.style.padding = '0.55em 0.9em';
        btn.style.borderRadius = theme.controlRadius;
        btn.style.borderWidth = '1px';
        btn.style.borderStyle = 'solid';
        btn.style.transition =
            'background-color 120ms ease, border-color 120ms ease, color 120ms ease';
        btn.style.display = 'inline-flex';
        btn.style.alignItems = 'center';
        btn.style.justifyContent = 'center';
        btn.style.gap = '0.35em';
        if (variant === 'primary') {
            btn.style.backgroundColor = theme.accent;
            btn.style.borderColor = theme.accent;
            btn.style.color = theme.accentText;
        }
        else {
            btn.style.backgroundColor = (_a = theme.surface) !== null && _a !== void 0 ? _a : 'transparent';
            btn.style.borderColor = theme.secondaryBorder;
            btn.style.color = theme.text;
        }
        return btn;
    }
    function renderFinalSuggestions(container, suggestions, onCta) {
        container.innerHTML = '';
        if (!(suggestions === null || suggestions === void 0 ? void 0 : suggestions.length)) {
            container.removeAttribute('data-assistant-theme');
            return;
        }
        const theme = deriveHostTheme(container);
        container.setAttribute('data-assistant-theme', 'host');
        const frag = document.createDocumentFragment();
        suggestions.forEach((s0) => {
            var _a, _b, _c, _d;
            const s = s0;
            const card = document.createElement('article');
            card.setAttribute('data-testid', 'assistant-card');
            card.dataset['role'] = 'assistant-card';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '0.65rem';
            card.style.border = `1px solid ${theme.border}`;
            card.style.borderRadius = theme.containerRadius;
            card.style.padding = '1rem';
            card.style.margin = '0.75rem 0';
            card.style.backgroundColor = (_a = theme.surface) !== null && _a !== void 0 ? _a : 'transparent';
            card.style.color = theme.text;
            card.style.boxSizing = 'border-box';
            const title = document.createElement('h3');
            title.dataset['role'] = 'assistant-title';
            title.textContent = (_b = s.title) !== null && _b !== void 0 ? _b : s.type;
            title.style.margin = '0';
            title.style.fontWeight = '600';
            title.style.color = theme.text;
            card.appendChild(title);
            if (s.description) {
                const desc = document.createElement('p');
                desc.dataset['role'] = 'assistant-description';
                desc.textContent = s.description;
                desc.style.margin = '0';
                desc.style.color = theme.subtleText;
                desc.style.fontSize = '0.95em';
                card.appendChild(desc);
            }
            // Build primary + secondary actions with de-duplication.
            // Display the primaryCta as the main action; primaryActions is a hidden pipeline run by the SDK.
            const primary = s.primaryCta ? [s.primaryCta] : [];
            const secondaryFromSchema = s.secondaryCta ? [s.secondaryCta] : [];
            const secondaryFromNew = (_c = s.secondaryActions) !== null && _c !== void 0 ? _c : [];
            const secondaryFallback = (_d = s.actions) !== null && _d !== void 0 ? _d : [];
            const pickFirstPopulated = (lists) => {
                for (const list of lists) {
                    if (Array.isArray(list) && list.length) {
                        return list;
                    }
                }
                return [];
            };
            const secondary = pickFirstPopulated([
                secondaryFromNew,
                secondaryFromSchema,
                secondaryFallback,
            ]).slice(0, 5);
            const sig = (c) => {
                var _a, _b, _c, _d;
                const kind = (_a = c.kind) !== null && _a !== void 0 ? _a : '';
                const label = (_b = c.label) !== null && _b !== void 0 ? _b : '';
                const payload = (_c = c.payload) !== null && _c !== void 0 ? _c : null;
                const url = (_d = c.url) !== null && _d !== void 0 ? _d : '';
                return `${kind}|${label}|${JSON.stringify(payload) || ''}|${url}`;
            };
            const primarySig = primary.length ? sig(primary[0]) : null;
            const dedupedSecondary = secondary.filter((c) => sig(c) !== primarySig);
            if (primary.length || dedupedSecondary.length) {
                const row = document.createElement('div');
                row.dataset['role'] = 'assistant-actions';
                row.style.display = 'flex';
                row.style.flexWrap = 'wrap';
                row.style.gap = '0.5rem';
                row.style.marginTop = '0.5rem';
                // Render primary CTA with host-aware styling
                if (primary.length) {
                    const p = primary[0];
                    const btn = createButton(p.label, theme, 'primary');
                    btn.setAttribute('data-cta-kind', String(p.kind || ''));
                    btn.onclick = () => onCta(p);
                    row.appendChild(btn);
                }
                // Render secondary actions
                dedupedSecondary.forEach((cta, idx) => {
                    const btn = createButton(cta.label, theme, 'secondary');
                    btn.setAttribute('data-cta-idx', String(idx));
                    btn.onclick = () => onCta(cta);
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
        // Local helper types to avoid `any` casting for extended fields not yet in the OpenAPI client
        sigForCta(c) {
            var _a, _b, _c, _d;
            const kind = (_a = c.kind) !== null && _a !== void 0 ? _a : '';
            const label = (_b = c.label) !== null && _b !== void 0 ? _b : '';
            const payload = (_c = c.payload) !== null && _c !== void 0 ? _c : null;
            const url = (_d = c.url) !== null && _d !== void 0 ? _d : '';
            return `${String(kind)}|${String(label)}|${JSON.stringify(payload) || ''}|${String(url)}`;
        }
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
            this.triggeredRules = new Set();
            this.choiceInput = {};
            // Time-based rule tracking
            this.lastTimeBasedTrigger = 0;
            this.triggeredTimeThresholds = new Set();
            // Session tracking for advanced conditions
            this.pageLoadTime = Date.now();
            this.sessionData = {
                clickCount: 0,
                scrollDepth: 0,
                timeOnSite: 0,
                referrer: document.referrer,
                userAgent: navigator.userAgent,
                viewport: `${window.innerWidth}x${window.innerHeight}`,
            };
            this.timeBasedTimers = new Map();
            this.opts = Object.assign({ debounceMs: (_a = options.debounceMs) !== null && _a !== void 0 ? _a : 150, finalCooldownMs: (_b = options.finalCooldownMs) !== null && _b !== void 0 ? _b : 30000 }, options);
            this.api = createApi(options);
        }
        on(evt, fn) {
            return this.bus.on(evt, fn);
        }
        start() {
            return __awaiter(this, void 0, void 0, function* () {
                var _a;
                // 1) Load rules to choose focus vs rich tracking
                try {
                    const res = (yield this.api.ruleListGet(this.opts.siteId));
                    const rules = ((_a = res === null || res === void 0 ? void 0 : res.rules) !== null && _a !== void 0 ? _a : []);
                    const tracked = rules.filter((r) => !!r.tracking);
                    this.trackOn = tracked.length > 0;
                    if (this.trackOn) {
                        const { focus, kinds } = collectFocusFromRules(tracked);
                        this.focus = focus;
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
            // Initialize session tracking
            this.initializeSessionTracking();
            // page_load
            if (this.allow.has('page_load')) {
                this.schedule(() => {
                    const target = this.pickFocusTarget('page_load') || document.body || undefined;
                    if (this.pathMatches('page_load'))
                        this.handleEvent('page_load', target);
                });
            }
            // time_spent events
            if (this.allow.has('time_spent')) {
                this.setupTimeBasedEvents();
            }
            // clicks
            const onClick = (e) => {
                const tgt = e.target;
                // Update session click count
                this.sessionData['clickCount'] =
                    this.sessionData['clickCount'] + 1;
                if (!this.allow.has('dom_click'))
                    return;
                const focusTgt = this.pickFocusTarget('dom_click') || tgt;
                if (!this.pathMatches('dom_click'))
                    return;
                // Only emit when target matches configured ids or cssPath filters (if any)
                if (!this.targetMatches('dom_click', tgt))
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
                if (!this.targetMatches('input_change', tgt))
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
                if (!this.targetMatches('submit', tgt))
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
                // Clear dedupe when route changes
                this.triggeredRules.clear();
                // Clear accumulated choice inputs on navigation
                this.choiceInput = {};
                // Reset session tracking for new page
                this.pageLoadTime = Date.now();
                this.lastTimeBasedTrigger = 0;
                this.triggeredTimeThresholds.clear();
                this.sessionData['clickCount'] = 0;
                this.sessionData['scrollDepth'] = 0;
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
            // Observe text/value changes on configured elements (id-only) to synthesize input_change
            if (this.allow.has('input_change')) {
                const f = this.focus.get('input_change');
                if (f && f.elementIds.size > 0) {
                    try {
                        const observer = new MutationObserver((mutations) => {
                            if (!this.pathMatches('input_change'))
                                return;
                            const seen = new Set();
                            for (const m of mutations) {
                                const t = m.target.nodeType === Node.TEXT_NODE
                                    ? m.target.parentElement
                                    : m.target;
                                if (!t)
                                    continue;
                                // Bubble and collect first matching selector per mutation
                                let el = t;
                                let hops = 0;
                                while (el && hops < 5) {
                                    const id = el.id || '';
                                    const matchId = id && f.elementIds.has(id);
                                    if (matchId) {
                                        seen.add(el);
                                        break;
                                    }
                                    el = el.parentElement;
                                    hops++;
                                }
                            }
                            seen.forEach((el) => {
                                if (!this.targetMatches('input_change', el))
                                    return;
                                this.schedule(() => this.handleEvent('input_change', el));
                            });
                        });
                        // Observe specific ids
                        f.elementIds.forEach((id) => {
                            const el = document.getElementById(id);
                            if (el)
                                observer.observe(el, {
                                    subtree: true,
                                    childList: true,
                                    characterData: true,
                                });
                        });
                        // No cssPath-based observation to avoid oversensitivity
                        this.detachFns.push(() => observer.disconnect());
                    }
                    catch (_a) {
                        /* MutationObserver unavailable; skip */
                    }
                }
            }
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
            return idMatches(this.focus, kind, target);
        }
        targetMatches(kind, target) {
            return targetMatches(this.focus, kind, target);
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
        closePanel() {
            const panel = this.panelEl();
            if (panel)
                panel.innerHTML = '';
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
                return ((Number.isFinite(step) ? step : 1) === this.currentStep);
            });
            renderFinalSuggestions(panel, toShow, (cta) => this.executeCta(cta));
            this.bus.emit('suggest:ready', toShow);
            this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
        }
        executeCta(cta) {
            return __awaiter(this, void 0, void 0, function* () {
                var _a, _b;
                // Suppress rule checks during CTA execution to avoid racing renders
                const prevInflight = this.inflight;
                this.inflight = true;
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
                        choose: (c) => __awaiter(this, void 0, void 0, function* () {
                            var _a, _b;
                            const p = ((_a = c.payload) !== null && _a !== void 0 ? _a : {});
                            const name = String(p['name'] || p['key'] || '').trim();
                            const value = (_b = p['value']) !== null && _b !== void 0 ? _b : null;
                            if (!name)
                                return;
                            try {
                                // Merge prior choices so the agent sees cumulative input
                                const extra = c
                                    .nextInput || {};
                                const input = Object.assign(Object.assign(Object.assign({}, this.choiceInput), { [name]: value }), extra);
                                const body = {
                                    siteId: this.opts.siteId,
                                    url: window.location.origin + window.location.pathname,
                                    ruleId: this.lastRuleId || '',
                                    input,
                                };
                                const res = yield this.api.suggestNext(body);
                                const suggestions = (res === null || res === void 0 ? void 0 : res.suggestions) || [];
                                if (Array.isArray(suggestions)) {
                                    // Persist the selection
                                    this.choiceInput[name] = value;
                                    this.renderSuggestions(suggestions);
                                }
                            }
                            catch (err) {
                                this.bus.emit('error', err);
                            }
                        }),
                    };
                    const runPipeline = (steps) => __awaiter(this, void 0, void 0, function* () {
                        if (!Array.isArray(steps) || steps.length === 0)
                            return;
                        for (const step of steps) {
                            const k = String(step.kind || '').toLowerCase();
                            const fn = handlers[k];
                            if (fn)
                                yield Promise.resolve(fn(step));
                        }
                    });
                    const getParentSuggestion = () => {
                        // Find the suggestion that owns this CTA by signature
                        const targetSig = this.sigForCta(cta);
                        for (const s0 of this.lastSuggestions) {
                            const s = s0;
                            const p = s.primaryCta;
                            const primArr = s.primaryActions;
                            const second = (s.secondaryActions ||
                                (s.secondaryCta ? [s.secondaryCta] : []) ||
                                s.actions ||
                                []);
                            if (p && this.sigForCta(p) === targetSig)
                                return s;
                            if (Array.isArray(second) &&
                                second.some((c) => this.sigForCta(c) === targetSig))
                                return s;
                            if (Array.isArray(primArr) &&
                                primArr.some((c) => this.sigForCta(c) === targetSig))
                                return s;
                        }
                        return null;
                    };
                    // Work out if this CTA is the suggestion's primaryCta and has a primaryActions pipeline
                    const parent = getParentSuggestion();
                    const isPrimaryWithPipeline = (() => {
                        if (!parent || !parent.primaryCta)
                            return false;
                        const prim = parent.primaryCta;
                        const match = this.sigForCta(prim) === this.sigForCta(cta);
                        const steps = parent.primaryActions || [];
                        return match && Array.isArray(steps) && steps.length > 0;
                    })();
                    if (isPrimaryWithPipeline && parent) {
                        // If a primaryActions pipeline is defined, run it INSTEAD of the primaryCta's own handler.
                        // This lets the pipeline control ordering (e.g., fill then submit).
                        yield runPipeline(parent.primaryActions || []);
                    }
                    else {
                        // Otherwise, invoke the CTA handler and then any CTA-level run pipeline.
                        {
                            const fn = handlers[kind];
                            if (fn)
                                yield Promise.resolve(fn(cta));
                        }
                        const ctaRun = cta.run;
                        yield runPipeline(ctaRun);
                    }
                    // After executing a CTA, advance based on explicit next* navigation or fallbacks.
                    const nav = cta;
                    if (nav.nextClose) {
                        this.closePanel();
                        return;
                    }
                    if (nav.nextId) {
                        const target = this.lastSuggestions.find((s) => s.id === nav.nextId);
                        const metaObj = ((target === null || target === void 0 ? void 0 : target.meta) || {});
                        const step = Number((_a = metaObj['step']) !== null && _a !== void 0 ? _a : 0);
                        if (Number.isFinite(step) && step > 0) {
                            this.currentStep = step;
                            this.renderStep();
                            return;
                        }
                    }
                    const advNum = Number((_b = nav.nextStep) !== null && _b !== void 0 ? _b : nav.advanceTo);
                    if (Number.isFinite(advNum) && advNum > 0) {
                        this.currentStep = advNum;
                        this.renderStep();
                    }
                }
                catch (e) {
                    this.bus.emit('error', e);
                }
                finally {
                    this.inflight = prevInflight;
                }
            });
        }
        buildTelemetry(target) {
            const el = target && target.nodeType === 1 ? target : null;
            let elementText = el ? (el.textContent || '').trim().slice(0, 400) : null;
            // For form controls (e.g., input/textarea), prefer their value when textContent is empty
            try {
                if (el && (!elementText || elementText.length === 0)) {
                    const anyEl = el;
                    const v = anyEl && typeof anyEl.value === 'string' ? anyEl.value : null;
                    if (v != null)
                        elementText = String(v).slice(0, 400);
                }
            }
            catch (_a) {
                /* ignore */
            }
            const elementHtml = el ? el.outerHTML.slice(0, 4000) : null; // cap size
            const attributes = el ? attrMap(el) : {};
            // Always include current path so rules can filter on it
            try {
                const p = window.location ? window.location.pathname : '/';
                attributes['path'] = normalizePath(p);
            }
            catch (_b) {
                /* ignore */
            }
            // Add session data to attributes for rule matching
            const timeOnPage = Math.floor((Date.now() - this.pageLoadTime) / 1000);
            attributes['timeOnPage'] = String(timeOnPage);
            attributes['clickCount'] = String(this.sessionData['clickCount'] || 0);
            attributes['scrollDepth'] = String(this.sessionData['scrollDepth'] || 0);
            try {
                const withAction = el === null || el === void 0 ? void 0 : el.closest('[data-action]');
                const action = withAction === null || withAction === void 0 ? void 0 : withAction.getAttribute('data-action');
                if (action && !('action' in attributes)) {
                    attributes['action'] = action;
                }
            }
            catch (_c) {
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
                    const matched = Array.isArray(rcRes.matchedRules)
                        ? rcRes.matchedRules
                        : [];
                    const topRuleId = matched.length
                        ? matched[matched.length - 1]
                        : undefined;
                    const sig = matched.join('|');
                    const isNewMatch = !!sig && sig !== this.lastMatchSig;
                    // Skip if this rule already triggered in this session (until route change)
                    if (topRuleId && this.triggeredRules.has(topRuleId)) {
                        return;
                    }
                    if (!rcRes.shouldProceed || (!this.canOpenPanel() && !isNewMatch)) {
                        return;
                    }
                    if (!topRuleId) {
                        return;
                    }
                    // Reset choice inputs when switching to a new rule
                    if (topRuleId !== this.lastRuleId) {
                        this.choiceInput = {};
                    }
                    const sgReq = {
                        siteId: this.opts.siteId,
                        url: window.location.origin + window.location.pathname,
                        ruleId: topRuleId,
                    };
                    const { suggestions } = (yield this.api.suggestGet(sgReq));
                    this.lastRuleId = topRuleId;
                    this.lastMatchSig = sig;
                    if (topRuleId)
                        this.triggeredRules.add(topRuleId);
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
        // Session tracking initialization
        initializeSessionTracking() {
            this.pageLoadTime = Date.now();
            // Track scroll depth
            if (this.allow.has('scroll')) {
                const onScroll = () => {
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
                    const scrollPercent = docHeight > 0 ? Math.round((scrollTop / docHeight) * 100) : 0;
                    this.sessionData['scrollDepth'] = Math.max(this.sessionData['scrollDepth'], scrollPercent);
                };
                window.addEventListener('scroll', onScroll, { passive: true });
                this.detachFns.push(() => window.removeEventListener('scroll', onScroll));
            }
            // Update time on site periodically
            const updateTimeOnSite = () => {
                this.sessionData['timeOnSite'] = Math.floor((Date.now() - this.pageLoadTime) / 1000);
            };
            const timeInterval = setInterval(updateTimeOnSite, 1000);
            this.detachFns.push(() => clearInterval(timeInterval));
        }
        // Setup time-based event triggers
        setupTimeBasedEvents() {
            const filters = this.focus.get('time_spent');
            if (!filters || filters.timeConditions.length === 0)
                return;
            // Find the minimum time threshold to start checking
            const minTime = Math.min(...filters.timeConditions.map((c) => c.value));
            const checkTimeConditions = () => {
                const timeOnPage = Math.floor((Date.now() - this.pageLoadTime) / 1000);
                // Check for newly crossed time thresholds
                const newlyTriggeredThresholds = filters.timeConditions.filter(({ op, value }) => {
                    // Skip if we've already triggered this threshold
                    if (this.triggeredTimeThresholds.has(value))
                        return false;
                    // Check if we've just crossed this threshold
                    switch (op) {
                        case 'gt':
                            return timeOnPage > value;
                        case 'gte':
                            return timeOnPage >= value;
                        case 'lt':
                            return timeOnPage < value;
                        case 'lte':
                            return timeOnPage <= value;
                        default:
                            return false;
                    }
                });
                // If we have newly triggered thresholds and path matches
                if (newlyTriggeredThresholds.length > 0 &&
                    this.pathMatches('time_spent') &&
                    !this.inflight) {
                    // Mark these thresholds as triggered
                    newlyTriggeredThresholds.forEach(({ value }) => {
                        this.triggeredTimeThresholds.add(value);
                    });
                    this.schedule(() => this.handleEvent('time_spent', document.body));
                }
            };
            // Start checking after the minimum time threshold
            const timerId = setTimeout(() => {
                checkTimeConditions();
                // Continue checking every second
                const intervalId = setInterval(checkTimeConditions, 1000);
                this.detachFns.push(() => clearInterval(intervalId));
            }, minTime * 1000);
            this.detachFns.push(() => clearTimeout(timerId));
        }
        // Enhanced event handling with advanced conditions
        handleEventWithAdvancedConditions(kind, target) {
            return __awaiter(this, void 0, void 0, function* () {
                const timeOnPage = Math.floor((Date.now() - this.pageLoadTime) / 1000);
                // Check if advanced conditions are met
                const conditionsMet = evaluateAdvancedConditions(this.focus, kind, {
                    timeOnPage,
                    sessionData: this.sessionData,
                });
                if (!conditionsMet)
                    return;
                // Proceed with normal event handling
                return this.handleEvent(kind, target);
            });
        }
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
