import type { AnyExtension, Editor, JSONContent } from '@tiptap/core';

export interface RichTextEditorProps {
  modelValue?: JSONContent | null;
  defaultValue?: JSONContent | null;
  mode?: 'full' | 'compact';
  toolbar?: boolean | string[];
  ai?: boolean;
  upload?: boolean;
  editable?: boolean;
  placeholder?: string;
  minHeight?: number | string;
  maxHeight?: number | string;
  autofocus?: boolean;
  extensions?: AnyExtension[];
  contextTitle?: string;
  /** Page key for Ctrl+K AI page operations. When set, the editor auto-registers content operations. */
  pageKey?: string;
}

export interface MountOptions {
  content?: JSONContent | null;
  defaultValue?: JSONContent | null;
  mode?: 'full' | 'compact';
  toolbar?: boolean | string[];
  ai?: boolean;
  upload?: boolean;
  editable?: boolean;
  placeholder?: string;
  minHeight?: number | string;
  maxHeight?: number | string;
  autofocus?: boolean;
  extensions?: AnyExtension[];
  contextTitle?: string;
  pageKey?: string;
  onChange?: (json: JSONContent, html: string, text: string) => void;
  onReady?: (editor: Editor) => void;
}

export interface MountedEditor {
  getJSON(): JSONContent | null;
  getHTML(): string;
  getText(): string;
  setContent(content: JSONContent | string): void;
  focus(): void;
  destroy(): void;
}

export interface ToolbarButtonDef {
  key: string;
  icon: string;
  label: string;
  action: (editor: Editor) => void;
  isActive?: (editor: Editor) => boolean;
  disabled?: (editor: Editor) => boolean;
}

export interface AttachmentInfo {
  id: string | number;
  name: string;
  size: number;
  mime_type: string;
  url: string;
}
