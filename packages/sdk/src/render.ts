import type { CtaSpec, Suggestion } from './types';

type SuggestionExt = Suggestion & {
  primaryActions?: CtaSpec[];
  secondaryActions?: CtaSpec[];
  secondaryCta?: CtaSpec;
  actions?: CtaSpec[];
};

type RgbaColor = {
  r: number;
  g: number;
  b: number;
  a: number;
};

type ThemeTokens = {
  accent: string;
  accentText: string;
  border: string;
  surface: string | null;
  text: string;
  subtleText: string;
  secondaryBorder: string;
  containerRadius: string;
  controlRadius: string;
};

const ACCENT_VAR_CANDIDATES = [
  '--accent-color',
  '--accent',
  '--brand-color',
  '--primary-color',
  '--color-primary',
  '--primary',
  '--link-color',
  '--bs-primary',
];

const CARD_RADIUS_CANDIDATES = [
  '--radius-md',
  '--radius',
  '--border-radius',
  '--border-radius-md',
  '--bs-border-radius',
  'border-radius',
];

const CONTROL_RADIUS_CANDIDATES = [
  '--radius-sm',
  '--control-radius',
  '--button-radius',
  '--bs-border-radius-sm',
  '--radius-md',
  '--border-radius',
  'border-radius',
];

let resolverEl: HTMLSpanElement | null = null;

function ensureResolver(): HTMLSpanElement | null {
  if (typeof document === 'undefined') {
    return null;
  }
  if (resolverEl) {
    return resolverEl;
  }
  const el = document.createElement('span');
  el.style.position = 'fixed';
  el.style.top = '-9999px';
  el.style.width = '0';
  el.style.height = '0';
  el.style.visibility = 'hidden';
  el.style.pointerEvents = 'none';
  document.body?.appendChild(el);
  resolverEl = el;
  return resolverEl;
}

function resolveColorValue(input: string): string | null {
  if (!input || typeof window === 'undefined') {
    return null;
  }
  const resolver = ensureResolver();
  if (!resolver) {
    return null;
  }
  resolver.style.color = '';
  resolver.style.color = input;
  const color = window.getComputedStyle(resolver).color;
  if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
    return color;
  }
  resolver.style.backgroundColor = '';
  resolver.style.backgroundColor = input;
  const bg = window.getComputedStyle(resolver).backgroundColor;
  if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
    return bg;
  }
  return color || bg || null;
}

function parseCssColor(input: string | null | undefined): RgbaColor | null {
  if (!input) {
    return null;
  }
  let value = input.trim();
  if (!value) {
    return null;
  }
  if (value === 'transparent') {
    return { r: 0, g: 0, b: 0, a: 0 };
  }
  if (!/^rgb/i.test(value)) {
    const resolved = resolveColorValue(value);
    if (!resolved) {
      return null;
    }
    value = resolved;
  }
  const modernMatch = value.match(
    /^rgba?\(\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)(?:\s*\/\s*(\d+(?:\.\d+)?))?\s*\)$/i
  );
  if (modernMatch) {
    const [, r, g, b, a] = modernMatch;
    return toRgba(r, g, b, a);
  }
  const classicMatch = value.match(
    /^rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*(\d+(?:\.\d+)?))?\s*\)$/i
  );
  if (classicMatch) {
    const [, r, g, b, a] = classicMatch;
    return toRgba(r, g, b, a);
  }
  return null;
}

function toRgba(
  rStr: string,
  gStr: string,
  bStr: string,
  aStr?: string
): RgbaColor | null {
  const r = Number(rStr);
  const g = Number(gStr);
  const b = Number(bStr);
  const a = aStr === undefined ? 1 : Number(aStr);
  if ([r, g, b, a].some((n) => Number.isNaN(n))) {
    return null;
  }
  return {
    r: clamp255(r),
    g: clamp255(g),
    b: clamp255(b),
    a: clampUnit(a),
  };
}

function clamp255(value: number): number {
  return Math.min(255, Math.max(0, value));
}

function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function rgbaToCss({ r, g, b, a }: RgbaColor): string {
  const alpha = Math.round(a * 1000) / 1000;
  if (alpha >= 1) {
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  }
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;
}

function mixColors(base: RgbaColor, other: RgbaColor, weight: number): RgbaColor {
  const t = clampUnit(weight);
  return {
    r: base.r + (other.r - base.r) * t,
    g: base.g + (other.g - base.g) * t,
    b: base.b + (other.b - base.b) * t,
    a: base.a + (other.a - base.a) * t,
  };
}

function getRelativeLuminance({ r, g, b }: RgbaColor): number {
  const toLin = (channel: number) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * toLin(r) + 0.7152 * toLin(g) + 0.0722 * toLin(b);
}

function contrastRatio(a: RgbaColor, b: RgbaColor): number {
  const L1 = getRelativeLuminance(a);
  const L2 = getRelativeLuminance(b);
  const lighter = Math.max(L1, L2);
  const darker = Math.min(L1, L2);
  return (lighter + 0.05) / (darker + 0.05);
}

