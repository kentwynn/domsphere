// Re-export the generated OpenAPI types (schema.ts will be created by codegen)
export type { components, operations, paths } from './schema';

// Optionally: add a typed API helper wrapper here
export async function fetchApi<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}
