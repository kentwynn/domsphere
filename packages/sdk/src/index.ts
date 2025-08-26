/**
 * Auto Assistant SDK (POC)
 * - Self-detects cart changes (clicks + MutationObserver)
 * - Calls /rule/check then /suggest/get (returns { turn })
 * - Supports ask -> final micro-conversation via answerAsk()
 * - Minimal render helpers for ask + final turns
 *
 * Build-ready for Nx + Rollup. Only type-imports from api-client.
 */

import type { components } from '@domsphere/api-client'; // <-- change if your alias differs

/* =========================
 * OpenAPI Type Aliases
 * ========================= */
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

/* =========================
 * Small utils
 * ========================= */
const clamp = (n: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, n));
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

/* =========================
 * API client (headers per schema)
 * ========================= */
export type ClientOptions = {
  baseUrl: string;
  contractVersion?: string | null; // -> X-Contract-Version
  requestIdFactory?: () => string; // -> X-Request-Id
  fetchHeaders?: Record<string, string>;
};

export function createApi(opts: ClientOptions) {
  const {
    baseUrl,
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
  };
}

/* =========================
 * Tiny event bus
 * ========================= */
type Listener = (...args: any[]) => void;
class Emitter {
  private m = new Map<string, Set<Listener>>();
  on(evt: string, fn: Listener) {
    if (!this.m.has(evt)) this.m.set(evt, new Set());
    this.m.get(evt)!.add(fn);
    return () => this.off(evt, fn);
  }
  off(evt: string, fn: Listener) {
    this.m.get(evt)?.delete(fn);
  }
  emit(evt: string, ...a: any[]) {
    this.m.get(evt)?.forEach((fn) => {
      try {
        fn(...a);
      } catch {
        /* empty */
      }
    });
  }
}

/* =========================
 * Auto Assistant
 * ========================= */
export type AutoAssistantOptions = ClientOptions & {
  siteId: string;
  sessionId: string;

  selectors?: {
    addButton?: string; // clicks imply +1
    removeButton?: string; // clicks imply -1
    cartCounter?: string; // read textContent as number
    cartItem?: string; // count elements when no counter
    panelSelector?: string; // optional container to render into
  };

  minCountToProceed?: number; // default 2
  debounceMs?: number; // default 250

  /** Stuff you want to attach to /suggest/get context */
  baseContext?: Record<string, unknown>;
};

export class AutoAssistant {
  private api: ReturnType<typeof createApi>;
  private bus = new Emitter();
  private opts: Required<
    Pick<
      AutoAssistantOptions,
      'siteId' | 'sessionId' | 'minCountToProceed' | 'debounceMs'
    >
  > &
    AutoAssistantOptions;

  private detachFns: Array<() => void> = [];
  private mo?: MutationObserver;
  private inflight = 0;
  private lastCount = 0;
  private debTimer?: number;
  private lastTurn?: Turn; // remember last turn (ask/final)

  constructor(options: AutoAssistantOptions) {
    this.opts = {
      ...options,
      minCountToProceed: options.minCountToProceed ?? 2,
      debounceMs: options.debounceMs ?? 250,
      selectors: {
        addButton: "[data-testid='add']",
        removeButton: "[data-testid='remove']",
        cartCounter: '#cart-count',
        cartItem: "[data-testid='cart-item']",
        panelSelector: '#suggestions',
        ...(options.selectors ?? {}),
      },
    };
    this.api = createApi(options);
  }

