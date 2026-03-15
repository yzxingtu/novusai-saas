/**
 * 富文本编辑器类型定义 / Rich Text Editor Type Definitions
 *
 * 定义 RichTextEditor 组件、挂载选项及挂载后实例的 TypeScript 类型。
 * Defines TypeScript types for RichTextEditor component, mount options, and mounted instance.
 */

import type { AnyExtension, Editor, JSONContent } from '@tiptap/core';

/** 富文本编辑器组件 Props / Rich text editor component props */
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
  /** Page key for Ctrl+K AI page operations. When set, the editor auto-registers content operations. / 页面键，用于 Ctrl+K AI 页面操作；设置后编辑器自动注册内容操作 */
  pageKey?: string;
}

/** 命令式挂载选项 / Imperative mount options */
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

/** 挂载后的编辑器实例 API / Mounted editor instance API */
export interface MountedEditor {
  getJSON(): JSONContent | null;
  getHTML(): string;
  getText(): string;
  setContent(content: JSONContent | string): void;
  focus(): void;
  destroy(): void;
}

/** 工具栏按钮定义 / Toolbar button definition */
export interface ToolbarButtonDef {
  key: string;
  icon: string;
  label: string;
  action: (editor: Editor) => void;
  isActive?: (editor: Editor) => boolean;
  disabled?: (editor: Editor) => boolean;
}

/** 附件信息（用于上传与展示） / Attachment info (for upload and display) */
export interface AttachmentInfo {
  id: string | number;
  name: string;
  size: number;
  mime_type: string;
  url: string;
}
