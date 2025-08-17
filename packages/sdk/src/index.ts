// packages/sdk/src/index.ts

type Options = { apiUrl?: string };

export class DomSphereSDK {
  private apiUrl: string;

  constructor(options: Options = {}) {
    const envUrl =
      (globalThis as any).DOMSPHERE_API_URL ?? 'http://localhost:4000';
    this.apiUrl = options.apiUrl ?? envUrl;
  }

  async health(): Promise<unknown> {
    const res = await fetch(`${this.apiUrl}/health`);
    if (!res.ok) throw new Error(`Health failed: ${res.status}`);
    return res.json();
  }

  mount(el: HTMLElement) {
    el.innerHTML = `
      <div style="font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; padding:12px; border:1px solid #e5e7eb; border-radius:10px; max-width:520px">
        <p style="margin:0 0 8px 0;">DomSphere SDK mounted. API: <code>${this.apiUrl}</code></p>
        <button id="domsphere-btn" style="padding:8px 12px; cursor:pointer;">Test API</button>
        <pre id="domsphere-output" style="margin-top:10px; background:#f6f8fa; padding:8px; border-radius:8px; white-space:pre-wrap;"></pre>
      </div>
    `;

    const btn = el.querySelector<HTMLButtonElement>('#domsphere-btn');
    const output = el.querySelector<HTMLElement>('#domsphere-output');

    btn?.addEventListener('click', async () => {
      if (!output) return;
      output.textContent = 'Loading...';
      try {
        const data = await this.health();
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        output.textContent =
          'Error: ' + (err instanceof Error ? err.message : String(err));
      }
    });
  }
}

// Make the constructor available for <script> users:
//   const sdk = new window.DomSphereSDK({ apiUrl: "http://localhost:4000" });
export default DomSphereSDK;
(globalThis as any).DomSphereSDK = DomSphereSDK;
