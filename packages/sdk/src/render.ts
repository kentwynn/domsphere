import type { CtaSpec, Suggestion } from './types';

type SuggestionExt = Suggestion & {
  primaryActions?: CtaSpec[];
  secondaryActions?: CtaSpec[];
  secondaryCta?: CtaSpec;
  actions?: CtaSpec[];
};

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
    container.innerHTML = `<div data-testid="assistant-empty">No suggestions</div>`;
    return;
  }

  const frag = document.createDocumentFragment();

  suggestions.forEach((s0) => {
    const s = s0 as SuggestionExt;
    const card = document.createElement('div');
    card.setAttribute('data-testid', 'assistant-card');
    card.style.border = '1px solid #e5e7eb';
    card.style.borderRadius = '12px';
    card.style.padding = '12px';
    card.style.margin = '8px 0';

    const title = document.createElement('div');
    title.textContent = s.title ?? s.type;
    title.style.fontWeight = '600';
    card.appendChild(title);

    if (s.description) {
      const desc = document.createElement('div');
      desc.textContent = s.description;
      desc.style.opacity = '0.9';
      desc.style.marginTop = '4px';
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
      row.style.display = 'flex';
      row.style.flexWrap = 'wrap';
      row.style.gap = '8px';
      row.style.marginTop = '10px';

      // Render primary CTA with emphasized styling
      if (primary.length) {
        const p = primary[0];
        const btn = document.createElement('button');
        btn.textContent = p.label;
        btn.setAttribute('data-cta-kind', String(p.kind || ''));
        btn.onclick = () => onCta(p);
        btn.style.padding = '8px 12px';
        btn.style.borderRadius = '8px';
        btn.style.border = '1px solid #2563eb';
        btn.style.background = '#2563eb';
        btn.style.color = '#fff';
        row.appendChild(btn);
      }

      // Render secondary actions
      dedupedSecondary.forEach((cta, idx) => {
        const btn = document.createElement('button');
        btn.textContent = cta.label;
        btn.setAttribute('data-cta-idx', String(idx));
        btn.onclick = () => onCta(cta);
        btn.style.padding = '6px 10px';
        btn.style.borderRadius = '8px';
        btn.style.border = '1px solid #d1d5db';
        btn.style.background = 'transparent';
        row.appendChild(btn);
      });

      card.appendChild(row);
    }

    frag.appendChild(card);
  });

  container.appendChild(frag);
}
