/**
 * DOM API extensions for vendor-prefixed and emerging APIs
 */
declare global {
  interface ViewTransition {
    finished: Promise<void>;
    ready: Promise<void>;
    skipTransition(): void;
    updateCallbackDone: Promise<void>;
  }

  interface Document {
    mozFullScreenElement?: Element | null;
    msFullscreenElement?: Element | null;
    startViewTransition?(callback: () => Promise<void> | void): ViewTransition;
    webkitFullscreenElement?: Element | null;
  }
}
