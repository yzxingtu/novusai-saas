/**
 * Shared Rich Text AI frontend contracts.
 *
 * The NovusDoc/RichTextEditor runtime uses system.ai_writing for editor-domain
 * rich-text operations. Keep this file free of page-runtime, DOM-scanning, or
 * page operation tool coupling.
 */

export const RICH_TEXT_AI_MANIFEST_FEATURE_CODE = 'rich_text_ai' as const;
export const RICH_TEXT_AI_FEATURE_CODE = 'system.ai_writing' as const;
export const RICH_TEXT_AI_FEATURE_CODE_RESOLUTION_ORDER = [
  RICH_TEXT_AI_FEATURE_CODE,
] as const;

export type RichTextAiFeatureCode = typeof RICH_TEXT_AI_FEATURE_CODE;

export const RICH_TEXT_AI_WRITING_ACTIONS = [
  'continue',
  'insert',
  'rewrite',
  'optimize',
  'proofread',
  'translate',
  'summarize',
  'expand',
  'format',
  'custom',
  'chat',
] as const;

export type RichTextAiWritingAction =
  (typeof RICH_TEXT_AI_WRITING_ACTIONS)[number];

export type RichTextAiActionType = RichTextAiWritingAction;

export type RichTextAiOperationKind =
  | 'assist'
  | 'format'
  | 'insert'
  | 'summarize'
  | 'transform'
  | 'translate';

export type RichTextAiApplyMode =
  | 'append_to_document'
  | 'copy_only'
  | 'insert_after_selection'
  | 'insert_at_cursor'
  | 'replace_selection';

export type RichTextAiFormatPreset =
  | 'bullet_list'
  | 'plain_text'
  | 'preserve_structure'
  | 'structured_sections';

export interface RichTextAiActionTemplate {
  action: RichTextAiActionType;
  defaultApplyMode: RichTextAiApplyMode;
  defaultFormatPreset?: RichTextAiFormatPreset;
  descriptionKey: string;
  endpointFeature: RichTextAiWritingAction;
  icon: string;
  labelKey: string;
  operationKind: RichTextAiOperationKind;
  promptHintKey: string;
  requiresSelection: boolean;
  supportsCustomInstruction: boolean;
  supportsFormatInstruction: boolean;
  tagColor: string;
  visibleInContextMenu: boolean;
}

export interface RichTextAiFormatTemplate {
  descriptionKey: string;
  formatInstructionKey: string;
  icon: string;
  labelKey: string;
  preset: RichTextAiFormatPreset;
}

export interface RichTextAiActionGroup {
  actions: RichTextAiActionTemplate[];
  kind: RichTextAiOperationKind;
}

export function isRichTextAiWritingAction(
  value: string,
): value is RichTextAiWritingAction {
  return (RICH_TEXT_AI_WRITING_ACTIONS as readonly string[]).includes(value);
}
