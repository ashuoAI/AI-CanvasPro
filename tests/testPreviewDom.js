class FakeClassList {
  constructor() { this._classes = new Set(); }
  add(...tokens) { tokens.forEach(t => this._classes.add(t)); }
  remove(...tokens) { tokens.forEach(t => this._classes.delete(t)); }
  toggle(token, force) {
    if (force === true) { this._classes.add(token); return true; }
    if (force === false) { this._classes.delete(token); return false; }
    if (this._classes.has(token)) { this._classes.delete(token); return false; }
    this._classes.add(token); return true;
  }
  contains(token) { return this._classes.has(token); }
}

export function createFakePreviewContainer() {
  const container = {
    classList: new FakeClassList(),
    querySelector: () => null,
    appendChild: () => {},
    removeChild: () => {}
  };
  return container;
}

export function installPreviewDomStubs() {
  const saved = {};
  const fakeBody = { classList: new FakeClassList() };
  const fakeDocument = {
    body: fakeBody,
    createElement: (tag) => ({
      tagName: tag.toUpperCase(),
      classList: new FakeClassList(),
      style: {},
      appendChild: () => {},
      removeChild: () => {},
      querySelector: () => null,
      setAttribute: () => {},
      removeAttribute: () => {}
    }),
    querySelector: () => null,
    querySelectorAll: () => []
  };

  saved.window = globalThis.window;
  saved.document = globalThis.document;
  saved.PREVIEW_MODE = globalThis.PREVIEW_MODE;

  globalThis.window = globalThis.window || {};
  globalThis.document = fakeDocument;
  globalThis.window.PREVIEW_MODE = false;
  globalThis.window.document = fakeDocument;
  globalThis.window.dispatchEvent = () => {};
  globalThis.window.CustomEvent = class CustomEvent {
    constructor(type, options) { this.type = type; this.detail = options?.detail; }
  };

  return function restore() {
    if (saved.window !== undefined) globalThis.window = saved.window;
    else delete globalThis.window;
    if (saved.document !== undefined) globalThis.document = saved.document;
    else delete globalThis.document;
    if (saved.PREVIEW_MODE !== undefined) globalThis.PREVIEW_MODE = saved.PREVIEW_MODE;
    else delete globalThis.PREVIEW_MODE;
  };
}
