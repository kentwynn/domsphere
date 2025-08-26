/**
 * Auto Assistant SDK (POC)
 * - Self-detects cart changes (clicks + MutationObserver)
 * - Calls /rule/check then /suggest/get when rule passes
 * - Optional minimal UI render to a panel
 *
 * Build: Nx Rollup (esm/cjs) + your UMD step
 */

// CHANGE THIS IMPORT if your api-client package name differs:
import type { components } from '@domsphere/api-client';

/* =========================
 * Types from OpenAPI
 * ========================= */
export type RuleCheckRequest = components['schemas']['RuleCheckRequest'];
export type RuleCheckResponse = components['schemas']['RuleCheckResponse'];
export type SuggestGetRequest = components['schemas']['SuggestGetRequest'];
export type SuggestGetResponse = components['schemas']['SuggestGetResponse'];
export type Suggestion = components['schemas']['Suggestion'];
export type EventSchema = components['schemas']['Event'];
export type SuggestGetContext = components['schemas']['SuggestGetContext'];

/* =========================
 * Small helpers
 * ========================= */
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const clamp = (n: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, n));

type HeadersInitLoose = Record<string, string | undefined | null>;
async function postJson<TReq, TRes>(
  baseUrl: string,
  path: string,
  body: TReq,
  headers: HeadersInitLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...Object.fromEntries(
        Object.entries(headers).filter(([, v]) => v != null)
      ),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}

/* =========================
 * API client
 * ========================= */
export type ClientOptions = {
  baseUrl: string;
  siteKey?: string | null; // -> X-Site-Key
  contractVersion?: string | null; // -> X-Contract-Version
  requestIdFactory?: () => string; // -> X-Request-Id
  fetchHeaders?: Record<string, string>;
};

function createApi(opts: ClientOptions) {
  const {
    baseUrl,
    siteKey = null,
    contractVersion = null,
    requestIdFactory,
    fetchHeaders = {},
  } = opts;

  const headers = (): HeadersInitLoose => ({
    'X-Site-Key': siteKey ?? undefined,
    'X-Contract-Version': contractVersion ?? undefined,
    'X-Request-Id': requestIdFactory?.(),
    ...fetchHeaders,
  });

  return {
    ruleCheck(body: RuleCheckRequest) {
      return postJson<RuleCheckRequest, RuleCheckResponse>(
        baseUrl,
        '/rule/check',
        body,
        headers()
      );
    },
    suggestGet(body: SuggestGetRequest) {
      return postJson<SuggestGetRequest, SuggestGetResponse>(
        baseUrl,
        '/suggest/get',
        body,
        headers()
      );
    },
  };
}

/* =========================
 * Event bus (tiny)
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

  /** DOM hooks (override as needed for your demo page) */
  selectors?: {
    addButton?: string; // clicks on these imply +1
    removeButton?: string; // clicks on these imply -1
    cartCounter?: string; // read the textContent as number
    cartItem?: string; // count elements as number
    panelSelector?: string; // optional: where to render suggestions
  };

  /** Rule trigger: required count to proceed (default 2) */
  minCountToProceed?: number;

  /** Debounce for cart change detection */
  debounceMs?: number;

  /** Additional context to include in /suggest/get */
  baseContext?: Partial<SuggestGetContext> & Record<string, any>;
};

export class AutoAssistant {
  private api: ReturnType<typeof createApi>;
  private opts: Required<
    Pick<
      AutoAssistantOptions,
      'siteId' | 'sessionId' | 'minCountToProceed' | 'debounceMs'
    >
  > &
    AutoAssistantOptions;

