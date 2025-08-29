/**
 * Auto Assistant SDK (Generic, cart-agnostic)
 * ---------------------------------------------------------
 * - Observes DOM events (click, input/change, submit, route changes)
 * - POSTs /rule/check (Event enum + string-only telemetry)
 * - If shouldProceed: POSTs /suggest/get, handles ask → final
 * - Optional rendering into a panel container
 *
 * Defaults:
 *   baseUrl: http://localhost:4000  (FastAPI; /suggest/get proxies to agent)
 *
 * OpenAPI types are imported only for compile-time safety.
 */

import type { components } from '@domsphere/api-client';

/* ========== OpenAPI Type Aliases ========== */
export type EventSchema = components['schemas']['Event'];
export type RuleCheckRequest = components['schemas']['RuleCheckRequest'];
export type RuleCheckResponse = components['schemas']['RuleCheckResponse'];
export type SuggestGetRequest = components['schemas']['SuggestGetRequest'];
export type SuggestGetResponse = components['schemas']['SuggestGetResponse'];
export type Turn = components['schemas']['Turn'];
export type Suggestion = components['schemas']['Suggestion'];
export type Action = components['schemas']['Action'];
export type FormSpec = components['schemas']['FormSpec'];
export type UIHint = components['schemas']['UIHint'];

/* ========== Small utils ========== */
type HeadersLoose = Record<string, string | undefined>;

async function postJson<TReq, TRes>(
  baseUrl: string,
  path: string,
  body: TReq,
  headers: HeadersLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}

// Helper for GET requests returning JSON
async function getJson<TRes>(
  baseUrl: string,
  path: string,
  headers: HeadersLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json', ...headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}
// Minimal type for the rule-track profile
export type RuleTrackProfile = {
  siteId: string;
  status: 'on' | 'off';
  version?: string | null;
  updatedAt?: string | null;
  events?: Record<string, string[]> | null;
};

/* ========== API client (headers) ========== */
export type ClientOptions = {
  baseUrl?: string; // default http://localhost:4000
  contractVersion?: string | null; // -> X-Contract-Version
  requestIdFactory?: () => string; // -> X-Request-Id
  fetchHeaders?: Record<string, string>;
};

export function createApi(opts: ClientOptions) {
  const {
    baseUrl = 'http://localhost:4000',
    contractVersion = null,
    requestIdFactory,
    fetchHeaders = {},
  } = opts;

  const headers = (): HeadersLoose => ({
    'X-Contract-Version': contractVersion ?? undefined,
    'X-Request-Id': requestIdFactory?.(),
    ...fetchHeaders,
  });

  return {
    ruleCheck: (body: RuleCheckRequest) =>
      postJson<RuleCheckRequest, RuleCheckResponse>(
        baseUrl,
        '/rule/check',
        body,
        headers()
      ),
    suggestGet: (body: SuggestGetRequest) =>
      postJson<SuggestGetRequest, SuggestGetResponse>(
        baseUrl,
        '/suggest/get',
        body,
        headers()
      ),
    ruleTrackGet: () =>
      getJson<RuleTrackProfile>(baseUrl, '/rule/track', headers()),
  };
}

/* ========== Tiny event bus ========== */
// Generic listener that accepts unknown args to avoid `any`
type Listener = (...args: unknown[]) => void;
class Emitter {
  private m = new Map<string, Set<Listener>>();
  on(evt: string, fn: Listener) {
    if (!this.m.has(evt)) this.m.set(evt, new Set());
    const set = this.m.get(evt);
    if (set) set.add(fn);
    else this.m.set(evt, new Set([fn]));
    return () => this.off(evt, fn);
  }
  off(evt: string, fn: Listener) {
    this.m.get(evt)?.delete(fn);
  }
  emit(evt: string, ...a: unknown[]) {
    this.m.get(evt)?.forEach((fn) => {
      try {
        fn(...a);
      } catch {
        /* empty */
      }
    });
  }
}

/* ========== Telemetry builders (string-only) ========== */
function safeStr(v: unknown): string | null {
  if (v == null) return null;
  try {
    const t = typeof v;
    if (t === 'string') return v as string;
    if (t === 'number' || t === 'boolean') return String(v);
    // compress long HTML/text
    const s = JSON.stringify(v);
    return s.length > 5000 ? s.slice(0, 5000) : s;
  } catch {
    return null;
  }
}

function cssPath(el: Element): string | null {
  try {
    const parts: string[] = [];
    let node: Element | null = el;
    while (node && node.nodeType === 1) {
      const name = node.nodeName.toLowerCase();
      let selector = name;
      if (node.id) {
        selector += `#${node.id}`;
        parts.unshift(selector);
        break;
      } else {
        let sib: Element | null = node;
        let nth = 1;
        while ((sib = sib.previousElementSibling as Element | null)) {
          if (sib.nodeName.toLowerCase() === name) nth++;
        }
        selector += `:nth-of-type(${nth})`;
      }
      parts.unshift(selector);
      node = node.parentElement;
    }
    return parts.join(' > ');
  } catch {
    return null;
  }
}

function xPath(el: Element): string | null {
  try {
    if ((document as Document & { evaluate?: unknown }).evaluate) {
      const xpath = (start: Node): string => {
        let node: Node | null = start;
        if (node === document.body) return '/html/body';
        const ix = (sibling: Node | null, name: string): number => {
          let i = 1;
          for (; sibling; sibling = sibling.previousSibling) {
            if (sibling.nodeName === name) i++;
          }
          return i;
        };
        const segs: string[] = [];
        for (; node && (node as Element).nodeType === 1; ) {
          const cur = node as Element;
          const name = node.nodeName.toLowerCase();
          segs.unshift(`${name}[${ix(node, name.toUpperCase())}]`);
          node = cur.parentElement;
        }
        return '/' + segs.join('/');
      };
      return xpath(el);
    }
    return null;
  } catch {
    return null;
  }
}

function attrMap(el: Element): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  try {
    for (const a of Array.from(el.attributes)) {
      out[a.name] = a.value ?? null;
    }
  } catch {
    /* empty */
  }
  return out;
}

