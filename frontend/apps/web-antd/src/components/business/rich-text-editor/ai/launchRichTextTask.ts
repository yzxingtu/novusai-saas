import type { Editor } from '@tiptap/core';

import type { RichTextAITask } from '#/types/ai-chat';

import { message } from 'ant-design-vue';

import { resolveAgentAssignmentApi } from '#/api/shared/agent-assignments';
import { normalizePageKey } from '#/components/business/ai-slide-panel/page-key-utils';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';

interface LaunchRichTextTaskOptions {
  contextTitle?: string;
  editor: Editor;
  editorInstanceId: string;
  feature: string;
  getRevision: () => number;
  pageKey: string;
}

const FEATURE_TITLES: Record<string, string> = {
  continue: 'common.aiContinue',
  optimize: 'common.aiOptimize',
  proofread: 'common.aiProofread',
  expand: 'common.aiExpand',
  rewrite: 'common.aiRewrite',
  summarize: 'common.aiSummarize',
  translate: 'common.aiTranslate',
};

function resolveApiPrefix(): '/admin' | '/tenant' {
  return window.location.pathname.startsWith('/admin') ? '/admin' : '/tenant';
}

function createSelectionSnapshot(
  editor: Editor,
  pageKey: string,
  editorInstanceId: string,
  revision: number,
) {
  const { from, to } = editor.state.selection;
  const docSize = editor.state.doc.content.size;
  const safeFrom = Math.max(0, Math.min(from, docSize));
  const safeTo = Math.max(safeFrom, Math.min(to, docSize));
  const beforeFrom = Math.max(0, safeFrom - 2000);
  const afterTo = Math.min(docSize, safeTo + 500);
  return {
    from: safeFrom,
    to: safeTo,
    selectedText: editor.state.doc.textBetween(safeFrom, safeTo, '\n'),
    beforeTextExcerpt: editor.state.doc.textBetween(beforeFrom, safeFrom, '\n'),
    afterTextExcerpt: editor.state.doc.textBetween(safeTo, afterTo, '\n'),
    editorRevision: revision,
    pageKey,
    editorInstanceId,
  };
}

function buildTaskMessage(
  feature: string,
  snapshot: ReturnType<typeof createSelectionSnapshot>,
  contextTitle?: string,
): string {
  const labelKey = FEATURE_TITLES[feature];
  const actionTitle = labelKey ? $t(labelKey) : feature;
  return [
    `[Rich Text Task] ${actionTitle}`,
    contextTitle ? `Document title:\n${contextTitle}` : '',
    `Selected text:\n${snapshot.selectedText || '(empty)'}`,
    snapshot.beforeTextExcerpt
      ? `Before selection:\n${snapshot.beforeTextExcerpt}`
      : '',
    snapshot.afterTextExcerpt
      ? `After selection:\n${snapshot.afterTextExcerpt}`
      : '',
  ]
    .filter(Boolean)
    .join('\n\n');
}

export async function launchRichTextTask({
  editor,
  editorInstanceId,
  feature,
  pageKey,
  contextTitle,
  getRevision,
}: LaunchRichTextTaskOptions): Promise<boolean> {
  const normalizedPageKey = normalizePageKey(pageKey);
  const snapshot = createSelectionSnapshot(
    editor,
    normalizedPageKey,
    editorInstanceId,
    getRevision(),
  );

  if (!snapshot.selectedText.trim()) {
    return false;
  }

  try {
    const assignment = await resolveAgentAssignmentApi(
      resolveApiPrefix(),
      'system.ai_writing',
    );
    if (!assignment.agent_id || !assignment.is_active) {
      message.warning($t('common.pleaseRetry'));
      return false;
    }

    const now = Date.now();
    const task: RichTextAITask = {
      taskId: `rich-text-${now}`,
      agentId: assignment.agent_id,
      pageKey: normalizedPageKey,
      editorInstanceId,
      feature,
      contextTitle,
      message: buildTaskMessage(feature, snapshot, contextTitle),
      selectionSnapshot: snapshot,
      preferredApplyMode: 'formatted',
      availableModes: ['plain', 'formatted'],
      draft: {},
      state: 'ready',
      createdAt: now,
      updatedAt: now,
      title:
        assignment.agent_name ||
        (FEATURE_TITLES[feature] ? $t(FEATURE_TITLES[feature]) : feature),
      selectionLabel: snapshot.selectedText.slice(0, 120),
    };

    const aiPanelStore = useAIPanelStore();
    aiPanelStore.setPendingRichTextTask(task);
    aiPanelStore.open();
    return true;
  } catch (error) {
    console.error('[RichTextTask] launch failed', error);
    message.error($t('common.pleaseRetry'));
    return false;
  }
}
