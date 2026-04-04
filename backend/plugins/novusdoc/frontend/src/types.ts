export interface NovusPluginSharedAPI {
  requestClient: {
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    put: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    delete: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    getBaseUrl?: () => string | undefined;
  };
  $t: (key: string, ...args: unknown[]) => string;
  IconifyIcon: unknown;
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
  RichTextEditor: unknown;
  mountRichTextEditor: (
    target: string | HTMLElement,
    options?: Record<string, unknown>,
  ) => {
    getJSON(): unknown;
    getHTML(): string;
    getText(): string;
    setContent(content: unknown): void;
    focus(): void;
    destroy(): void;
  };
  createSimplePageOperation?: (options: Record<string, unknown>) => unknown;
  createParameterizedPageOperation?: (options: Record<string, unknown>) => unknown;
  createOpenPageOperation?: (options: Record<string, unknown>) => unknown;
  createOpenCurrentPageOperation?: (
    options: Record<string, unknown>,
  ) => unknown;
  createOpenRecordPageOperation?: (options: Record<string, unknown>) => unknown;
  createRecordActionPageOperation?: (
    options: Record<string, unknown>,
  ) => unknown;
  buildPageAIFormExtraData?: (
    options: Record<string, unknown>,
  ) => Record<string, unknown>;
  createPrefilledCreatePageOperation?: (
    options: Record<string, unknown>,
  ) => unknown;
  createRefreshPageOperation?: (options: Record<string, unknown>) => unknown;
  createSavePageOperation?: (options: Record<string, unknown>) => unknown;
  createKeywordSearchPageOperation?: (
    options: Record<string, unknown>,
  ) => unknown;
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (
    codes: string | string[] | undefined,
    options?: { mode?: 'all' | 'any' },
  ) => boolean;
  registerRichTextDocumentPageAI?: (options: Record<string, unknown>) => () => void;
  waitForRichTextEditorOperations?: (
    pageKey: string,
    options?: Record<string, unknown>,
  ) => Promise<boolean>;
}

export interface DocItem {
  id: number;
  title: string;
  word_count: number;
  status: 'draft' | 'published';
  is_pinned: boolean;
  folder_id: number | null;
  cover_image: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocDetail extends DocItem {
  content: Record<string, unknown> | null;
  content_text: string;
}

export interface Folder {
  id: number;
  name: string;
  parent_id: number | null;
  sort_order: number;
}

export interface Tag {
  id: number;
  name: string;
  color: string | null;
}
