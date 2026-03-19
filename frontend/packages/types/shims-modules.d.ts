declare module 'vue-json-viewer' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<Record<string, unknown>>;
  export default component;
}

declare module 'json-bigint' {
  interface JsonBigintOptions {
    storeAsString?: boolean;
    strict?: boolean;
  }
  function jsonBigint(options?: JsonBigintOptions): {
    parse: (text: string) => unknown;
    stringify: (value: unknown) => string;
  };
  export = jsonBigint;
}

declare module 'sortablejs/modular/sortable.complete.esm.js' {
  import type { default as Sortable } from 'sortablejs';
  const SortableMod: typeof Sortable;
  export default SortableMod;
}

declare module 'secure-ls' {
  interface SecureLSConfig {
    encodingType?: 'aes' | 'base64' | 'lz-string' | 'rc4' | 'rabbit' | 'des';
    encryptionSecret?: string;
    encryptionNamespace?: string;
    isCompression?: boolean;
    metaKey?: string;
  }
  class SecureLS {
    constructor(config?: SecureLSConfig);
    get(key: string): string | null;
    set(key: string, value: string): void;
    remove(key: string): void;
    clear(): void;
  }
  export = SecureLS;
}
