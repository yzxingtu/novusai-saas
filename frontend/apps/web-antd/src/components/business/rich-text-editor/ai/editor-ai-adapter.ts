import type { JSONContent } from '@tiptap/core';

import type {
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
} from '#/types/ai-chat';

export interface EditorAISelectionRange {
  afterTextExcerpt: string;
  beforeTextExcerpt: string;
  editorRevision: number;
  from: number;
  selectedContent: JSONContent | null;
  selectedText: string;
  to: number;
}

export interface EditorAIDraftVariant {
  html: string;
  json: JSONContent;
  text: string;
}

export interface EditorAIDraftContent {
  formatted: EditorAIDraftVariant;
  plain: EditorAIDraftVariant;
  raw: string;
}

export interface EditorAIOperation {
  contextTitle?: string;
  conversationId?: null | number;
  draft?: EditorAIDraftContent;
  feature: string;
  mode?: RichTextAIApplyMode;
  selection?: EditorAISelectionRange | null;
  target?: RichTextAIApplyTarget;
}

export interface EditorAIPreviewResult {
  agentId: number;
  contextTitle?: string;
  conversationId?: null | number;
  draft: EditorAIDraftContent;
  feature: string;
  mode: RichTextAIApplyMode;
  selection: EditorAISelectionRange;
  target: RichTextAIApplyTarget;
}

export interface EditorAIApplyResult {
  applied: boolean;
  reason?: 'editor_unavailable' | 'missing_preview' | 'selection_changed';
}

export interface EditorAIAdapter {
  applyOperation(operation: EditorAIOperation): Promise<EditorAIApplyResult>;
  canUndoLastOperation(): boolean;
  getDocumentModel(): JSONContent | null;
  getSelection(): EditorAISelectionRange | null;
  previewOperation(
    operation: EditorAIOperation,
  ): Promise<EditorAIPreviewResult>;
  undoLastAIOperation(): boolean;
}

export const EDITOR_AI_FEATURE_LABEL_KEYS: Record<string, string> = {
  continue: 'common.aiContinue',
  expand: 'common.aiExpand',
  optimize: 'common.aiOptimize',
  proofread: 'common.aiProofread',
  rewrite: 'common.aiRewrite',
  summarize: 'common.aiSummarize',
  translate: 'common.aiTranslate',
};

export function resolveEditorAIFeatureLabelKey(feature: string): string {
  return EDITOR_AI_FEATURE_LABEL_KEYS[feature] ?? 'common.richTextEditor';
}
