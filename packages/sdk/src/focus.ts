import { normalizePath } from './utils';
import type { RuleListItem } from './types';

export type EventKind =
  | 'dom_click'
  | 'input_change'
  | 'submit'
  | 'page_load'
  | 'route_change';

export type FocusFilters = {
  paths: Set<string>;
  elementIds: Set<string>;
  cssPaths: Set<string>;
  cssPatterns: RegExp[];
};

export type FocusMap = Map<EventKind, FocusFilters>;

function ensureBucket(focus: FocusMap, kind: EventKind): FocusFilters {
  if (!focus.has(kind))
    focus.set(kind, {
      paths: new Set<string>(),
      elementIds: new Set<string>(),
      cssPaths: new Set<string>(),
      cssPatterns: [],
    });
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  return focus.get(kind)!;
}

export function collectFocusFromRules(rules: RuleListItem[]): {
  focus: FocusMap;
  kinds: Set<EventKind>;
} {
  const kinds = new Set<EventKind>();
  const focus: FocusMap = new Map();
  for (const r of rules) {
    const triggers = (r.triggers ?? []) as Array<{
      eventType?: string;
      when?: Array<{ field?: string; op?: string; value?: unknown }>;
    }>;
    for (const t of triggers) {
      const k = String(t.eventType || '').trim();
      if (
        k &&
        ['dom_click', 'input_change', 'submit', 'page_load', 'route_change'].includes(k)
      )
        kinds.add(k as EventKind);
      const ek = k as EventKind;
      const bucket = ensureBucket(focus, ek);
      // equals filters
      for (const cond of t.when ?? []) {
        const field = String(cond.field || '');
        const op = String(cond.op || '').toLowerCase();
        const val = cond.value;
        if (op !== 'equals') continue;
        if (field === 'telemetry.attributes.path' && typeof val === 'string') {
          bucket.paths.add(normalizePath(val));
        }
        if (field === 'telemetry.attributes.id' && typeof val === 'string') {
          bucket.elementIds.add(val);
        }
        // cssPath focus is intentionally ignored to reduce sensitivity
      }
      // regex cssPath ignored
    }
  }
  return { focus, kinds };
}

export function pickFocusTarget(focus: FocusMap, kind: EventKind): Element | undefined {
  const f = focus.get(kind);
  if (!f) return undefined;
  for (const id of f.elementIds) {
    const el = document.getElementById(id);
    if (el) return el;
  }
  return undefined;
}

export function idMatches(focus: FocusMap, kind: EventKind, target?: Element): boolean {
  const f = focus.get(kind);
  if (!f) return true;
  if (f.elementIds.size === 0) return true;
  if (!target) return false;
  let el: Element | null = target;
  let hops = 0;
  while (el && hops < 5) {
    const id = (el as HTMLElement).id || '';
    if (id && f.elementIds.has(id)) return true;
    el = el.parentElement;
    hops++;
  }
  return false;
}

export function targetMatches(
  focus: FocusMap,
  kind: EventKind,
  target?: Element
): boolean {
  const f = focus.get(kind);
  if (!f) return true;
  const hasAny = f.elementIds.size > 0;
  if (!hasAny) return true;
  return idMatches(focus, kind, target);
}