function nearbyText(el: Element): string[] {
  const texts: string[] = [];
  try {
    const grab = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const t = (node.textContent || '').trim();
        if (t) texts.push(t);
      }
    };
    // siblings text samples
    if (el.parentElement) {
      Array.from(el.parentElement.childNodes).forEach((n) => grab(n));
    }
    return texts.slice(0, 5);
  } catch {
    return [];
  }
}

function ancestorBrief(el: Element): Array<Record<string, string | null>> {
  const arr: Array<Record<string, string | null>> = [];
  try {
    let p: Element | null = el.parentElement;
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
  } catch {
    /* empty */
  }
  return arr;
}

// Parse the first integer from a string, or null if none.
function firstInt(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = text.match(/\d+/);
  if (!m) return null;
  const n = parseInt(m[0], 10);
  return Number.isFinite(n) ? n : null;
}

/* ========== SDK ========== */
export type AutoAssistantOptions = ClientOptions & {
  siteId: string;
  sessionId: string;

  // Optional render target for ask/final turns
  panelSelector?: string;

  // Debounce for deduping rapid events
  debounceMs?: number; // default 150

  // Cooldown after a final turn before new convo can start
  finalCooldownMs?: number; // default 30000

  // You can provide base context that always goes to /suggest/get
  baseContext?: Record<string, unknown>;
};

type EventKind =
  | 'dom_click'
  | 'input_change'
  | 'submit'
  | 'page_load'
  | 'route_change';

export class AutoAssistant {
  private api: ReturnType<typeof createApi>;
  private bus = new Emitter();
  private opts: Required<
    Pick<
      AutoAssistantOptions,
      'siteId' | 'sessionId' | 'debounceMs' | 'finalCooldownMs'
    >
  > &
    AutoAssistantOptions;

  private detachFns: Array<() => void> = [];
  private debTimer?: number;
  private inflight = false;
  private lastContext = {
    matchedRules: [] as string[],
    eventType: 'page_load' as string,
  };
  private activeTurn?: Turn;
  private cooldownUntil = 0;

  private trackProfile?: RuleTrackProfile;
  private trackOn = false;
  private selClick: string[] = [];
  private selMutation: string[] = [];

  constructor(options: AutoAssistantOptions) {
    this.opts = {
      debounceMs: options.debounceMs ?? 150,
      finalCooldownMs: options.finalCooldownMs ?? 30000,
      ...options,
    };
    this.api = createApi(options);
  }

