import type { CtaSpec, Suggestion } from './types';

type SuggestionExt = Suggestion & {
  primaryActions?: CtaSpec[];
  secondaryActions?: CtaSpec[];
  secondaryCta?: CtaSpec;
  actions?: CtaSpec[];
};

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
  onCta: (
    cta:
      | NonNullable<Suggestion['actions']>[number]
      | NonNullable<Suggestion['primaryCta']>
  ) => void
): void {
  container.innerHTML = '';
  container.removeAttribute('data-assistant-theme');

  if (!suggestions?.length) {
    return;
  }

  const frag = document.createDocumentFragment();

  suggestions.forEach((original) => {
    const s = original as SuggestionExt;
    const card = document.createElement('article');
    card.setAttribute('data-testid', 'assistant-card');
    card.dataset['role'] = 'assistant-card';
    if (s.type) {
      card.dataset['assistantOrigin'] = `suggestion-${s.type}`;
    }

    const title = document.createElement('h3');
    title.dataset['role'] = 'assistant-title';
    title.textContent = s.title ?? s.type ?? '';
    card.appendChild(title);

    if (s.description) {
      const desc = document.createElement('p');
      desc.dataset['role'] = 'assistant-description';
      desc.textContent = s.description;
      card.appendChild(desc);
    }

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

    const sig = (cta: CtaSpec): string => {
      const kind = cta.kind ?? '';
      const text = cta.label ?? '';
      const payload = cta.payload ?? null;
      const url = cta.url ?? '';
      return `${kind}|${text}|${JSON.stringify(payload) || ''}|${url}`;
    };

    const primarySig = primary.length ? sig(primary[0]) : null;
    const dedupedSecondary = secondary.filter((cta) => sig(cta) !== primarySig);

    if (primary.length || dedupedSecondary.length) {
      const row = document.createElement('div');
      row.dataset['role'] = 'assistant-actions';

      if (primary.length) {
        const p = primary[0];
        const btn = createButton(p.label, 'primary');
        btn.setAttribute('data-cta-kind', String(p.kind || ''));
        btn.onclick = () => onCta(p);
        row.appendChild(btn);
      }

      dedupedSecondary.forEach((cta, index) => {
        const btn = createButton(cta.label, 'secondary');
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
