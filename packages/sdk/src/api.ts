import {
  ClientOptions,
  RuleCheckRequest,
  RuleCheckResponse,
  SuggestGetRequest,
  SuggestGetResponse,
  RuleListResponse,
  SuggestNextRequest,
  SuggestNextResponse,
  SiteStyleResponse,
  SiteStylePayload,
  SiteSettingsResponse,
  SiteSettingsPayload,
  EmbeddingSearchResponse,
} from './types';

type HeadersLoose = Record<string, string | undefined>;

async function postJson<TReq, TRes>(
  baseUrl: string,
  path: string,
  body: TReq,
  headers: HeadersLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}

async function putJson<TReq, TRes>(
  baseUrl: string,
  path: string,
  body: TReq,
  headers: HeadersLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}

async function getJson<TRes>(
  baseUrl: string,
  path: string,
  headers: HeadersLoose = {}
): Promise<TRes> {
  const res = await fetch(new URL(path, baseUrl).toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json', ...headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} ${res.statusText} @ ${path}: ${text}`);
  }
  return (await res.json()) as TRes;
}

export function createApi(opts: ClientOptions) {
  const {
    baseUrl = 'http://localhost:4000',
    contractVersion = null,
    requestIdFactory,
    fetchHeaders = {},
  } = opts;

  const headers = (): HeadersLoose => ({
    'X-Contract-Version': contractVersion ?? undefined,
    'X-Request-Id': requestIdFactory?.(),
    ...fetchHeaders,
  });

  return {
    ruleCheck: (body: RuleCheckRequest) =>
      postJson<RuleCheckRequest, RuleCheckResponse>(
        baseUrl,
        '/rule/check',
        body,
        headers()
      ),
    suggestGet: (body: SuggestGetRequest) =>
      postJson<SuggestGetRequest, SuggestGetResponse>(
        baseUrl,
        '/suggest',
        body,
        headers()
      ),
    suggestNext: (body: SuggestNextRequest) =>
      postJson<SuggestNextRequest, SuggestNextResponse>(
        baseUrl,
        '/suggest/next',
        body,
        headers()
      ),
    ruleListGet: (siteId: string) => getJson<RuleListResponse>(baseUrl, `/rule?siteId=${encodeURIComponent(siteId)}`, headers()),
    styleGet: (siteId: string) =>
      getJson<SiteStyleResponse>(
        baseUrl,
        `/sdk/style?siteId=${encodeURIComponent(siteId)}`,
        headers()
      ),
    styleUpsert: (body: SiteStylePayload) =>
      postJson<SiteStylePayload, SiteStyleResponse>(
        baseUrl,
        '/sdk/style',
        body,
        headers()
      ),
    settingsGet: (siteId: string) =>
      getJson<SiteSettingsResponse>(
        baseUrl,
        `/sdk/settings?siteId=${encodeURIComponent(siteId)}`,
        headers()
      ),
    settingsUpdate: (body: SiteSettingsPayload) =>
      putJson<SiteSettingsPayload, SiteSettingsResponse>(
        baseUrl,
        '/sdk/settings',
        body,
        headers()
      ),
    embeddingSearch: (body: { siteId: string; query: string; limit?: number }) =>
      postJson<{ siteId: string; query: string; limit?: number }, EmbeddingSearchResponse>(
        baseUrl,
        '/embedding/search',
        body,
        headers()
      ),
  };
}