const WHITE: RgbaColor = { r: 255, g: 255, b: 255, a: 1 };
const BLACK: RgbaColor = { r: 0, g: 0, b: 0, a: 1 };

function pickContrastingText(base: RgbaColor): RgbaColor {
  return contrastRatio(base, WHITE) >= contrastRatio(base, BLACK) ? WHITE : BLACK;
}

function readFirstStyleValue(
  style: CSSStyleDeclaration,
  candidates: string[]
): string | undefined {
  const anyStyle = style as unknown as Record<string, unknown>;
  for (const name of candidates) {
    const value = style.getPropertyValue(name);
    if (value && value.trim() && value.trim() !== '0px') {
      return value.trim();
    }
    const camel = toCamelCase(name);
    const direct = anyStyle[camel];
    if (typeof direct === 'string' && direct.trim() && direct.trim() !== '0px') {
      return direct.trim();
    }
  }
  return undefined;
}

function toCamelCase(value: string): string {
  return value.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

function deriveAccentCandidate(
  node: HTMLElement,
  style: CSSStyleDeclaration
): RgbaColor | null {
  for (const name of ACCENT_VAR_CANDIDATES) {
    const raw = style.getPropertyValue(name);
    const color = parseCssColor(raw);
    if (color) {
      return color;
    }
  }
  const attr = node.getAttribute('data-accent-color');
  const attrColor = parseCssColor(attr ?? undefined);
  if (attrColor) {
    return attrColor;
  }
  const linkColor = pickLinkColor(node);
  if (linkColor) {
    return linkColor;
  }
  return parseCssColor(style.color) ?? null;
}

function pickLinkColor(root: HTMLElement): RgbaColor | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const link = root.querySelector('a[href]');
  if (link) {
    const color = window.getComputedStyle(link).color;
    const parsed = parseCssColor(color);
    if (parsed) {
      return parsed;
    }
  }
  if (root !== document.body && document.body) {
    const fallbackLink = document.body.querySelector('a[href]');
    if (fallbackLink) {
      const color = window.getComputedStyle(fallbackLink).color;
      const parsed = parseCssColor(color);
      if (parsed) {
        return parsed;
      }
    }
  }
  return null;
}

function getReferenceElement(container: HTMLElement): HTMLElement {
  const explicit = container.closest('[data-assistant-theme-root]');
  if (explicit instanceof HTMLElement) {
    return explicit;
  }
  return container;
}

function deriveHostTheme(container: HTMLElement): ThemeTokens {
  const reference = getReferenceElement(container);
  const style = window.getComputedStyle(reference);
  const bodyStyle = document.body
    ? window.getComputedStyle(document.body)
    : (null as unknown as CSSStyleDeclaration);

  const textColor =
    parseCssColor(style.color) ??
    parseCssColor(bodyStyle?.color) ??
    ({ r: 17, g: 24, b: 39, a: 1 } satisfies RgbaColor);

  const backgroundColor =
    parseCssColor(style.backgroundColor) ??
    parseCssColor(bodyStyle?.backgroundColor) ??
    ({ r: 255, g: 255, b: 255, a: 1 } satisfies RgbaColor);

  const accentColor =
    deriveAccentCandidate(reference, style) ??
    parseCssColor(style.color) ??
    textColor;

  const accentText = pickContrastingText(accentColor);

  const surfaceMix = mixColors(backgroundColor, accentColor, 0.06);
  surfaceMix.a = Math.max(surfaceMix.a, backgroundColor.a);
  const surface = rgbaToCss(surfaceMix);

  const borderMix = mixColors(backgroundColor, textColor, 0.7);
  borderMix.a = Math.max(borderMix.a, 0.45);
  const border = rgbaToCss(borderMix);

  const subtleTextMix = mixColors(textColor, backgroundColor, 0.4);
  subtleTextMix.a = textColor.a;
  const subtleText = rgbaToCss(subtleTextMix);

  const secondaryBorderMix = mixColors(backgroundColor, textColor, 0.55);
  secondaryBorderMix.a = Math.max(secondaryBorderMix.a, 0.5);
  const secondaryBorder = rgbaToCss(secondaryBorderMix);

  const containerRadius =
    readFirstStyleValue(style, CARD_RADIUS_CANDIDATES) ?? '0.75rem';
  const controlRadius =
    readFirstStyleValue(style, CONTROL_RADIUS_CANDIDATES) ?? containerRadius;

  return {
    accent: rgbaToCss(accentColor),
    accentText: rgbaToCss(accentText),
    border,
    surface,
    text: rgbaToCss(textColor),
    subtleText,
    secondaryBorder,
    containerRadius,
    controlRadius,
  };
}

