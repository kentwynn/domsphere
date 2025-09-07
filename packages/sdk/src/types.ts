import type { components } from '@domsphere/api-client';

// OpenAPI Type Aliases
export type EventSchema = components['schemas']['Event'];
export type RuleCheckRequest = components['schemas']['RuleCheckRequest'];
export type RuleCheckResponse = components['schemas']['RuleCheckResponse'];
export type SuggestGetRequest = components['schemas']['SuggestGetRequest'];
export type SuggestGetResponse = components['schemas']['SuggestGetResponse'];
export type SuggestNextRequest = components['schemas']['SuggestNextRequest'];
export type SuggestNextResponse = components['schemas']['SuggestNextResponse'];
export type Suggestion = components['schemas']['Suggestion'];
export type CtaSpec = components['schemas']['CtaSpec'];

// Minimal type for the rule-track profile
// Use the OpenAPI contract type for rule tracking (request shape is compatible for our read usage)
// Fallback structural type (generator type alias lookup appears unavailable in this build context)
export type RuleTrackProfile = {
  siteId: string;
  status: 'on' | 'off';
  version?: string | null;
  updatedAt?: string | null;
  events?: Record<string, string[]> | null;
};

export type ClientOptions = {
  baseUrl?: string; // default http://localhost:4000
  contractVersion?: string | null; // -> X-Contract-Version
  requestIdFactory?: () => string; // -> X-Request-Id
  fetchHeaders?: Record<string, string>;
};

// Rule list payload (API /rule)
export type RuleTrigger = {
  eventType?: string;
  when?: Array<Record<string, unknown>>;
};
export type RuleListItem = {
  id: string;
  enabled?: boolean;
  tracking?: boolean;
  triggers?: RuleTrigger[];
  [k: string]: unknown;
};
export type RuleListResponse = { siteId: string; rules: RuleListItem[] };