  on(
    evt:
      | 'rule:checked'
      | 'turn:ask'
      | 'turn:final'
      | 'turn:cleared'
      | 'suggest:ready'
      | 'error',
    fn: Listener
  ) {
    return this.bus.on(evt, fn);
  }

  private matchesAny(
    target: Element | undefined,
    selectors: string[]
  ): boolean {
    if (!target) return false;
    for (const sel of selectors) {
      try {
        if (target.closest(sel)) return true;
      } catch {
        /* invalid selector */
      }
    }
    return false;
  }

  async start() {
    // 0) Fetch track profile first; if fetch fails, default to rich mode (off)
    try {
      const prof = await this.api.ruleTrackGet();
      this.trackProfile = prof;
      this.trackOn = prof?.status === 'on';
      const ev = (prof?.events || {}) as Record<string, unknown>;
      this.selClick = Array.isArray(ev['dom_click'])
        ? (ev['dom_click'] as string[])
        : [];
      this.selMutation = Array.isArray(ev['mutation'])
        ? (ev['mutation'] as string[])
        : [];
    } catch {
      this.trackOn = false; // rich mode fallback
      this.selClick = [];
      this.selMutation = [];
    }

    // 1) Only send page_load when rich mode (track off)
    if (!this.trackOn) {
      this.schedule(() =>
        this.handleEvent('page_load', document.body || undefined)
      );
    }

    // Clicks
    const onClick = (e: Event) => {
      const tgt = e.target as Element | undefined;
      if (this.trackOn && !this.matchesAny(tgt, this.selClick)) return;
      this.schedule(() => this.handleEvent('dom_click', tgt));
    };
    document.addEventListener('click', onClick, true);
    this.detachFns.push(() =>
      document.removeEventListener('click', onClick, true)
    );

    // Input / change
    const onChange = (e: Event) => {
      if (this.trackOn) return;
      this.schedule(() =>
        this.handleEvent('input_change', e.target as Element | undefined)
      );
    };
    document.addEventListener('input', onChange, true);
    document.addEventListener('change', onChange, true);
    this.detachFns.push(() =>
      document.removeEventListener('input', onChange, true)
    );
    this.detachFns.push(() =>
      document.removeEventListener('change', onChange, true)
    );

    // Submit
    const onSubmit = (e: Event) => {
      if (this.trackOn) return;
      this.schedule(() =>
        this.handleEvent('submit', e.target as Element | undefined)
      );
    };
    document.addEventListener('submit', onSubmit, true);
    this.detachFns.push(() =>
      document.removeEventListener('submit', onSubmit, true)
    );

    // Basic route changes (SPA)
    const _push = history.pushState;
    const _replace = history.replaceState;
    history.pushState = function (
      this: History,
      data: unknown,
      unused: string,
      url?: string | URL | null
    ) {
      const r = _push.apply(this, [data, unused, url]);
      window.dispatchEvent(new Event('agent-route-change'));
      return r;
    };
    history.replaceState = function (
      this: History,
      data: unknown,
      unused: string,
      url?: string | URL | null
    ) {
      const r = _replace.apply(this, [data, unused, url]);
      window.dispatchEvent(new Event('agent-route-change'));
      return r;
    };
    const onPop = () => {
      if (this.trackOn) return;
      this.schedule(() => this.handleEvent('route_change', undefined));
    };
    window.addEventListener('popstate', onPop);
    window.addEventListener('agent-route-change', onPop as EventListener);
    this.detachFns.push(() => {
      window.removeEventListener('popstate', onPop);
      window.removeEventListener('agent-route-change', onPop as EventListener);
      history.pushState = _push;
      history.replaceState = _replace;
    });

    // Generic DOM mutation detection (MutationObserver)
    try {
      const pickTarget = (n?: Node | null): Element | undefined => {
        if (!n) return undefined;
        if (n.nodeType === Node.ELEMENT_NODE) return n as Element;
        if (n.nodeType === Node.TEXT_NODE)
          return (n.parentElement || undefined) as Element | undefined;
        return undefined;
      };
      const mutObserver = new MutationObserver((muts) => {
        const raw = muts[0]?.target as Node | undefined;
        const tgt = pickTarget(raw);
        // Only send when mutation target matches configured selectors in focus mode
        if (this.trackOn && !this.matchesAny(tgt, this.selMutation)) return;
        this.schedule(() => this.handleEvent('dom_click', tgt));
      });
      mutObserver.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
      });
      this.detachFns.push(() => mutObserver.disconnect());
    } catch {
      // ignore if observer cannot start
    }
  }

  stop() {
    this.detachFns.forEach((f) => {
      try {
        f();
      } catch {
        /* empty */
      }
    });
    this.detachFns = [];
    if (this.debTimer) window.clearTimeout(this.debTimer);
  }

  /** Answer an ask turn (chips/buttons) */
  async answerAsk(
    turn: Turn,
    action: Action | { id: string; label?: string; value?: unknown }
  ) {
    try {
      const { siteId, sessionId, baseContext } = this.opts;
      const req: SuggestGetRequest = {
        siteId,
        sessionId,
        prevTurnId: turn.turnId,
        answers: {
          choice: action.id,
          value: (isActionWithValue(action) ? action.value : undefined) as
            | string
            | number
            | boolean
            | null
            | undefined,
        },
        context: { ...(baseContext ?? {}) },
      };
      const { turn: next } = await this.api.suggestGet(req);
      this.setActiveTurn(next);
    } catch (e) {
      this.bus.emit('error', e);
    }
  }

  /** Answer an ask turn via form submission */
  private async answerForm(turn: Turn, formData: FormData) {
    try {
      const { siteId, sessionId, baseContext } = this.opts;
      const answers: Record<string, unknown> = {};
      const keys: string[] = [];
      formData.forEach((_, key) => {
        if (!keys.includes(key)) keys.push(key);
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
      const req: SuggestGetRequest = {
        siteId,
        sessionId,
        prevTurnId: turn.turnId,
        answers,
        context: { ...(baseContext ?? {}) },
      };
      const { turn: next } = await this.api.suggestGet(req);
      this.setActiveTurn(next);
    } catch (e) {
      this.bus.emit('error', e);
    }
  }

  /* ========== internals ========== */

  private schedule(fn: () => void) {
    if (this.debTimer) window.clearTimeout(this.debTimer);
    this.debTimer = window.setTimeout(fn, this.opts.debounceMs);
  }

  private canOpenConversation(): boolean {
    if (!this.activeTurn) return Date.now() >= this.cooldownUntil;
    if (this.activeTurn.status === 'ask') return false;
    return Date.now() >= this.cooldownUntil;
  }

  private panelEl(): HTMLElement | null {
    const sel = this.opts.panelSelector;
    return sel ? (document.querySelector(sel) as HTMLElement | null) : null;
  }

  private setActiveTurn(turn?: Turn) {
    this.activeTurn = turn;
    const panel = this.panelEl();
    if (!panel) {
      if (turn?.status === 'ask') this.bus.emit('turn:ask', turn);
      else if (turn?.status === 'final') {
        this.bus.emit('suggest:ready', turn.suggestions ?? [], turn);
        this.bus.emit('turn:final', turn);
        this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
      } else {
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
      renderAskTurn(
        panel,
        turn,
        (a) => this.answerAsk(turn, a),
        (fd) => this.answerForm(turn, fd as FormData)
      );
      this.bus.emit('turn:ask', turn);
    } else {
      renderFinalSuggestions(panel, turn.suggestions ?? [], () => undefined);
      this.bus.emit('suggest:ready', turn.suggestions ?? [], turn);
      this.bus.emit('turn:final', turn);
      this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
    }
  }

  private buildTelemetry(target?: Element): EventSchema['telemetry'] {
    const el = target && target.nodeType === 1 ? (target as Element) : null;
    const elementText = el ? (el.textContent || '').trim().slice(0, 400) : null;
    const elementHtml = el ? el.outerHTML.slice(0, 4000) : null; // cap size
    const attributes: Record<string, string | null> = el ? attrMap(el) : {};
    // Promote semantic action into telemetry.attributes.action (without changing event.type)
    try {
      const withAction = el?.closest('[data-action]') as HTMLElement | null;
      const action = withAction?.getAttribute('data-action');
      if (action && !('action' in attributes)) {
        attributes['action'] = action;
      }
    } catch {
      /* empty */
    }
    // Surface numeric values from likely counter elements into attributes (generic)
    try {
      const candidates: Element[] = [];

      // (a) Always consider the event target and a few ancestors
      if (el) {
        candidates.push(el);
        let p: Element | null = el.parentElement;
        let hops = 0;
        while (p && hops < 4) {
          candidates.push(p);
          p = p.parentElement;
          hops++;
        }
      }

      // (b) If a server-provided tracking profile is ON, include configured mutation selectors
      try {
        const want = this.selMutation as string[] | undefined;
        const isOn = !!this.trackOn;
        if (isOn && Array.isArray(want) && want.length) {
          for (const sel of want) {
            try {
              document.querySelectorAll(sel).forEach((node) => {
                if (node instanceof Element) candidates.push(node);
              });
            } catch {
              /* invalid selector from server; ignore */
            }
          }
        }
      } catch {
        /* ignore */
      }

      // Deduplicate
      const uniq: Element[] = Array.from(new Set(candidates));

      // Helper: choose a stable attribute key for a numeric element
      const pickKey = (cand: Element): string | null => {
        const id = (cand as HTMLElement).id || '';
        if (id) return id;
        // prefer semantic data-* keys
        const dataNames: string[] = [];
        for (const a of Array.from(cand.attributes)) {
          if (a.name.startsWith('data-'))
            dataNames.push(a.name.replace(/^data-/, ''));
        }
        const pref = dataNames.find((n) =>
          /^(name|counter|count|qty|quantity|total|badge|value)$/i.test(n)
        );
        if (pref) return pref;
        if (dataNames.length) return dataNames[0];
        const cls = (cand.getAttribute('class') || '').trim();
        if (cls) return cls.split(/\s+/)[0];
        return cand.tagName ? cand.tagName.toLowerCase() : null;
      };

      for (const cand of uniq) {
        const txt = (cand.textContent || '').trim();
        const n = firstInt(txt);
        if (n == null) continue; // not a simple numeric text
        const key = pickKey(cand);
        if (!key) continue;
        // camelCase the key: cart-count -> cartCount, total_qty -> totalQty
        const camel = key
          .replace(/[^a-zA-Z0-9]+(.)/g, (_, c) =>
            c ? String(c).toUpperCase() : ''
          )
          .replace(/^(.)/, (m) => m.toLowerCase());
        attributes[camel] = String(n);
      }
    } catch {
      /* best-effort only */
    }
    const css = el ? cssPath(el) : null;
    const xp = el ? xPath(el) : null;
    const near = el ? nearbyText(el) : [];
    const ancs = el ? ancestorBrief(el) : [];

    // ensure strings or nulls
    const toStr = (obj: Record<string, string | null>) =>
      Object.fromEntries(
        Object.entries(obj).map(([k, v]) => [k, v == null ? null : String(v)])
      );

    return {
      elementText: safeStr(elementText),
      elementHtml: safeStr(elementHtml),
      attributes: toStr(attributes),
      cssPath: safeStr(css),
      xpath: safeStr(xp),
      nearbyText: near.map((t) => String(t)).slice(0, 5),
      ancestors: ancs.map((a) =>
        Object.fromEntries(
          Object.entries(a).map(([k, v]) => [k, v == null ? null : String(v)])
        )
      ),
    } as EventSchema['telemetry'];
  }

  private async handleEvent(kind: EventKind, target?: Element) {
    // avoid concurrent runs
    if (this.inflight) return;
    this.inflight = true;

    try {
      // 1) rule check
      const rcReq: RuleCheckRequest = {
        siteId: this.opts.siteId,
        sessionId: this.opts.sessionId,
        event: {
          type: kind,
          ts: Date.now(),
          telemetry: this.buildTelemetry(target),
        } as EventSchema,
      };

      const rcRes = await this.api.ruleCheck(rcReq);
      this.bus.emit('rule:checked', rcRes);

      this.lastContext = {
        matchedRules: rcRes.matchedRules,
        eventType: rcRes.eventType,
      };

      // 2) ask agent only if rules pass + allowed by cooldown/turn state
      if (!rcRes.shouldProceed || !this.canOpenConversation()) {
        if (!rcRes.shouldProceed) this.setActiveTurn(undefined);
        return;
      }

      const sgReq: SuggestGetRequest = {
        siteId: this.opts.siteId,
        sessionId: this.opts.sessionId,
        context: {
          matchedRules: rcRes.matchedRules,
          eventType: rcRes.eventType,
          ...(this.opts.baseContext ?? {}),
        },
      };

      const { turn } = await this.api.suggestGet(sgReq);
      this.setActiveTurn(turn);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = false;
    }
  }
}

// Type guard to safely read optional `value` from action-like inputs
function isActionWithValue(
  a: Action | { id: string; label?: string; value?: unknown }
): a is { id: string; label?: string; value?: unknown } {
  return typeof (a as { value?: unknown }).value !== 'undefined';
}

/* ========== Minimal render helpers (generic) ========== */
export function renderAskTurn(
  container: HTMLElement,
  turn: Turn,
  onAction: (action: Action) => void,
  onSubmitForm?: (form: FormData) => void
) {
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

  if (turn.actions?.length) {
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

  if (turn.form?.fields?.length) {
    const form = document.createElement('form');
    form.style.marginTop = '12px';

    if (turn.form.title) {
      const title = document.createElement('div');
      title.textContent = turn.form.title;
      title.style.fontWeight = '600';
      form.appendChild(title);
    }

    turn.form.fields.forEach((f) => {
      const wrap = document.createElement('div');
      wrap.style.marginTop = '8px';
      const label = document.createElement('label');
      label.textContent = f.label + (f.required ? ' *' : '');
      label.style.display = 'block';
      label.style.marginBottom = '4px';
      wrap.appendChild(label);

      let input: HTMLElement;
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
          (f.options ?? []).forEach((opt) => {
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
          (el as HTMLInputElement).name = f.key;
          input = el;
          break;
        }
        case 'radio': {
          const group = document.createElement('div');
          (f.options ?? []).forEach((opt) => {
            const lbl = document.createElement('label');
            lbl.style.marginRight = '10px';
            const r = document.createElement('input');
            r.type = 'radio';
            (r as HTMLInputElement).name = f.key;
            (r as HTMLInputElement).value = String(opt.value);
            lbl.appendChild(r);
            lbl.append(' ' + opt.label);
            group.appendChild(lbl);
          });
          input = group;
          break;
        }
        default: {
          const el = document.createElement('input');
          el.type = 'text';
          (el as HTMLInputElement).name = f.key;
          input = el;
        }
      }
      wrap.appendChild(input);
      form.appendChild(wrap);
    });

    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.textContent = turn.form.submitLabel ?? 'Continue';
    submit.style.marginTop = '10px';
    submit.style.padding = '6px 10px';
    submit.style.borderRadius = '8px';
    submit.style.border = '1px solid #d1d5db';
    form.appendChild(submit);

    form.onsubmit = (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      onSubmitForm?.(fd);
    };

    panel.appendChild(form);
  }

  container.appendChild(panel);
}

export function renderFinalSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onCta: (
    cta:
      | NonNullable<Suggestion['actions']>[number]
      | NonNullable<Suggestion['primaryCta']>
  ) => void
) {
  container.innerHTML = '';
  if (!suggestions?.length) {
    container.innerHTML = `<div data-testid="assistant-empty">No suggestions</div>`;
    return;
  }

  const frag = document.createDocumentFragment();

  suggestions.forEach((s) => {
    const card = document.createElement('div');
    card.setAttribute('data-testid', 'assistant-card');
    card.style.border = '1px solid #e5e7eb';
    card.style.borderRadius = '12px';
    card.style.padding = '12px';
    card.style.margin = '8px 0';

    const title = document.createElement('div');
    title.textContent = s.title ?? s.type;
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
      ...(s.actions ?? []),
      ...(s.primaryCta ? [s.primaryCta] : []),
    ].filter(Boolean) as Array<
      NonNullable<typeof s.actions>[number] | NonNullable<typeof s.primaryCta>
    >;

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

/* ========== UMD convenience ========== */
declare global {
  interface Window {
    AgentSDK?: unknown;
  }
}
if (typeof window !== 'undefined') {
  window.AgentSDK = {
    AutoAssistant,
    renderAskTurn,
    renderFinalSuggestions,
    createApi,
  };
}
