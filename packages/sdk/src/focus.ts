import { normalizePath } from './utils';
import type { RuleListItem } from './types';

export type EventKind =
  | 'dom_click'
  | 'input_change'
  | 'submit'
  | 'page_load'
  | 'route_change'
  | 'scroll'
  | 'time_spent'
  | 'visibility_change';

export type FocusFilters = {
  paths: Set<string>;
  elementIds: Set<string>;
  cssPaths: Set<string>;
  cssPatterns: RegExp[];
  timeConditions: Array<{ op: string; value: number }>;
  sessionConditions: Array<{ field: string; op: string; value: unknown }>;
};

export type FocusMap = Map<EventKind, FocusFilters>;

function ensureBucket(focus: FocusMap, kind: EventKind): FocusFilters {
  if (!focus.has(kind))
    focus.set(kind, {
      paths: new Set<string>(),
      elementIds: new Set<string>(),
      cssPaths: new Set<string>(),
      cssPatterns: [],
      timeConditions: [],
      sessionConditions: [],
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
        ['dom_click', 'input_change', 'submit', 'page_load', 'route_change', 'scroll', 'time_spent', 'visibility_change'].includes(k)
      )
        kinds.add(k as EventKind);
      const ek = k as EventKind;
      const bucket = ensureBucket(focus, ek);
      
      // Process all conditions
      for (const cond of t.when ?? []) {
        const field = String(cond.field || '');
        const op = String(cond.op || '').toLowerCase();
        const val = cond.value;
        
        // Path conditions (equals only)
        if (field === 'telemetry.attributes.path' && op === 'equals' && typeof val === 'string') {
          bucket.paths.add(normalizePath(val));
        }
        
        // Element ID conditions (equals only)
        if (field === 'telemetry.attributes.id' && op === 'equals' && typeof val === 'string') {
          bucket.elementIds.add(val);
        }
        
        // Time-based conditions
        if (field === 'session.timeOnPage' && ['gt', 'gte', 'lt', 'lte'].includes(op) && typeof val === 'number') {
          bucket.timeConditions.push({ op, value: val });
        }
        
        // Session conditions (clickCount, scrollDepth, etc.)
        if (field.startsWith('session.') && field !== 'session.timeOnPage') {
          bucket.sessionConditions.push({ field, op, value: val });
        }
        
        // CSS Path patterns for advanced selectors
        if (field === 'telemetry.cssPath' && op === 'regex' && typeof val === 'string') {
          try {
            bucket.cssPatterns.push(new RegExp(val));
          } catch {
            // Invalid regex, skip
          }
        }
      }
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

// Advanced condition evaluation helpers
export function evaluateTimeConditions(
  focus: FocusMap,
  kind: EventKind,
  timeOnPage: number
): boolean {
  const f = focus.get(kind);
  if (!f || f.timeConditions.length === 0) return true;
  
  return f.timeConditions.every(({ op, value }) => {
    switch (op) {
      case 'gt': return timeOnPage > value;
      case 'gte': return timeOnPage >= value;
      case 'lt': return timeOnPage < value;
      case 'lte': return timeOnPage <= value;
      default: return true;
    }
  });
}

export function evaluateSessionConditions(
  focus: FocusMap,
  kind: EventKind,
  sessionData: Record<string, unknown>
): boolean {
  const f = focus.get(kind);
  if (!f || f.sessionConditions.length === 0) return true;
  
  return f.sessionConditions.every(({ field, op, value }) => {
    const sessionValue = sessionData[field.replace('session.', '')];
    
    switch (op) {
      case 'equals': return sessionValue === value;
      case 'gt': return typeof sessionValue === 'number' && sessionValue > (value as number);
      case 'gte': return typeof sessionValue === 'number' && sessionValue >= (value as number);
      case 'lt': return typeof sessionValue === 'number' && sessionValue < (value as number);
      case 'lte': return typeof sessionValue === 'number' && sessionValue <= (value as number);
      case 'contains': return typeof sessionValue === 'string' && sessionValue.includes(String(value));
      case 'in': return Array.isArray(value) && value.includes(sessionValue);
      default: return true;
    }
  });
}

export function evaluateAdvancedConditions(
  focus: FocusMap,
  kind: EventKind,
  context: {
    timeOnPage?: number;
    sessionData?: Record<string, unknown>;
  }
): boolean {
  // Evaluate time conditions
  if (context.timeOnPage !== undefined && !evaluateTimeConditions(focus, kind, context.timeOnPage)) {
    return false;
  }
  
  // Evaluate session conditions
  if (context.sessionData && !evaluateSessionConditions(focus, kind, context.sessionData)) {
    return false;
  }
  
  return true;
}
