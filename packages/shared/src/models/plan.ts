export type SelectorStrategy = 'CSS' | 'ARIA' | 'XPATH';

export interface Selector {
  strategy: SelectorStrategy;
  value: string;
}

export type ActionType =
  | 'CLICK'
  | 'INPUT'
  | 'SELECT'
  | 'WAIT'
  | 'SCROLL'
  | 'NAVIGATE';
export type AssertCondition = 'EXISTS' | 'VISIBLE' | 'TEXT_CONTAINS';

export interface Assertion {
  selector: Selector;
  condition: AssertCondition;
  text?: string; // required when TEXT_CONTAINS
  timeoutMs?: number; // per-assert timeout
}

export interface ActionStep {
  action: ActionType;
  selector?: Selector; // optional for pure WAIT
  inputValue?: string; // INPUT/SELECT
  notes?: string;
  assert?: Assertion[]; // post-step checks
}

export interface Fallback {
  when: 'selector_not_found' | 'assert_failed';
  try: Selector;
}

export interface DomActionPlan {
  agentVersion: string; // e.g., 'v1'
  planId: string; // uuid
  steps: ActionStep[];
  fallbacks?: Fallback[];
  cacheKey?: string;
  confidence?: number; // 0..1
}

export interface PlanRequest {
  siteId?: string; // uuid, optional hint
  url: string;
  intent: string;
  atlasVersion: string;
  domSnapshot: import('./atlas').ElementAtlas;
  doNotStore?: boolean;
}

export interface PlanResponse {
  sessionId: string; // uuid
  agentVersion: string;
  planId: string;
  cache: 'HIT' | 'MISS';
  plan: DomActionPlan;
}
