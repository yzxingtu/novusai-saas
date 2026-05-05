/**
 * 富文本编辑器类型定义 / Rich Text Editor Type Definitions
 *
 * 定义 RichTextEditor 组件、挂载选项及挂载后实例的 TypeScript 类型。
 * Defines TypeScript types for RichTextEditor component, mount options, and mounted instance.
 */

import type { AnyExtension, Editor, JSONContent } from '@tiptap/core';
import type { RichTextAiActionType } from '#/features/rich-text-ai';

import type { Ref, ShallowRef } from 'vue';

export interface RichTextEditorAiWritingOptions {
  /** Whether the editor-domain AI writing UI is enabled. */
  enabled?: boolean;
  /** API prefix used by resolveAgentAssignmentApi for the global AI panel handoff. */
  apiPrefix?: string;
  /** Optional document title sent as editor-domain context. */
  documentTitle?: string;
  /** Optional feature code override; omitted uses system.ai_writing. */
  featureCode?: string;
  /** i18n prefix for product copy. Defaults to plugin.novusdoc.ai when omitted. */
  i18nPrefix?: string;
  /** Optional route/path for the "configure" action when assignment is missing. */
  configurePath?: string;
  /** Whether to show the configure action for assignment failures. */
  canConfigure?: boolean;
  /** Optional action allow-list. */
  enabledActions?: RichTextAiActionType[];
}

/** 富文本编辑器组件 Props / Rich text editor component props */
export interface RichTextEditorProps {
  modelValue?: JSONContent | null;
  defaultValue?: JSONContent | null;
  mode?: 'compact' | 'full';
  toolbar?: boolean | string[];
  upload?: boolean;
  editable?: boolean;
  placeholder?: string;
  minHeight?: number | string;
  maxHeight?: number | string;
  autofocus?: boolean;
  extensions?: AnyExtension[];
  aiWriting?: RichTextEditorAiWritingOptions;
}

/** 命令式挂载选项 / Imperative mount options */
export interface MountOptions {
  content?: JSONContent | null;
  defaultValue?: JSONContent | null;
  mode?: 'compact' | 'full';
  toolbar?: boolean | string[];
  upload?: boolean;
  editable?: boolean;
  placeholder?: string;
  minHeight?: number | string;
  maxHeight?: number | string;
  autofocus?: boolean;
  extensions?: AnyExtension[];
  aiWriting?: RichTextEditorAiWritingOptions;
  onChange?: (json: JSONContent, html: string, text: string) => void;
  onReady?: (editor: Editor) => void;
}

export interface RichTextEditorSetContentOptions {
  emitUpdate?: boolean;
}

export type RichTextEditorApplyContentMode = 'insert' | 'replace';

export interface RichTextEditorSelectionSnapshot {
  afterText: string;
  beforeText: string;
  empty: boolean;
  from: number;
  revision: number;
  selectedText: string;
  to: number;
}

export interface RichTextEditorApplyContentOptions {
  emitUpdate?: boolean;
  mode?: RichTextEditorApplyContentMode;
  selection?: RichTextEditorSelectionSnapshot | null;
}

export interface RichTextEditorExposed {
  editor: ShallowRef<Editor | undefined>;
  wordCount: Ref<number>;
  characterCount: Ref<number>;
  editorInstanceId: string;
  getRevision(): number;
  getJSON(): JSONContent | null;
  getHTML(): string;
  getText(): string;
  getSelectionSnapshot(): RichTextEditorSelectionSnapshot;
  setContent(
    content: JSONContent | string,
    options?: RichTextEditorSetContentOptions,
  ): void;
  applyContent(
    content: string,
    options?: RichTextEditorApplyContentOptions,
  ): void;
  focus(): void;
}

/** 挂载后的编辑器实例 API / Mounted editor instance API */
export interface MountedEditor {
  editorInstanceId: string;
  getRevision(): number;
  getJSON(): JSONContent | null;
  getHTML(): string;
  getText(): string;
  getSelectionSnapshot(): RichTextEditorSelectionSnapshot;
  setContent(
    content: JSONContent | string,
    options?: RichTextEditorSetContentOptions,
  ): void;
  applyContent(
    content: string,
    options?: RichTextEditorApplyContentOptions,
  ): void;
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
  id: number | string;
  name: string;
  size: number;
  mime_type: string;
  url: string;
}
