/** ElementAtlas: compact DOM snapshot sent to the planner */
export interface AtlasNode {
  id: string; // local unique id
  tag: string; // e.g., 'button', 'input'
  role?: string; // ARIA role
  testid?: string; // data-testid
  name?: string; // accessible name
  ariaLabel?: string; // aria-label
  textSnippet?: string; // short, trimmed text
  cssFingerprint?: string; // hashed classes (not full class list)
  pathFingerprint: string; // short, stable path (not full XPath)
  visible: boolean;
  hrefOriginSafe?: string; // same-origin or origin-stripped
}

export interface ElementAtlas {
  atlasVersion: string; // e.g., '1.0.0'
  url: string; // page URL
  title?: string;
  capturedAt: string; // ISO timestamp
  snapshotSha256: string; // hash of serialized nodes
  nodes: AtlasNode[];
}
