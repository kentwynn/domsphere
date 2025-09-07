import type { Suggestion } from './types';

export function renderFinalSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onCta: (
    cta:
      | NonNullable<Suggestion['actions']>[number]
      | NonNullable<Suggestion['primaryCta']>
  ) => void
) {
  container.innerHTML = '';
  if (!suggestions?.length) {
    container.innerHTML = `<div data-testid="assistant-empty">No suggestions</div>`;
    return;
  }

  const frag = document.createDocumentFragment();

  suggestions.forEach((s) => {
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

    const actions = [
      ...(s.actions ?? []),
      ...(s.primaryCta ? [s.primaryCta] : []),
    ].filter(Boolean) as Array<
      NonNullable<typeof s.actions>[number] | NonNullable<typeof s.primaryCta>
    >;

    if (actions.length) {
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.flexWrap = 'wrap';
      row.style.gap = '8px';
      row.style.marginTop = '10px';
      actions.forEach((cta, idx) => {
        const btn = document.createElement('button');
        btn.textContent = cta.label;
        btn.setAttribute('data-cta-idx', String(idx));
        btn.onclick = () => onCta(cta);
        btn.style.padding = '6px 10px';
        btn.style.borderRadius = '8px';
        btn.style.border = '1px solid #d1d5db';
        row.appendChild(btn);
      });
      card.appendChild(row);
    }

    frag.appendChild(card);
  });

  container.appendChild(frag);
}
