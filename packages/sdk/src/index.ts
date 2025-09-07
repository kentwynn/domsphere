export * from './types';
export { createApi } from './api';
export { AutoAssistant } from './assistant';
export { renderFinalSuggestions } from './render';

import { createApi } from './api';
import { AutoAssistant } from './assistant';
import { renderFinalSuggestions } from './render';

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
    createApi,
  } as unknown as Window['AgentSDK'];
}
