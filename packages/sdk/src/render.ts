import type { Action, Suggestion, Turn } from './types';
type MinimalTurn = Pick<
  Turn,
  | 'intentId'
  | 'turnId'
  | 'status'
  | 'message'
  | 'actions'
  | 'form'
  | 'suggestions'
  | 'ui'
  | 'ttlSec'
>;

export function renderAskTurn(
  container: HTMLElement,
  turn: Turn,
  onAction: (action: Action) => void,
  onSubmitForm?: (form: FormData) => void
) {
  container.innerHTML = '';
  const panel = document.createElement('div');
  panel.style.border = '1px solid #e5e7eb';
  panel.style.borderRadius = '12px';
  panel.style.padding = '12px';
  panel.style.margin = '8px 0';

  if (turn.message) {
    const msg = document.createElement('div');
    msg.textContent = turn.message;
    msg.style.fontWeight = '600';
    panel.appendChild(msg);
  }

  if (turn.actions?.length) {
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.flexWrap = 'wrap';
    row.style.gap = '8px';
    row.style.marginTop = '10px';
    turn.actions.forEach((a) => {
      const btn = document.createElement('button');
      btn.textContent = a.label;
      btn.onclick = () => onAction(a);
      btn.style.padding = '6px 10px';
      btn.style.borderRadius = '8px';
      btn.style.border = '1px solid #d1d5db';
      row.appendChild(btn);
    });
    panel.appendChild(row);
  }

  if (turn.form?.fields?.length) {
    const form = document.createElement('form');
    form.style.marginTop = '12px';

    if (turn.form.title) {
      const title = document.createElement('div');
      title.textContent = turn.form.title;
      title.style.fontWeight = '600';
      form.appendChild(title);
    }

    turn.form.fields.forEach((f) => {
      const wrap = document.createElement('div');
      wrap.style.marginTop = '8px';
      const label = document.createElement('label');
      label.textContent = f.label + (f.required ? ' *' : '');
      label.style.display = 'block';
      label.style.marginBottom = '4px';
      wrap.appendChild(label);

      let input: HTMLElement;
      switch (f.type) {
        case 'textarea': {
          const el = document.createElement('textarea');
          el.name = f.key;
          el.required = !!f.required;
          // Placeholder not part of strict spec; omit to keep types safe
          input = el;
          break;
        }
        case 'select': {
          const el = document.createElement('select');
          el.name = f.key;
          el.required = !!f.required;
          (f.options ?? []).forEach((opt) => {
            const o = document.createElement('option');
            o.value = String(opt.value);
            o.textContent = opt.label ?? String(opt.value);
            el.appendChild(o);
          });
          input = el;
          break;
        }
        case 'radio': {
          const group = document.createElement('div');
          (f.options ?? []).forEach((opt) => {
            const wrapRadio = document.createElement('label');
            wrapRadio.style.marginRight = '8px';
            const r = document.createElement('input');
            r.type = 'radio';
            (r as HTMLInputElement).name = f.key;
            (r as HTMLInputElement).value = String(opt.value);
            wrapRadio.appendChild(r);
            wrapRadio.appendChild(document.createTextNode(opt.label ?? String(opt.value)));
            group.appendChild(wrapRadio);
          });
          input = group;
          break;
        }
        default: {
          const el = document.createElement('input');
          el.type = 'text';
          (el as HTMLInputElement).name = f.key;
          input = el;
        }
      }
      wrap.appendChild(input);
      form.appendChild(wrap);
    });

    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.textContent = turn.form.submitLabel ?? 'Continue';
    submit.style.marginTop = '10px';
    submit.style.padding = '6px 10px';
    submit.style.borderRadius = '8px';
    submit.style.border = '1px solid #d1d5db';
    form.appendChild(submit);

    form.onsubmit = (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      onSubmitForm?.(fd);
    };

    panel.appendChild(form);
  }

  container.appendChild(panel);
}

export function renderFinalSuggestions(
  container: HTMLElement,
  suggestions: Suggestion[],
  onCta: (
    cta:
      | NonNullable<Suggestion['actions']>[number]
      | NonNullable<Suggestion['primaryCta']>
  ) => void,
  _turn?: MinimalTurn
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