function createButton(
  label: string | undefined,
  theme: ThemeTokens,
  variant: 'primary' | 'secondary'
): HTMLButtonElement {
  const btn = document.createElement('button');
  btn.type = 'button';
  const finalLabel = (label ?? '').trim() || 'Action';
  btn.textContent = finalLabel;
  btn.setAttribute('aria-label', finalLabel);
  btn.dataset['assistantVariant'] = variant;
  btn.style.font = 'inherit';
  btn.style.cursor = 'pointer';
  btn.style.lineHeight = '1.4';
  btn.style.padding = '0.55em 0.9em';
  btn.style.borderRadius = theme.controlRadius;
  btn.style.borderWidth = '1px';
  btn.style.borderStyle = 'solid';
  btn.style.transition =
    'background-color 120ms ease, border-color 120ms ease, color 120ms ease';
  btn.style.display = 'inline-flex';
  btn.style.alignItems = 'center';
  btn.style.justifyContent = 'center';
  btn.style.gap = '0.35em';
  if (variant === 'primary') {
    btn.style.backgroundColor = theme.accent;
    btn.style.borderColor = theme.accent;
    btn.style.color = theme.accentText;
  } else {
    btn.style.backgroundColor = theme.surface ?? 'transparent';
    btn.style.borderColor = theme.secondaryBorder;
    btn.style.color = theme.text;
  }
  return btn;
}

export function renderFinalSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onCta: (
    cta:
      | NonNullable<Suggestion['actions']>[number]
      | NonNullable<Suggestion['primaryCta']>
  ) => void
): void {
  container.innerHTML = '';
  if (!suggestions?.length) {
    container.removeAttribute('data-assistant-theme');
    return;
  }

  const theme = deriveHostTheme(container);
  container.setAttribute('data-assistant-theme', 'host');

  const frag = document.createDocumentFragment();

  suggestions.forEach((s0) => {
    const s = s0 as SuggestionExt;
    const card = document.createElement('article');
    card.setAttribute('data-testid', 'assistant-card');
    card.dataset['role'] = 'assistant-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.gap = '0.65rem';
    card.style.border = `1px solid ${theme.border}`;
    card.style.borderRadius = theme.containerRadius;
    card.style.padding = '1rem';
    card.style.margin = '0.75rem 0';
    card.style.backgroundColor = theme.surface ?? 'transparent';
    card.style.color = theme.text;
    card.style.boxSizing = 'border-box';

    const title = document.createElement('h3');
    title.dataset['role'] = 'assistant-title';
    title.textContent = s.title ?? s.type;
    title.style.margin = '0';
    title.style.fontWeight = '600';
    title.style.color = theme.text;
    card.appendChild(title);

    if (s.description) {
      const desc = document.createElement('p');
      desc.dataset['role'] = 'assistant-description';
      desc.textContent = s.description;
      desc.style.margin = '0';
      desc.style.color = theme.subtleText;
      desc.style.fontSize = '0.95em';
      card.appendChild(desc);
    }

    // Build primary + secondary actions with de-duplication.
    // Display the primaryCta as the main action; primaryActions is a hidden pipeline run by the SDK.
    const primary: CtaSpec[] = s.primaryCta ? [s.primaryCta as CtaSpec] : [];

    const secondaryFromSchema = s.secondaryCta ? [s.secondaryCta] : [];
    const secondaryFromNew = s.secondaryActions ?? [];
    const secondaryFallback = s.actions ?? [];

    const pickFirstPopulated = (
      lists: CtaSpec[][]
    ): CtaSpec[] => {
      for (const list of lists) {
        if (Array.isArray(list) && list.length) {
          return list;
        }
      }
      return [];
    };

    const secondary: CtaSpec[] = pickFirstPopulated([
      secondaryFromNew,
      secondaryFromSchema,
      secondaryFallback,
    ]).slice(0, 5);
    const sig = (c: CtaSpec): string => {
      const kind = c.kind ?? '';
      const label = c.label ?? '';
      const payload = c.payload ?? null;
      const url = c.url ?? '';
      return `${kind}|${label}|${JSON.stringify(payload) || ''}|${url}`;
    };
    const primarySig = primary.length ? sig(primary[0]) : null;
    const dedupedSecondary = secondary.filter((c) => sig(c) !== primarySig);

    if (primary.length || dedupedSecondary.length) {
      const row = document.createElement('div');
      row.dataset['role'] = 'assistant-actions';
      row.style.display = 'flex';
      row.style.flexWrap = 'wrap';
      row.style.gap = '0.5rem';
      row.style.marginTop = '0.5rem';

      // Render primary CTA with host-aware styling
      if (primary.length) {
        const p = primary[0];
        const btn = createButton(p.label, theme, 'primary');
        btn.setAttribute('data-cta-kind', String(p.kind || ''));
        btn.onclick = () => onCta(p);
        row.appendChild(btn);
      }

      // Render secondary actions
      dedupedSecondary.forEach((cta, idx) => {
        const btn = createButton(cta.label, theme, 'secondary');
        btn.setAttribute('data-cta-idx', String(idx));
        btn.onclick = () => onCta(cta);
        row.appendChild(btn);
      });

      card.appendChild(row);
    }

    frag.appendChild(card);
  });

  container.appendChild(frag);
}
