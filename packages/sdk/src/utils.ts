export function normalizePath(p: string): string {
  let s = String(p || '/').trim();
  if (!s.startsWith('/')) s = '/' + s;
  if (s.length > 1 && s.endsWith('/')) s = s.slice(0, -1);
  return s;
}

// Convert identifiers like cart-count or total_qty to cartCount / totalQty
export function toCamel(key: string): string {
  return key
    .replace(/[^a-zA-Z0-9]+(.)/g, (_, c: string) => (c ? c.toUpperCase() : ''))
    .replace(/^(.)/, (m) => m.toLowerCase());
}

