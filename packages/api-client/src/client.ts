import createClient, { ClientOptions } from 'openapi-fetch';
import type { paths } from './gen/schema';

// Configure a typed client for your API
export function createApiClient(options?: ClientOptions) {
  const baseUrl =
    options?.baseUrl ||
    process.env.NEXT_PUBLIC_DOMSPHERE_API_URL ||
    'http://localhost:4000';

  return createClient<paths>({ baseUrl, ...options });
}

export type ApiClient = ReturnType<typeof createApiClient>;
