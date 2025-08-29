import { createApi } from './api';
import { Emitter, type Listener } from './emitter';
import { renderAskTurn, renderFinalSuggestions } from './render';
import {
  ancestorBrief,
  attrMap,
  cssPath,
  firstInt,
  nearbyText,
  safeStr,
  xPath,
} from './telemetry';
import {
  type Action,
  type ClientOptions,
  type EventSchema,
  type RuleCheckRequest,
  type RuleTrackProfile,
  type SuggestGetRequest,
  type SuggestGetResponse,
  type Turn,
} from './types';

export type AutoAssistantOptions = ClientOptions & {
  siteId: string;
  sessionId: string;
  panelSelector?: string;
  debounceMs?: number; // default 150
  finalCooldownMs?: number; // default 30000
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
  private selInput: string[] = [];
  private selMutation: string[] = [];
  private allow: Set<EventKind> = new Set();

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
    // 1) Load tracking profile to decide operating mode
    try {
      const prof = await this.api.ruleTrackGet();
      this.trackProfile = prof;
      this.trackOn = prof?.status === 'on';
      const ev = (prof?.events || {}) as Record<string, unknown>;
      // Allowed event kinds when focused tracking is ON
      this.allow = new Set(Object.keys(ev) as EventKind[]);
      this.selClick = Array.isArray(ev['dom_click'])
        ? (ev['dom_click'] as string[])
        : [];
      this.selInput = Array.isArray(ev['input_change'])
        ? (ev['input_change'] as string[])
        : [];
      this.selMutation = Array.isArray(ev['mutation'])
        ? (ev['mutation'] as string[])
        : [];
    } catch {
      this.trackOn = false; // rich mode fallback
      this.allow = new Set<EventKind>([
        'dom_click',
        'input_change',
        'submit',
        'page_load',
        'route_change',
      ]);
      this.selClick = [];
      this.selInput = [];
      this.selMutation = [];
    }
    // 2) Register listeners in a clear on/off branch for readability
    if (this.trackOn) {
      this.setupListenersFocusMode();
    } else {
      this.setupListenersRichMode();
    }
  }

  // Focused tracking: only emit allowed events and only for allowed selectors
  private setupListenersFocusMode() {
    // page_load
    if (this.allow.has('page_load')) {
      this.schedule(() =>
        this.handleEvent('page_load', document.body || undefined)
      );
    }

    // clicks
    const onClick = (e: Event) => {
      const tgt = e.target as Element | undefined;
      if (!this.allow.has('dom_click')) return;
      if (!this.matchesAny(tgt, this.selClick)) return;
      this.schedule(() => this.handleEvent('dom_click', tgt));
    };
    document.addEventListener('click', onClick, true);
    this.detachFns.push(() =>
      document.removeEventListener('click', onClick, true)
    );

    // input/change
    const onChange = (e: Event) => {
      const tgt = e.target as Element | undefined;
      if (!this.allow.has('input_change')) return;
      if (!this.matchesAny(tgt, this.selInput)) return;
      this.schedule(() => this.handleEvent('input_change', tgt));
    };
    document.addEventListener('input', onChange, true);
    document.addEventListener('change', onChange, true);
    this.detachFns.push(() =>
      document.removeEventListener('input', onChange, true)
    );
    this.detachFns.push(() =>
      document.removeEventListener('change', onChange, true)
    );

    // submit
    const onSubmit = (e: Event) => {
      if (!this.allow.has('submit')) return;
      this.schedule(() =>
        this.handleEvent('submit', e.target as Element | undefined)
      );
    };
    document.addEventListener('submit', onSubmit, true);
    this.detachFns.push(() =>
      document.removeEventListener('submit', onSubmit, true)
    );

    // route change
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
      if (!this.allow.has('route_change')) return;
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

    // mutation
    try {
      if (this.allow.has('mutation' as EventKind)) {
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
          if (!this.matchesAny(tgt, this.selMutation)) return;
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
    } catch {
      /* ignore */
    }
  }

  // Rich mode (tracking off): emit all core events
  private setupListenersRichMode() {
    // page_load
    this.schedule(() =>
      this.handleEvent('page_load', document.body || undefined)
    );

    // clicks
    const onClick = (e: Event) => {
      this.schedule(() =>
        this.handleEvent('dom_click', e.target as Element | undefined)
      );
    };
    document.addEventListener('click', onClick, true);
    this.detachFns.push(() =>
      document.removeEventListener('click', onClick, true)
    );

    // input/change
    const onChange = (e: Event) => {
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

    // submit
    const onSubmit = (e: Event) => {
      this.schedule(() =>
        this.handleEvent('submit', e.target as Element | undefined)
      );
    };
    document.addEventListener('submit', onSubmit, true);
    this.detachFns.push(() =>
      document.removeEventListener('submit', onSubmit, true)
    );

    // route change
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

    // mutation
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
      /* ignore */
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
          value: isActionWithValue(action)
            ? (action.value as string | number | boolean | null | undefined)
            : undefined,
        },
        context: { ...(baseContext ?? {}) },
      };
      const { turn: next } = await this.api.suggestGet(req);
      this.setActiveTurn(next);
    } catch (e) {
      this.bus.emit('error', e);
    }
  }

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
    try {
      const withAction = el?.closest('[data-action]') as HTMLElement | null;
      const action = withAction?.getAttribute('data-action');
      if (action && !('action' in attributes)) {
        attributes['action'] = action;
      }
    } catch {
      /* empty */
    }
    try {
      // Candidate elements and optional selector-derived keys
      const candidates: Element[] = [];
      const keyFromSelector = new Map<Element, string>();

      if (this.trackOn) {
        // In focus mode, rely on server-provided selectors for structure
        const want = this.selMutation as string[] | undefined;
        if (Array.isArray(want) && want.length) {
          for (const sel of want) {
            try {
              document.querySelectorAll(sel).forEach((node) => {
                if (node instanceof Element) {
                  candidates.push(node);
                  if (!keyFromSelector.has(node))
                    keyFromSelector.set(node, selectorToKey(sel));
                }
              });
            } catch {
              /* invalid selector from server; ignore */
            }
          }
        }
      } else if (el) {
        // In rich mode, consider target and ancestors (heuristic)
        candidates.push(el);
        let p: Element | null = el.parentElement;
        let hops = 0;
        while (p && hops < 4) {
          candidates.push(p);
          p = p.parentElement;
          hops++;
        }
      }

      const uniq: Element[] = Array.from(new Set(candidates));

      // Heuristic key picker used only in rich mode
      const pickKey = (cand: Element): string | null => {
        const id = (cand as HTMLElement).id || '';
        if (id) return id;
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
        if (n == null) continue;
        const key = this.trackOn
          ? keyFromSelector.get(cand) ?? null
          : pickKey(cand);
        if (!key) continue;
        const camel = toCamel(key);
        attributes[camel] = String(n);
      }
    } catch {
      /* best-effort only */
    }
    const css = el ? cssPath(el) : null;
    const xp = el ? xPath(el) : null;
    const near = el ? nearbyText(el) : [];
    const ancs = el ? ancestorBrief(el) : [];

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
    if (this.inflight) return;
    this.inflight = true;

    try {
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

      const { turn } = (await this.api.suggestGet(sgReq)) as SuggestGetResponse;
      this.setActiveTurn(turn);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = false;
    }
  }
}

