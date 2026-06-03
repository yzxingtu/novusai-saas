import type {
  RichTextAiActionType,
  RichTextAiApplyMode,
} from '#/features/rich-text-ai';

export interface TextSelectionAiSnapshot {
  afterText: string;
  beforeText: string;
  empty: boolean;
  from: number;
  plainInputPolicy?: TextSelectionPlainInputPolicy;
  revision: number;
  selectedText: string;
  sessionId?: string;
  to: number;
}

export interface TextSelectionPlainInputPolicy {
  allowedActions: RichTextAiActionType[];
  enabled: boolean;
  fieldKind: string;
}

export interface TextSelectionAiAnchorRect {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
}

export interface TextSelectionAiApplyRequest {
  applyMode: RichTextAiApplyMode | string;
  content: string;
  mode: 'insert' | 'replace';
  selection: TextSelectionAiSnapshot;
}

export interface TextSelectionAiAssistOpenOptions {
  requireSelection?: boolean;
  silent?: boolean;
  unavailableReasonKey?: string;
}

export interface TextSelectionAiAssistExpose {
  close: () => void;
  discard: () => void;
  isPromptOpen: () => boolean;
  isWorkflowActive: () => boolean;
  notify: (
    type: 'error' | 'info' | 'success',
    key: string,
    params?: Record<string, unknown>,
  ) => void;
  open: (
    event?: KeyboardEvent | MouseEvent,
    options?: TextSelectionAiAssistOpenOptions,
  ) => void;
  reposition: () => void;
}

export interface TextSelectionAiAssistProps {
  apiPrefix?: string;
  documentId?: null | number;
  documentTitle?: string;
  documentType?: string;
  editable?: boolean;
  enabled?: boolean;
  enabledActions?: RichTextAiActionType[];
  featureCode?: string;
  getAnchorRect?: (
    selection: null | TextSelectionAiSnapshot,
  ) => null | TextSelectionAiAnchorRect;
  getSelection: () => null | TextSelectionAiSnapshot;
  i18nPrefix?: string;
  requireSelectionToOpen?: boolean;
  surface?: string;
  validateSelection: (selection: TextSelectionAiSnapshot) => boolean;
  applyResult: (request: TextSelectionAiApplyRequest) => boolean | undefined;
}