  private bus = new Emitter();
  private detachFns: Array<() => void> = [];
  private mo?: MutationObserver;
  private inflight = 0;
  private lastCount = 0;
  private debTimer?: any;

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
      | 'suggest:ready'
      | 'turn:cleared'
      | 'error',
    fn: Listener
  ) {
    return this.bus.on(evt, fn);
  }

  /** Start auto-detection of cart changes */
  start() {
    const { addButton, removeButton, cartCounter, cartItem } =
      this.opts.selectors!;
    // Click listeners
    if (addButton) this.attach('click', addButton, () => this.bumpCount(+1));
    if (removeButton)
      this.attach('click', removeButton, () => this.bumpCount(-1));

    // Mutation observer for counter or cart items
    this.mo = new MutationObserver(() => this.scheduleReadAndProcess());
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
        characterData: true,
        childList: true,
        subtree: true,
      })
    );

    // Initial read & process
    this.scheduleReadAndProcess();
  }

  /** Stop all observers/listeners */
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
    clearTimeout(this.debTimer);
  }

  /* ---------- internals ---------- */

  private attach(evt: string, selector: string, handler: EventListener) {
    const fn = (e: Event) => {
      const t = e.target as Element | null;
      if (!t) return;
      if ((t as Element).closest(selector)) handler(e);
    };
    document.addEventListener(evt, fn, true);
    this.detachFns.push(() => document.removeEventListener(evt, fn, true));
  }

  private bumpCount(delta: number) {
    // When we don't have a counter, still emit synthetic changes
    this.lastCount = clamp(this.lastCount + delta, 0, 9999);
    this.scheduleReadAndProcess(true);
  }

  private readCount(): number {
    const { cartCounter, cartItem } = this.opts.selectors!;
    // Prefer explicit counter element
    if (cartCounter) {
      const el = document.querySelector(cartCounter);
      if (el) {
        const n = parseInt((el.textContent || '0').replace(/\D+/g, ''), 10);
        if (!Number.isNaN(n)) return n;
      }
    }
    // Fallback: count cart-item elements
    if (cartItem) {
      const n = document.querySelectorAll(cartItem).length;
      if (n >= 0) return n;
    }
    // Fallback to last known
    return this.lastCount;
  }

  private scheduleReadAndProcess(force = false) {
    clearTimeout(this.debTimer);
    this.debTimer = setTimeout(
      () => this.readAndProcess(force),
      this.opts.debounceMs
    );
  }

  private async readAndProcess(force = false) {
    const count = this.readCount();
    const changed = force || count !== this.lastCount;
    this.lastCount = count;
    if (!changed) return;

    this.bus.emit('cart:changed', count);

    if (count < this.opts.minCountToProceed) {
      this.bus.emit('turn:cleared');
      return;
    }

    // Prevent overlapping runs
    if (this.inflight > 0) return;
    this.inflight++;

    try {
      await this.process(count);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = 0;
    }
  }

  private async process(count: number) {
    const { siteId, sessionId, baseContext } = this.opts;

    // 1) /rule/check
    const ruleReq: RuleCheckRequest = {
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
    const ruleRes = await this.api.ruleCheck(ruleReq);
    this.bus.emit('rule:checked', ruleRes);

    if (!ruleRes.shouldProceed) {
      this.bus.emit('turn:cleared');
      return;
    }

    // 2) /suggest/get
    const suggestReq: SuggestGetRequest = {
      siteId,
      sessionId,
      context: {
        matchedRules: ruleRes.matchedRules,
        eventType: ruleRes.eventType,
        ...(baseContext ?? {}),
      } as SuggestGetContext,
    };
    const suggestRes = await this.api.suggestGet(suggestReq);

    this.bus.emit('suggest:ready', suggestRes.suggestions);

    // Optional render
    const panelSel = this.opts.selectors?.panelSelector;
    if (panelSel) {
      const el = document.querySelector(panelSel) as HTMLElement | null;
      if (el)
        renderSuggestions(el, suggestRes.suggestions, (cta) =>
          this.bus.emit('sdk:action', cta)
        );
    }
  }
}

/* =========================
 * Minimal renderer (optional)
 * ========================= */
// uses components["schemas"]["Suggestion"] from your api-client
export function renderSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onAction: (action: NonNullable<Suggestion['actions']>[number]) => void
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

    // Header: type (fallback) + optional id tag
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';

    const kind = document.createElement('div');
    kind.textContent = s.type;
    kind.style.fontWeight = '600';
    header.appendChild(kind);

    if (s.id) {
      const tag = document.createElement('span');
      tag.textContent = s.id;
      tag.style.fontSize = '0.75rem';
      tag.style.opacity = '0.7';
      header.appendChild(tag);
    }
    card.appendChild(header);

    // Message (required by your schema)
    const msg = document.createElement('div');
    msg.textContent = s.message;
    msg.style.marginTop = '6px';
    msg.style.opacity = '0.9';
    card.appendChild(msg);

    // Actions (array of {type,label,payload?})
    const actions = s.actions ?? [];
    if (actions.length) {
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.gap = '8px';
      row.style.marginTop = '10px';

      actions.forEach((a, idx) => {
        const btn = document.createElement('button');
        btn.textContent = a.label;
        btn.setAttribute('data-action-type', a.type);
        btn.setAttribute('data-action-idx', String(idx));
        btn.onclick = () => onAction(a);
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
 * UMD global (optional)
 * ========================= */
// When bundled as UMD, consumers can use window.AgentSDK.AutoAssistant, etc.
declare global {
  interface Window {
    AgentSDK?: any;
  }
}
if (typeof window !== 'undefined') {
  (window as any).AgentSDK = { AutoAssistant, renderSuggestions };
}
