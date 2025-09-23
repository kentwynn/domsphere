import type { CtaSpec, Suggestion } from './types';

type SuggestionExt = Suggestion & {
  primaryActions?: CtaSpec[];
  secondaryActions?: CtaSpec[];
  secondaryCta?: CtaSpec;
  actions?: CtaSpec[];
};

function ctaRecord(cta: CtaSpec): Record<string, unknown> {
  return (cta as unknown as Record<string, unknown>) || {};
}

function ctaString(cta: CtaSpec, key: string, fallback = ''): string {
  const value = ctaRecord(cta)[key];
  return value == null ? fallback : String(value);
}

function createButton(
  label: string | undefined,
  variant: 'primary' | 'secondary'
): HTMLButtonElement {
  const btn = document.createElement('button');
  btn.type = 'button';
  const finalLabel = (label ?? '').trim() || 'Action';
  btn.textContent = finalLabel;
  if (finalLabel) {
    btn.setAttribute('aria-label', finalLabel);
  }
  btn.dataset['assistantVariant'] = variant;
  return btn;
}

export function renderFinalSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onCta: (cta: CtaSpec) => void
): void {
  container.innerHTML = '';
  container.removeAttribute('data-assistant-theme');

  if (!suggestions?.length) {
    return;
  }

  const frag = document.createDocumentFragment();

  suggestions.forEach((original) => {
    const s = original as SuggestionExt;
    const sRec = (s as unknown as Record<string, unknown>) || {};
    const type = typeof sRec['type'] === 'string' ? (sRec['type'] as string) : '';
    const titleText =
      typeof sRec['title'] === 'string' && sRec['title']
        ? (sRec['title'] as string)
        : type;
    const descriptionText =
      typeof sRec['description'] === 'string' ? (sRec['description'] as string) : '';
    const card = document.createElement('article');
    card.setAttribute('data-testid', 'assistant-card');
    card.dataset['role'] = 'assistant-card';
    if (type) {
      card.dataset['assistantOrigin'] = `suggestion-${type}`;
    }

    const title = document.createElement('h3');
    title.dataset['role'] = 'assistant-title';
    title.textContent = titleText ?? '';
    card.appendChild(title);

    if (descriptionText) {
      const desc = document.createElement('p');
      desc.dataset['role'] = 'assistant-description';
      desc.textContent = descriptionText;
      card.appendChild(desc);
    }

    const primary: CtaSpec[] = sRec['primaryCta']
      ? [sRec['primaryCta'] as CtaSpec]
      : [];

    const secondaryFromSchema = sRec['secondaryCta']
      ? [sRec['secondaryCta'] as CtaSpec]
      : [];
    const secondaryFromNew = (sRec['secondaryActions'] as CtaSpec[]) ?? [];
    const secondaryFallback = (sRec['actions'] as CtaSpec[]) ?? [];

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

    const sig = (cta: CtaSpec): string => {
      const kind = ctaString(cta, 'kind');
      const text = ctaString(cta, 'label');
      const payload = ctaRecord(cta)['payload'] ?? null;
      const url = ctaString(cta, 'url');
      return `${kind}|${text}|${JSON.stringify(payload) || ''}|${url}`;
    };

    const primarySig = primary.length ? sig(primary[0]) : null;
    const dedupedSecondary = secondary.filter((cta) => sig(cta) !== primarySig);

    if (primary.length || dedupedSecondary.length) {
      const row = document.createElement('div');
      row.dataset['role'] = 'assistant-actions';

      if (primary.length) {
        const p = primary[0];
        const btn = createButton(ctaString(p, 'label'), 'primary');
        btn.setAttribute(
          'data-cta-kind',
          ctaString(p, 'kind')
        );
        btn.onclick = () => onCta(p);
        row.appendChild(btn);
      }

      dedupedSecondary.forEach((cta, index) => {
        const btn = createButton(ctaString(cta, 'label'), 'secondary');
        btn.setAttribute('data-cta-idx', String(index));
        btn.onclick = () => onCta(cta);
        row.appendChild(btn);
      });

      card.appendChild(row);
    }

    frag.appendChild(card);
  });

  container.appendChild(frag);
}
