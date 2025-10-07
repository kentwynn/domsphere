export * from './types';
export { createApi } from './api';
export { AutoAssistant } from './assistant';
export { renderFinalSuggestions } from './render';
export { renderSearchResults } from './search';

import { createApi } from './api';
import { AutoAssistant } from './assistant';
import { renderFinalSuggestions } from './render';
import { renderSearchResults } from './search';

declare global {
  interface Window {
    AgentSDK?: unknown;
  }
}

// Attach a simple UMD-style global for convenience when used via <script>
if (typeof window !== 'undefined') {
  window.AgentSDK = {
    AutoAssistant,
    renderFinalSuggestions,
    renderSearchResults,
    createApi,
  } as unknown as Window['AgentSDK'];
}
