import type { components } from '@domsphere/api-client';

// OpenAPI Type Aliases
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

// Minimal type for the rule-track profile
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

