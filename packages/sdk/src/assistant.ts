import { createApi } from './api';
import { Emitter, type Listener } from './emitter';
import {
  collectFocusFromRules,
  idMatches as idMatchHelper,
  targetMatches as targetMatchHelper,
  type EventKind,
  type FocusMap,
} from './focus';
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
  type SuggestNextRequest,
  type SuggestNextResponse,
} from './types';
import { normalizePath, toCamel } from './utils';

export type AutoAssistantOptions = ClientOptions & {
  siteId: string;
  sessionId: string;
  panelSelector?: string;
  debounceMs?: number; // default 150
  finalCooldownMs?: number; // default 30000
  baseContext?: Record<string, unknown>;
  ctaExecutor?: (cta: CtaSpec) => void;
};

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
  private focus: FocusMap = new Map();
  private lastSuggestions: Suggestion[] = [];
  private currentStep = 1;
  private lastRuleId?: string;
  private lastMatchSig?: string;
  private triggeredRules = new Set<string>();
  private choiceInput: Record<string, unknown> = {};

  // Local helper types to avoid `any` casting for extended fields not yet in the OpenAPI client
  private sigForCta(c: CtaSpec): string {
    const kind = (c as CtaSpec).kind ?? '';
    const label = (c as CtaSpec).label ?? '';
    const payload = (c as CtaSpec).payload ?? null;
    const url = (c as CtaSpec).url ?? '';
    return `${String(kind)}|${String(label)}|${
      JSON.stringify(payload) || ''
    }|${String(url)}`;
  }

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
      const tracked = rules.filter((r) => !!r.tracking);
      this.trackOn = tracked.length > 0;
      if (this.trackOn) {
        const { focus, kinds } = collectFocusFromRules(
          tracked as RuleListItem[]
        );
        this.focus = focus;
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
      this.schedule(() => {
        const target =
          this.pickFocusTarget('page_load') || document.body || undefined;
        if (this.pathMatches('page_load'))
          this.handleEvent('page_load', target);
      });
    }

    // clicks
    const onClick = (e: Event) => {
      const tgt = e.target as Element | undefined;
      if (!this.allow.has('dom_click')) return;
      const focusTgt = this.pickFocusTarget('dom_click') || tgt;
      if (!this.pathMatches('dom_click')) return;
      // Only emit when target matches configured ids or cssPath filters (if any)
      if (!this.targetMatches('dom_click', tgt)) return;
      this.schedule(() => this.handleEvent('dom_click', focusTgt));
    };
    document.addEventListener('click', onClick, true);
    this.detachFns.push(() =>
      document.removeEventListener('click', onClick, true)
    );

    // input/change
    const onChange = (e: Event) => {
      const tgt = e.target as Element | undefined;
      if (!this.allow.has('input_change')) return;
      const focusTgt = this.pickFocusTarget('input_change') || tgt;
      if (!this.pathMatches('input_change')) return;
      if (!this.targetMatches('input_change', tgt)) return;
      this.schedule(() => this.handleEvent('input_change', focusTgt));
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
      const tgt = e.target as Element | undefined;
      const focusTgt = this.pickFocusTarget('submit') || tgt;
      if (!this.pathMatches('submit')) return;
      if (!this.targetMatches('submit', tgt)) return;
      this.schedule(() => this.handleEvent('submit', focusTgt));
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
      if (!this.pathMatches('route_change')) return;
      // Clear dedupe when route changes
      this.triggeredRules.clear();
      // Clear accumulated choice inputs on navigation
      this.choiceInput = {};
      const target = this.pickFocusTarget('route_change');
      this.schedule(() => this.handleEvent('route_change', target));
    };
    window.addEventListener('popstate', onPop);
    window.addEventListener('agent-route-change', onPop as EventListener);
    this.detachFns.push(() => {
      window.removeEventListener('popstate', onPop);
      window.removeEventListener('agent-route-change', onPop as EventListener);
      history.pushState = _push;
      history.replaceState = _replace;
    });

    // Observe text/value changes on configured elements (id-only) to synthesize input_change
    if (this.allow.has('input_change')) {
      const f = this.focus.get('input_change');
      if (f && f.elementIds.size > 0) {
        try {
          const observer = new MutationObserver((mutations) => {
            if (!this.pathMatches('input_change')) return;
            const seen = new Set<Element>();
            for (const m of mutations) {
              const t =
                m.target.nodeType === Node.TEXT_NODE
                  ? (m.target as CharacterData).parentElement
                  : (m.target as Element | null);
              if (!t) continue;
              // Bubble and collect first matching selector per mutation
              let el: Element | null = t;
              let hops = 0;
              while (el && hops < 5) {
                const id = (el as HTMLElement).id || '';
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
              if (!this.targetMatches('input_change', el)) return;
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
        } catch {
          /* MutationObserver unavailable; skip */
        }
      }
    }
  }

  private pickFocusTarget(kind: EventKind): Element | undefined {
    const f = this.focus.get(kind);
    if (!f || f.elementIds.size === 0) return undefined;
    for (const id of f.elementIds) {
      const el = document.getElementById(id);
      if (el) return el;
    }
    return undefined;
  }

  private pathMatches(kind: EventKind): boolean {
    const f = this.focus.get(kind);
    if (!f) return true;
    if (f.paths.size === 0) return true;
    try {
      const cur = normalizePath(window.location.pathname || '/');
      return f.paths.has(cur);
    } catch {
      return true;
    }
  }

  private idMatches(kind: EventKind, target?: Element): boolean {
    return idMatchHelper(this.focus, kind, target);
  }

  private targetMatches(kind: EventKind, target?: Element): boolean {
    return targetMatchHelper(this.focus, kind, target);
  }

  // Only gate by path in focus mode; for DOM events we will send telemetry anchored
  // to the focused element (if configured) to satisfy id-based rule conditions.
  private shouldEmit(kind: EventKind): boolean {
    return this.pathMatches(kind);
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
    this.lastSuggestions = suggestions;
    // Determine the initial step to render
    const steps = suggestions
      .map((s) => {
        const m = (s.meta || {}) as Record<string, unknown>;
        const step = Number(m['step'] ?? 1);
        return Number.isFinite(step) ? (step as number) : 1;
      })
      .filter((n) => n > 0);
    this.currentStep = steps.length ? Math.min(...steps) : 1;
    this.renderStep();
  }

  private renderStep() {
    const panel = this.panelEl();
    if (!panel) return;
    const toShow = this.lastSuggestions.filter((s) => {
      const m = (s.meta || {}) as Record<string, unknown>;
      const step = Number(m['step'] ?? 1);
      return (
        (Number.isFinite(step) ? (step as number) : 1) === this.currentStep
      );
    });
    renderFinalSuggestions(panel, toShow, (cta) => this.executeCta(cta));
    this.bus.emit('suggest:ready', toShow);
    this.cooldownUntil = Date.now() + this.opts.finalCooldownMs;
  }

  private async executeCta(cta: CtaSpec) {
    try {
      const kind = String(cta.kind || '').toLowerCase();
      // Prefer app-provided CTA executor to avoid SDK-level hardcoding
      if (typeof this.opts.ctaExecutor === 'function') {
        this.opts.ctaExecutor(cta);
        return;
      }
      const handlers: Record<string, (c: CtaSpec) => void | Promise<void>> = {
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
          const url = typeof c.url === 'string' && c.url ? c.url : '';
          if (url) window.location.href = url as string;
        },
        choose: async (c) => {
          const p = (c.payload ?? {}) as Record<string, unknown>;
          const name = String(
            (p['name'] as string) || (p['key'] as string) || ''
          ).trim();
          const value = (p['value'] as unknown) ?? null;
          if (!name) return;
          try {
            // Merge prior choices so the agent sees cumulative input
            const input = { ...this.choiceInput, [name]: value } as Record<
              string,
              unknown
            >;
            const body: SuggestNextRequest = {
              siteId: this.opts.siteId,
              url: window.location.origin + window.location.pathname,
              ruleId: this.lastRuleId || '',
              input,
            };
            const res: SuggestNextResponse = await this.api.suggestNext(body);
            const suggestions = res?.suggestions || [];
            if (Array.isArray(suggestions)) {
              // Persist the selection
              this.choiceInput[name] = value as unknown;
              this.renderSuggestions(suggestions);
            }
          } catch (err) {
            this.bus.emit('error', err);
          }
        },
      };
      const runPipeline = async (steps: CtaSpec[] | undefined) => {
        if (!Array.isArray(steps) || steps.length === 0) return;
        for (const step of steps) {
          const k = String(step.kind || '').toLowerCase() as keyof typeof handlers | string;
          const fn = handlers[k as keyof typeof handlers];
          if (fn) await Promise.resolve(fn(step));
        }
      };

      type SuggestionExt = Suggestion & {
        primaryActions?: CtaSpec[];
        secondaryActions?: CtaSpec[];
        secondaryCtas?: CtaSpec[];
        actions?: CtaSpec[];
      };
      const getParentSuggestion = (): SuggestionExt | null => {
        // Find the suggestion that owns this CTA by signature
        const targetSig = this.sigForCta(cta);
        for (const s0 of this.lastSuggestions) {
          const s = s0 as SuggestionExt;
          const p = s.primaryCta as CtaSpec | undefined;
          const primArr = s.primaryActions as CtaSpec[] | undefined;
          const second = (s.secondaryActions ||
            s.secondaryCtas ||
            s.actions ||
            []) as CtaSpec[];
          if (p && this.sigForCta(p) === targetSig) return s;
          if (
            Array.isArray(second) &&
            second.some((c) => this.sigForCta(c) === targetSig)
          )
            return s;
          if (
            Array.isArray(primArr) &&
            primArr.some((c) => this.sigForCta(c) === targetSig)
          )
            return s;
        }
        return null;
      };

      // Work out if this CTA is the suggestion's primaryCta and has a primaryActions pipeline
      const parent = getParentSuggestion();
      const isPrimaryWithPipeline = (() => {
        if (!parent || !parent.primaryCta) return false;
        const prim = parent.primaryCta as CtaSpec;
        const match = this.sigForCta(prim) === this.sigForCta(cta);
        const steps = (parent.primaryActions as CtaSpec[]) || [];
        return match && Array.isArray(steps) && steps.length > 0;
      })();

      if (isPrimaryWithPipeline && parent) {
        // If a primaryActions pipeline is defined, run it INSTEAD of the primaryCta's own handler.
        // This lets the pipeline control ordering (e.g., fill then submit).
        await runPipeline((parent.primaryActions as CtaSpec[]) || []);
      } else {
        // Otherwise, invoke the CTA handler and then any CTA-level run pipeline.
        {
          const fn = handlers[kind as keyof typeof handlers];
          if (fn) await Promise.resolve(fn(cta));
        }
        const ctaRun = (cta as CtaSpec & { run?: CtaSpec[] }).run;
        await runPipeline(ctaRun);
      }
      // After executing a CTA, advance based on CTA.advanceTo or default to next step.
      const advNum = Number(
        (cta as CtaSpec & { advanceTo?: number }).advanceTo
      );
      if (Number.isFinite(advNum) && advNum > 0) {
        this.currentStep = advNum as number;
        this.renderStep();
      } else {
        const allSteps = this.lastSuggestions
          .map((s) =>
            Number(((s.meta || {}) as Record<string, unknown>)['step'] ?? 1)
          )
          .filter((n) => Number.isFinite(n)) as number[];
        const maxStep = allSteps.length ? Math.max(...allSteps) : 1;
        if (this.currentStep < maxStep) {
          this.currentStep += 1;
          this.renderStep();
        }
      }
    } catch (e) {
      this.bus.emit('error', e);
    }
  }

  private buildTelemetry(target?: Element): EventSchema['telemetry'] {
    const el = target && target.nodeType === 1 ? (target as Element) : null;
    let elementText = el ? (el.textContent || '').trim().slice(0, 400) : null;
    // For form controls (e.g., input/textarea), prefer their value when textContent is empty
    try {
      if (el && (!elementText || elementText.length === 0)) {
        const anyEl = el as unknown as { value?: unknown };
        const v = anyEl && typeof anyEl.value === 'string' ? anyEl.value : null;
        if (v != null) elementText = String(v).slice(0, 400);
      }
    } catch {
      /* ignore */
    }
    const elementHtml = el ? el.outerHTML.slice(0, 4000) : null; // cap size
    const attributes: Record<string, string | null> = el ? attrMap(el) : {};
    // Always include current path so rules can filter on it
    try {
      const p = window.location ? window.location.pathname : '/';
      attributes['path'] = normalizePath(p);
    } catch {
      /* ignore */
    }
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

      const matched = Array.isArray(rcRes.matchedRules)
        ? (rcRes.matchedRules as string[])
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
      const sgReq: SuggestGetRequest = {
        siteId: this.opts.siteId,
        url: window.location.origin + window.location.pathname,
        ruleId: topRuleId,
      };
      const { suggestions } = (await this.api.suggestGet(
        sgReq
      )) as SuggestGetResponse;
      this.lastRuleId = topRuleId;
      this.lastMatchSig = sig;
      if (topRuleId) this.triggeredRules.add(topRuleId);
      this.renderSuggestions(suggestions);
    } catch (e) {
      this.bus.emit('error', e);
    } finally {
      this.inflight = false;
    }
  }
}
