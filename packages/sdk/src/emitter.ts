// Generic listener that accepts unknown args to avoid `any`
export type Listener = (...args: unknown[]) => void;

export class Emitter {
  private m = new Map<string, Set<Listener>>();
  on(evt: string, fn: Listener) {
    if (!this.m.has(evt)) this.m.set(evt, new Set());
    const set = this.m.get(evt);
    if (set) set.add(fn);
    else this.m.set(evt, new Set([fn]));
    return () => this.off(evt, fn);
  }
  off(evt: string, fn: Listener) {
    this.m.get(evt)?.delete(fn);
  }
  emit(evt: string, ...a: unknown[]) {
    this.m.get(evt)?.forEach((fn) => {
      try {
        fn(...a);
      } catch {
        /* empty */
      }
    });
  }
}

