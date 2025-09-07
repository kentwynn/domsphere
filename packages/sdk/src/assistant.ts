import { createApi } from './api';
import { Emitter, type Listener } from './emitter';
import { renderFinalSuggestions } from './render';
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
  type ClientOptions,
  type CtaSpec,
  type EventSchema,
  type RuleCheckRequest,
  type RuleListItem,
  type RuleListResponse,
  type SuggestGetRequest,
  type SuggestGetResponse,
  type Suggestion,
} from './types';

export type AutoAssistantOptions = ClientOptions & {
  siteId: string;
  sessionId: string;
  panelSelector?: string;
  debounceMs?: number; // default 150
  finalCooldownMs?: number; // default 30000
  baseContext?: Record<string, unknown>;
  ctaExecutor?: (cta: CtaSpec) => void;
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
  private cooldownUntil = 0;
  private trackOn = false;
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
    evt: 'rule:ready' | 'rule:checked' | 'suggest:ready' | 'error',
    fn: Listener
  ) {
    return this.bus.on(evt, fn);
  }

  async start() {
    // 1) Load rules to choose focus vs rich tracking
    try {
      const res = (await this.api.ruleListGet(
        this.opts.siteId
      )) as RuleListResponse;
      const rules = (res?.rules ?? []) as RuleListItem[];
      this.trackOn = rules.some((r) => !!r.tracking);
      if (this.trackOn) {
        const kinds = new Set<EventKind>();
        for (const r of rules) {
          const triggers = (r.triggers ?? []) as Array<{ eventType?: string }>;
          for (const t of triggers) {
            const k = String(t.eventType || '').trim();
            if (
              k &&
              [
                'dom_click',
                'input_change',
                'submit',
                'page_load',
                'route_change',
              ].includes(k)
            )
              kinds.add(k as EventKind);
          }
        }
        this.allow = kinds.size ? kinds : new Set<EventKind>(['page_load']);
      } else {
        this.allow = new Set<EventKind>([
          'dom_click',
          'input_change',
          'submit',
          'page_load',
          'route_change',
        ]);
      }
      this.bus.emit('rule:ready');
    } catch (e) {
      this.trackOn = false;
      this.allow = new Set<EventKind>([
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
    } else {
      // TODO: Rich mode (tracking off) is currently disabled to avoid guessing.
      // When enabled, this branch should register broad listeners (page_load, clicks, inputs)
      // and derive telemetry heuristics safely.
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

    // No mutation observer in focus mode without selectors
  }

  // TODO: setupListenersRichMode removed. Reintroduce when we support rich tracking heuristics.

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

  // No ask/form flows in stateless mode

  private schedule(fn: () => void) {
    if (this.debTimer) window.clearTimeout(this.debTimer);
    this.debTimer = window.setTimeout(fn, this.opts.debounceMs);
  }

  private canOpenPanel(): boolean {
    return Date.now() >= this.cooldownUntil;
  }

  private panelEl(): HTMLElement | null {
    const sel = this.opts.panelSelector;
    return sel ? (document.querySelector(sel) as HTMLElement | null) : null;
  }
  private renderSuggestions(suggestions: Suggestion[]) {
    const panel = this.panelEl();
    if (!panel) return;
    renderFinalSuggestions(panel, suggestions, (cta) => this.executeCta(cta));
    this.bus.emit('suggest:ready', suggestions);
    this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
  }

  private executeCta(cta: CtaSpec) {
    try {
      const kind = String(cta.kind || '').toLowerCase();
      // Prefer app-provided CTA executor to avoid SDK-level hardcoding
      if (typeof this.opts.ctaExecutor === 'function') {
        this.opts.ctaExecutor(cta);
        return;
      }
      const handlers: Record<string, (c: CtaSpec) => void> = {
        dom_fill: (c) => {
          const p = (c.payload ?? {}) as Record<string, unknown>;
          const sel = String((p as Record<string, unknown>)['selector'] || '');
          const val = String((p as Record<string, unknown>)['value'] ?? '');
          const el = sel
            ? (document.querySelector(sel) as
                | HTMLInputElement
                | HTMLElement
                | null)
            : null;
          if (!el) return;
          if ('value' in (el as HTMLInputElement)) {
            (el as HTMLInputElement).value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          } else {
            el.textContent = val;
          }
        },
        click: (c) => {
          const p = (c.payload ?? {}) as Record<string, unknown>;
          const sel = String((p as Record<string, unknown>)['selector'] || '');
          const el = sel
            ? (document.querySelector(sel) as HTMLElement | null)
            : null;
          el?.click();
        },
        open: (c) => {
          const url = (typeof c.url === 'string' && c.url) ? c.url : '';
          if (url) window.location.href = url as string;
        },
      };
      if (handlers[kind]) handlers[kind](cta);
    } catch (e) {
      this.bus.emit('error', e);
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
      // Candidate elements (start with event target and ancestors)
      const candidates: Element[] = [];
      if (el) {
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
        const key = pickKey(cand);
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

      if (!rcRes.shouldProceed || !this.canOpenPanel()) {
        return;
      }

      const sgReq: SuggestGetRequest = {
        siteId: this.opts.siteId,
        url: window.location.origin + window.location.pathname,
        ruleId: rcRes.matchedRules[0],
      };
      const { suggestions } = (await this.api.suggestGet(
        sgReq
      )) as SuggestGetResponse;
      this.renderSuggestions(suggestions);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = false;
    }
  }
}

// Convert identifiers like cart-count or total_qty to cartCount / totalQty
function toCamel(key: string): string {
  return key
    .replace(/[^a-zA-Z0-9]+(.)/g, (_, c: string) => (c ? c.toUpperCase() : ''))
    .replace(/^(.)/, (m) => m.toLowerCase());
}