  on(
    evt:
      | 'cart:changed'
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

  /** Start auto-detection */
  start() {
    const { addButton, removeButton, cartCounter, cartItem } =
      this.opts.selectors!;

    if (addButton) this.attach('click', addButton, () => this.bumpCount(+1));
    if (removeButton)
      this.attach('click', removeButton, () => this.bumpCount(-1));

    this.mo = new MutationObserver(() => this.scheduleProcess());
    const observeTargets: Element[] = [];
    if (cartCounter) {
      const el = document.querySelector(cartCounter);
      if (el) observeTargets.push(el);
    }
    if (cartItem) {
      document
        .querySelectorAll(cartItem)
        .forEach((el) => observeTargets.push(el));
    }
    observeTargets.forEach((el) =>
      this.mo!.observe(el, {
        childList: true,
        characterData: true,
        subtree: true,
      })
    );

    this.scheduleProcess(true);
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
    this.mo?.disconnect();
    if (this.debTimer) window.clearTimeout(this.debTimer);
  }

  /** Continue the ask flow: send the chosen action back to /suggest/get */
  async answerAsk(
    turn: Turn,
    action: Action | { id: string; label?: string; value?: unknown }
  ) {
    const { siteId, sessionId, baseContext } = this.opts;

    const req: SuggestGetRequest = {
      siteId,
      sessionId,
      prevTurnId: turn.turnId,
      answers: { choice: action.id, value: (action as any).value },
      context: { ...(this.opts.baseContext ?? {}) },
    };

    try {
      const { turn: next } = await this.api.suggestGet(req);
      this.lastTurn = next;
      if (next.status === 'ask') {
        this.bus.emit('turn:ask', next);
        const panel = this.panelEl();
        if (panel) renderAskTurn(panel, next, (a) => this.answerAsk(next, a));
      } else {
        const suggestions = next.suggestions ?? [];
        this.bus.emit('suggest:ready', suggestions, next);
        this.bus.emit('turn:final', next);
        const panel = this.panelEl();
        if (panel)
          renderFinalSuggestions(
            panel,
            suggestions,
            (cta) => this.bus.emit('sdk:action', cta),
            next
          );
      }
    } catch (e) {
      this.bus.emit('error', e);
    }
  }

  /* ---------------- internals ---------------- */

  private attach(evt: string, selector: string, handler: EventListener) {
    const fn = (e: Event) => {
      const t = e.target as Element | null;
      if (!t) return;
      if (t.closest(selector)) handler(e);
    };
    document.addEventListener(evt, fn, true);
    this.detachFns.push(() => document.removeEventListener(evt, fn, true));
  }

  private readCount(): number {
    const { cartCounter, cartItem } = this.opts.selectors!;
    if (cartCounter) {
      const el = document.querySelector(cartCounter);
      if (el) {
        const n = parseInt((el.textContent || '0').replace(/\D+/g, ''), 10);
        if (!Number.isNaN(n)) return n;
      }
    }
    if (cartItem) {
      const n = document.querySelectorAll(cartItem).length;
      if (n >= 0) return n;
    }
    return this.lastCount;
  }

  private bumpCount(delta: number) {
    this.lastCount = clamp(this.lastCount + delta, 0, 9999);
    this.scheduleProcess(true);
  }

  private scheduleProcess(force = false) {
    if (this.debTimer) window.clearTimeout(this.debTimer);
    this.debTimer = window.setTimeout(
      () => this.process(force),
      this.opts.debounceMs
    );
  }

  private async process(force = false) {
    const count = this.readCount();
    const changed = force || count !== this.lastCount;
    this.lastCount = count;
    if (!changed) return;

    this.bus.emit('cart:changed', count);

    if (count < this.opts.minCountToProceed) {
      this.bus.emit('turn:cleared');
      const panel = this.panelEl();
      if (panel) panel.innerHTML = '';
      return;
    }

    if (this.inflight > 0) return;
    this.inflight++;

    try {
      await this.runFlow(count);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = 0;
    }
  }

  private async runFlow(count: number) {
    const { siteId, sessionId } = this.opts;

    // 1) /rule/check
    const rcReq: RuleCheckRequest = {
      siteId,
      sessionId,
      event: {
        type: 'dom_click',
        ts: Date.now(),
        telemetry: {
          attributes: { cartCount: String(count) },
        } as EventSchema['telemetry'],
      } as EventSchema,
    };
    const rcRes = await this.api.ruleCheck(rcReq);
    this.bus.emit('rule:checked', rcRes);

    if (!rcRes.shouldProceed) {
      this.bus.emit('turn:cleared');
      const panel = this.panelEl();
      if (panel) panel.innerHTML = '';
      return;
    }

    // 2) /suggest/get (first turn)
    const sgReq: SuggestGetRequest = {
      siteId,
      sessionId,
      context: {
        matchedRules: rcRes.matchedRules,
        eventType: rcRes.eventType,
        ...(this.opts.baseContext ?? {}),
      },
    };

    const { turn } = await this.api.suggestGet(sgReq);
    this.lastTurn = turn;

    if (turn.status === 'ask') {
      this.bus.emit('turn:ask', turn);
      const panel = this.panelEl();
      if (panel) renderAskTurn(panel, turn, (a) => this.answerAsk(turn, a));
    } else {
      const suggestions = turn.suggestions ?? [];
      this.bus.emit('suggest:ready', suggestions, turn);
      this.bus.emit('turn:final', turn);
      const panel = this.panelEl();
      if (panel)
        renderFinalSuggestions(
          panel,
          suggestions,
          (cta) => this.bus.emit('sdk:action', cta),
          turn
        );
    }
  }

  private panelEl(): HTMLElement | null {
    const sel = this.opts.selectors?.panelSelector;
    return sel ? (document.querySelector(sel) as HTMLElement | null) : null;
  }
}

/* =========================
 * Render helpers (optional)
 * ========================= */

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
      btn.setAttribute('data-action-id', a.id);
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
          (f.options ?? []).forEach((opt, i) => {
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
        case 'number':
        case 'range':
        case 'toggle':
        case 'text':
        default: {
          const el = document.createElement('input');
          el.type = f.type === 'number' ? 'number' : 'text';
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
  ) => void,
  turn?: Turn
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

    if (typeof s.price === 'number') {
      const price = document.createElement('div');
      price.textContent = s.currency
        ? `${s.price} ${s.currency}`
        : `${s.price}`;
      price.style.marginTop = '6px';
      card.appendChild(price);
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

/* =========================
 * UMD convenience (optional)
 * ========================= */
declare global {
  interface Window {
    AgentSDK?: any;
  }
}
if (typeof window !== 'undefined') {
  (window as any).AgentSDK = {
    AutoAssistant,
    renderAskTurn,
    renderFinalSuggestions,
    createApi,
  };
}
