import type {
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextAITask,
  RichTextDraftRuntimeState,
} from '#/components/business/ai-chat-panel/types';

import {
  prepareRichTextContent,
  resolveSourceEditor,
} from '#/components/business/rich-text-editor/sourceEditorRegistry';
import { $t } from '#/locales';

export interface RichTextDraftUiStateInternal {
  discarded?: boolean;
  editorRevisionAfterApply?: number;
  lastApplyMode?: RichTextAIApplyMode;
  lastApplyTarget?: RichTextAIApplyTarget;
  undoAvailable?: boolean;
}

export interface LastAppliedRichTextAction {
  clientKey: string;
  editorInstanceId: string;
  editorRevisionAfterApply: number;
  pageKey: string;
}

export type ApplyRichTextTaskToEditorResult =
  | {
      kind: 'applied';
      editorRevisionAfterApply: number;
      nextTask: RichTextAITask;
    }
  | {
      kind: 'editor_unavailable';
    }
  | {
      kind: 'noop';
    };

export type UndoRichTextTaskInEditorResult =
  | {
      kind: 'invalidate_last_action';
    }
  | {
      kind: 'noop';
    }
  | {
      kind: 'undone';
      nextTask: RichTextAITask;
    };

export function attachRichTextTaskToMessage(
  messageItem: ChatMessage | undefined,
  task: RichTextAITask,
): null | RichTextAITask {
  if (!messageItem || messageItem.role !== 'assistant') {
    return null;
  }
  const nextTask: RichTextAITask = {
    ...task,
    messageClientKey: messageItem.clientKey,
    updatedAt: Date.now(),
  };
  messageItem.source = 'rich_text_ai';
  messageItem.richTextFeature = nextTask.feature;
  messageItem.richTextAI = nextTask;
  return nextTask;
}

export function computeRichTextDraftState(
  task: RichTextAITask,
  uiState: RichTextDraftUiStateInternal = {},
): RichTextDraftRuntimeState {
  const sourceEditor = resolveSourceEditor(task.pageKey, task.editorInstanceId);
  const isMounted = !!sourceEditor?.isMounted();
  const currentRevision =
    isMounted && sourceEditor ? sourceEditor.getRevision() : null;
  const selectionStable =
    isMounted &&
    currentRevision === task.selectionSnapshot.editorRevision &&
    !!task.selectionSnapshot.selectedText.trim();
  let helperText: null | string = null;
  if (!isMounted) {
    helperText = $t('common.richTextDraftEditorUnavailable');
  } else if (!selectionStable) {
    helperText = $t('common.richTextDraftSelectionChanged');
  }

  return {
    canReplaceSelection: selectionStable,
    canInsertAfterSelection: selectionStable,
    canAppendToEnd: isMounted,
    canCopy: true,
    canUndo:
      !!uiState.undoAvailable &&
      isMounted &&
      currentRevision === uiState.editorRevisionAfterApply,
    discarded: uiState.discarded,
    helperText,
    lastApplyMode: uiState.lastApplyMode ?? task.lastAppliedMode,
    lastApplyTarget: uiState.lastApplyTarget ?? task.lastAppliedTarget,
  };
}

export function applyRichTextTaskToEditor(
  messageItem: ChatMessage,
  target: RichTextAIApplyTarget,
  mode: RichTextAIApplyMode,
): ApplyRichTextTaskToEditorResult {
  if (messageItem.role !== 'assistant' || !messageItem.richTextAI) {
    return { kind: 'noop' };
  }

  const task = messageItem.richTextAI;
  const sourceEditor = resolveSourceEditor(task.pageKey, task.editorInstanceId);
  if (!sourceEditor || !sourceEditor.isMounted()) {
    return { kind: 'editor_unavailable' };
  }

  const requiresStableSelection =
    target === 'replace_selection' || target === 'insert_after_selection';
  if (
    requiresStableSelection &&
    sourceEditor.getRevision() !== task.selectionSnapshot.editorRevision
  ) {
    return { kind: 'noop' };
  }

  const rawContent =
    mode === 'plain'
      ? task.draft.plainText || task.draft.markdown || messageItem.content
      : task.draft.markdown || messageItem.content;
  const preparedContent = prepareRichTextContent(rawContent, { mode });

  let applied = false;
  switch (target) {
    case 'append_to_end':
      applied = sourceEditor.appendToEnd(preparedContent);
      break;
    case 'insert_after_selection':
      applied = sourceEditor.insertAfterRange(
        task.selectionSnapshot.from,
        task.selectionSnapshot.to,
        preparedContent,
      );
      break;
    case 'replace_selection':
      applied = sourceEditor.replaceRange(
        task.selectionSnapshot.from,
        task.selectionSnapshot.to,
        preparedContent,
      );
      break;
  }

  if (!applied) {
    return { kind: 'noop' };
  }

  const nextTask: RichTextAITask = {
    ...task,
    state: 'applied',
    lastAppliedMode: mode,
    lastAppliedTarget: target,
    updatedAt: Date.now(),
  };
  messageItem.richTextAI = nextTask;
  return {
    kind: 'applied',
    nextTask,
    editorRevisionAfterApply: sourceEditor.getRevision(),
  };
}

export function undoRichTextTaskInEditor(
  messageItem: ChatMessage,
  uiState: RichTextDraftUiStateInternal | undefined,
): UndoRichTextTaskInEditorResult {
  if (messageItem.role !== 'assistant' || !messageItem.richTextAI) {
    return { kind: 'noop' };
  }

  const task = messageItem.richTextAI;
  const sourceEditor = resolveSourceEditor(task.pageKey, task.editorInstanceId);
  if (
    !sourceEditor ||
    !sourceEditor.isMounted() ||
    !uiState?.undoAvailable ||
    uiState.editorRevisionAfterApply !== sourceEditor.getRevision()
  ) {
    return { kind: 'invalidate_last_action' };
  }

  const undone = sourceEditor.undo();
  if (!undone) {
    return { kind: 'noop' };
  }

  const nextTask: RichTextAITask = {
    ...task,
    state: 'undone',
    updatedAt: Date.now(),
  };
  messageItem.richTextAI = nextTask;
  return {
    kind: 'undone',
    nextTask,
  };
}

export function isLastAppliedRichTextActionValid(
  action: LastAppliedRichTextAction,
): boolean {
  const sourceEditor = resolveSourceEditor(
    action.pageKey,
    action.editorInstanceId,
  );
  return !!(
    sourceEditor &&
    sourceEditor.isMounted() &&
    sourceEditor.getRevision() === action.editorRevisionAfterApply
  );
}