function isActionWithValue(
  a: Action | { id: string; label?: string; value?: unknown }
): a is { id: string; label?: string; value?: unknown } {
  return typeof (a as { value?: unknown }).value !== 'undefined';
}

// Convert identifiers like cart-count or total_qty to cartCount / totalQty
function toCamel(key: string): string {
  return key
    .replace(/[^a-zA-Z0-9]+(.)/g, (_, c: string) => (c ? c.toUpperCase() : ''))
    .replace(/^(.)/, (m) => m.toLowerCase());
}

// Derive a stable key name from a CSS selector provided by the server profile
function selectorToKey(sel: string): string {
  const s = sel.trim();
  const last = s.split(/\s*[>+~\s]\s*/).pop() || s;
  const data = last.match(/\[\s*data-([a-zA-Z0-9_-]+)/);
  if (data) return toCamel(data[1]);
  const id = last.match(/#([a-zA-Z0-9_-]+)/);
  if (id) return toCamel(id[1]);
  const cls = last.match(/\.([a-zA-Z0-9_-]+)/);
  if (cls) return toCamel(cls[1]);
  const nameAttr = last.match(/\[\s*name="?([a-zA-Z0-9_-]+)/);
  if (nameAttr) return toCamel(nameAttr[1]);
  const tag = last.match(/^([a-zA-Z0-9_-]+)/);
  if (tag) return toCamel(tag[1]);
  return toCamel(last.replace(/[^a-zA-Z0-9]+/g, '-'));
}
