export function safeStr(v: unknown): string | null {
  if (v == null) return null;
  try {
    const t = typeof v;
    if (t === 'string') return v as string;
    if (t === 'number' || t === 'boolean') return String(v);
    const s = JSON.stringify(v);
    return s.length > 5000 ? s.slice(0, 5000) : s;
  } catch {
    return null;
  }
}

export function cssPath(el: Element): string | null {
  try {
    const parts: string[] = [];
    let node: Element | null = el;
    while (node && node.nodeType === 1) {
      const name = node.nodeName.toLowerCase();
      let selector = name;
      if (node.id) {
        selector += `#${node.id}`;
        parts.unshift(selector);
        break;
      } else {
        let sib: Element | null = node;
        let nth = 1;
        while ((sib = sib.previousElementSibling as Element | null)) {
          if (sib.nodeName.toLowerCase() === name) nth++;
        }
        selector += `:nth-of-type(${nth})`;
      }
      parts.unshift(selector);
      node = node.parentElement;
    }
    return parts.join(' > ');
  } catch {
    return null;
  }
}

export function xPath(el: Element): string | null {
  try {
    if ((document as Document & { evaluate?: unknown }).evaluate) {
      const xpath = (start: Node): string => {
        let node: Node | null = start;
        if (node === document.body) return '/html/body';
        const ix = (sibling: Node | null, name: string): number => {
          let i = 1;
          for (; sibling; sibling = sibling.previousSibling) {
            if (sibling.nodeName === name) i++;
          }
          return i;
        };
        const segs: string[] = [];
        for (; node && (node as Element).nodeType === 1; ) {
          const cur = node as Element;
          const name = node.nodeName.toLowerCase();
          segs.unshift(`${name}[${ix(node, name.toUpperCase())}]`);
          node = cur.parentElement;
        }
        return '/' + segs.join('/');
      };
      return xpath(el);
    }
    return null;
  } catch {
    return null;
  }
}

export function attrMap(el: Element): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  try {
    for (const a of Array.from(el.attributes)) {
      out[a.name] = a.value ?? null;
    }
  } catch {
    /* empty */
  }
  return out;
}

export function nearbyText(el: Element): string[] {
  const texts: string[] = [];
  try {
    const grab = (node: Node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const t = (node.textContent || '').trim();
        if (t) texts.push(t);
      }
    };
    if (el.parentElement) {
      Array.from(el.parentElement.childNodes).forEach((n) => grab(n));
    }
    return texts.slice(0, 5);
  } catch {
    return [];
  }
}

export function ancestorBrief(el: Element): Array<Record<string, string | null>> {
  const arr: Array<Record<string, string | null>> = [];
  try {
    let p: Element | null = el.parentElement;
    let i = 0;
    while (p && i < 6) {
      arr.push({
        tag: p.tagName || null,
        id: p.id || null,
        class: p.getAttribute('class') || null,
      });
      p = p.parentElement;
      i++;
    }
  } catch {
    /* empty */
  }
  return arr;
}

export function firstInt(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = text.match(/\d+/);
  if (!m) return null;
  const n = parseInt(m[0], 10);
  return Number.isFinite(n) ? n : null;
}

