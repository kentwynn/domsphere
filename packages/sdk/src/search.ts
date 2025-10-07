import type { EmbeddingSearchResult } from './types';

function formatScore(score: number): string {
  if (!Number.isFinite(score)) {
    return '';
  }
  const rounded = Math.max(0, Math.min(1, score));
  return `${Math.round(rounded * 100) / 100}`;
}

export function renderSearchResults(
  container: HTMLElement,
  results: EmbeddingSearchResult[]
): void {
  container.innerHTML = '';
  container.dataset['role'] = 'assistant-search';
  container.dataset['assistantResults'] = String(results.length ?? 0);
  if (!results?.length) {
    container.dataset['assistantEmpty'] = 'true';
    return;
  }
  container.removeAttribute('data-assistant-empty');

  const list = document.createElement('ul');
  list.dataset['role'] = 'assistant-search-list';

  results.forEach((result) => {
    const item = document.createElement('li');
    item.dataset['role'] = 'assistant-search-item';

    const relevance = formatScore(result.similarity);

    const link = document.createElement('a');
    link.dataset['role'] = 'assistant-search-link';
    link.href = result.url;
    link.textContent = (result.title ?? '').trim() || result.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.title = (result.title ?? '').trim() || result.url;
    item.appendChild(link);

    const descText = (result.description ?? '').trim();
    if (descText) {
      const desc = document.createElement('p');
      desc.dataset['role'] = 'assistant-search-description';
      desc.textContent = descText;
      item.appendChild(desc);
    }

    if (relevance) {
      item.setAttribute('data-relevance', relevance);
    }

    list.appendChild(item);
  });

  container.appendChild(list);
}
