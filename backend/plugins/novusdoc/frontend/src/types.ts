export type RichTextApplyMode = 'insert' | 'replace';

export interface RichTextSelectionSnapshot {
  afterText: string;
  beforeText: string;
  empty: boolean;
  from: number;
  revision: number;
  selectedText: string;
  to: number;
}

export interface RichTextApplyContentOptions {
  emitUpdate?: boolean;
  mode?: RichTextApplyMode;
  selection?: RichTextSelectionSnapshot | null;
}

export interface RichTextAiWritingOptions {
  apiPrefix?: string;
  canConfigure?: boolean;
  configurePath?: string;
  documentTitle?: string;
  enabled?: boolean;
  enabledActions?: string[];
  featureCode?: string;
  i18nPrefix?: string;
}

export interface RichTextEditorMountOptions {
  aiWriting?: RichTextAiWritingOptions;
  autofocus?: boolean;
  content?: Record<string, unknown> | null;
  defaultValue?: Record<string, unknown> | null;
  editable?: boolean;
  maxHeight?: number | string;
  minHeight?: number | string;
  mode?: 'compact' | 'full';
  onChange?: (json: unknown, html: string, text: string) => void;
  onReady?: (editor: unknown) => void;
  placeholder?: string;
  toolbar?: boolean | string[];
  upload?: boolean;
}

export interface MountedRichTextEditor {
  applyContent(
    content: string,
    options?: RichTextApplyContentOptions,
  ): void;
  destroy(): void;
  editorInstanceId?: string;
  focus(): void;
  getHTML(): string;
  getJSON(): unknown;
  getRevision?: () => number;
  getSelectionSnapshot(): RichTextSelectionSnapshot;
  getText(): string;
  setContent(content: unknown): void;
}

export interface NovusPluginSharedAPI {
  requestClient: {
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    put: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    delete: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    download?: (url: string, config?: Record<string, unknown>) => Promise<Blob>;
    getBaseUrl?: () => string | undefined;
  };
  $t: (key: string, ...args: unknown[]) => string;
  downloadBlob?: (blob: Blob, opts: { filename: string }) => void;
  IconifyIcon: unknown;
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
  RichTextEditor: unknown;
  router?: {
    currentRoute?: {
      value?: {
        meta?: Record<string, unknown>;
        params?: Record<string, string>;
      };
    };
    push: (to: string) => void;
  };
  mountRichTextEditor: (
    target: string | HTMLElement,
    options?: RichTextEditorMountOptions,
  ) => MountedRichTextEditor;
  getAccessCodes?: () => string[];
  hasAccessByCodes?: (
    codes: string | string[] | undefined,
    options?: { mode?: 'all' | 'any' },
  ) => boolean;
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
