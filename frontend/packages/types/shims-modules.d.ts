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
  export default function jsonBigint(options?: JsonBigintOptions): {
    parse: (text: string) => unknown;
    stringify: (value: unknown) => string;
  };
}

declare module 'sortablejs/modular/sortable.complete.esm.js' {
  import type Sortable from 'sortablejs';

  const SortableMod: typeof Sortable;
  export default SortableMod;
}

declare module 'secure-ls' {
  interface SecureLSConfig {
    encodingType?: 'aes' | 'base64' | 'des' | 'lz-string' | 'rabbit' | 'rc4';
    encryptionSecret?: string;
    encryptionNamespace?: string;
    isCompression?: boolean;
    metaKey?: string;
  }

  export default class SecureLS {
    constructor(config?: SecureLSConfig);
    clear(): void;
    get(key: string): null | string;
    remove(key: string): void;
    set(key: string, value: string): void;
  }
}
