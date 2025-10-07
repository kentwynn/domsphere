import type { components } from '@domsphere/api-client';

type SchemaMap = components['schemas'];
type ExtractSchema<K extends string, Fallback> = SchemaMap extends Record<K, infer T>
  ? T
  : Fallback;

// OpenAPI Type Aliases with fallbacks when schema entries are missing
export type EventSchema = ExtractSchema<'Event', Record<string, unknown>>;
export type RuleCheckRequest = ExtractSchema<'RuleCheckRequest', Record<string, unknown>>;
export type RuleCheckResponse = ExtractSchema<'RuleCheckResponse', Record<string, unknown>>;
export type SuggestGetRequest = ExtractSchema<'SuggestGetRequest', Record<string, unknown>>;
export type SuggestGetResponse = ExtractSchema<'SuggestGetResponse', Record<string, unknown>>;
export type SuggestNextRequest = ExtractSchema<'SuggestNextRequest', Record<string, unknown>>;
export type SuggestNextResponse = ExtractSchema<'SuggestNextResponse', Record<string, unknown>>;
export type Suggestion = ExtractSchema<'Suggestion', Record<string, unknown>>;
export type CtaSpec = ExtractSchema<'CtaSpec', Record<string, unknown>>;

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

export type SiteStyleResponse = {
  siteId: string;
  css?: string | null;
  updatedAt?: string | null;
  source?: string | null;
};

export type SiteStylePayload = {
  siteId: string;
  css: string;
};

export type SiteSettingsResponse = {
  siteId: string;
  enableSuggestion: boolean;
  enableSearch: boolean;
  topSearchResults: number;
  updatedAt?: string | null;
};

export type SiteSettingsPayload = {
  siteId: string;
  enableSuggestion?: boolean;
  enableSearch?: boolean;
  topSearchResults?: number;
};

export type EmbeddingSearchResult = {
  url: string;
  similarity: number;
  title?: string | null;
  description?: string | null;
  meta?: Record<string, unknown> | null;
};

export type EmbeddingSearchResponse = {
  siteId: string;
  query: string;
  results: EmbeddingSearchResult[];
};
