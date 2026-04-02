/**
 * AIPanel page operation store tests.
 * AI 面板页面操作状态测试。
 */
import type {
  RichTextAISelectionSnapshot,
  RichTextAITask,
} from '#/types/ai-chat';

import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAIPanelStore } from '../ai-panel';

function createSelectionSnapshot(
  overrides: Partial<RichTextAISelectionSnapshot> = {},
): RichTextAISelectionSnapshot {
  return {
    afterTextExcerpt: '结尾段落',
    beforeTextExcerpt: '开头段落',
    editorInstanceId: 'editor-1',
    editorRevision: 3,
    from: 5,
    pageKey: 'tenant.docs.detail',
    selectedText: '需要改写的正文',
    to: 18,
    ...overrides,
  };
}

function createRichTextTask(
  overrides: Partial<RichTextAITask> & {
    selectionSnapshot?: Partial<RichTextAISelectionSnapshot>;
  } = {},
): RichTextAITask {
  const now = Date.now();
  const pageKey = overrides.pageKey ?? 'tenant.docs.detail';
  const editorInstanceId = overrides.editorInstanceId ?? 'editor-1';

  return {
    agentId: 7,
    availableModes: ['plain', 'formatted'],
    conversationId: 101,
    contextTitle: '产品方案',
    createdAt: now - 1000,
    draft: {
      html: '<p>AI Draft</p>',
      markdown: 'AI Draft',
      plainText: 'AI Draft',
    },
    editorInstanceId,
    feature: 'rewrite',
    message: '[Rich Text Task] Rewrite',
    pageKey,
    preferredApplyMode: 'formatted',
    selectionLabel: '需要改写的正文',
    selectionSnapshot: createSelectionSnapshot({
      pageKey,
      editorInstanceId,
      ...overrides.selectionSnapshot,
    }),
    state: 'ready',
    summary: '已生成富文本草稿',
    taskId: 'rich-text-task-1',
    title: 'AI Rewrite',
    updatedAt: now - 1000,
    ...overrides,
  };
}

describe('useAIPanelStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('auto-cleans resolved page operations after a short grace period', async () => {
    const store = useAIPanelStore();
    const confirmation = store.requestPageOpConfirmation({
      invokeId: 'op-1',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
      toolCallId: 'tc-1',
    });

    expect(store.pendingPageOps).toHaveLength(1);

    store.resolvePageOp('op-1', true);
    await expect(confirmation).resolves.toBe(true);

    expect(store.pendingPageOps).toHaveLength(1);
    vi.advanceTimersByTime(1500);

    expect(store.pendingPageOps).toHaveLength(0);
  });

  it('clearResolvedPageOps keeps unresolved operations intact', () => {
    const store = useAIPanelStore();

    void store.requestPageOpConfirmation({
      invokeId: 'resolved-op',
      pageKey: 'admin.ai.agents',
      operationName: 'create_record',
      operationLabel: '新建记录',
      operationDescription: '打开新建表单',
      params: {},
    });
    void store.requestPageOpConfirmation({
      invokeId: 'pending-op',
      pageKey: 'admin.ai.agents',
      operationName: 'edit_record',
      operationLabel: '编辑记录',
      operationDescription: '打开编辑表单',
      params: {},
    });

    store.resolvePageOp('resolved-op', false);
    store.clearResolvedPageOps();

    expect(store.pendingPageOps.map((op) => op.invokeId)).toEqual([
      'pending-op',
    ]);
  });

  it('queues rich text tasks and promotes them into the pending slot with cloned data', () => {
    const store = useAIPanelStore();
    const queuedAt = Date.UTC(2026, 2, 27, 8, 0, 0);
    const promotedAt = queuedAt + 2000;

    vi.setSystemTime(queuedAt);
    const task = createRichTextTask({
      taskId: 'rich-text-task-queued',
      updatedAt: queuedAt - 500,
    });

    store.queueRichTextTask(task);

    expect(store.pendingRichTextTask).toBeNull();
    expect(store.queuedRichTextTask).toMatchObject({
      taskId: 'rich-text-task-queued',
      state: 'queued',
      updatedAt: queuedAt,
    });

    task.draft.plainText = 'mutated outside store';
    expect(store.queuedRichTextTask?.draft.plainText).toBe('AI Draft');

    vi.setSystemTime(promotedAt);
    const promoted = store.promoteQueuedRichTextTask();

    expect(store.queuedRichTextTask).toBeNull();
    expect(promoted).toMatchObject({
      taskId: 'rich-text-task-queued',
      state: 'ready',
      updatedAt: promotedAt,
    });
    expect(store.pendingRichTextTask).toMatchObject({
      taskId: 'rich-text-task-queued',
      state: 'ready',
      updatedAt: promotedAt,
    });

    if (!promoted) {
      throw new Error('Expected queued rich text task to be promoted');
    }

    promoted.selectionSnapshot.selectedText = 'mutated promoted copy';
    expect(store.pendingRichTextTask?.selectionSnapshot.selectedText).toBe(
      '需要改写的正文',
    );
  });

  it('binds rich text conversations and keeps task state in sync across pending, queued, and binding lookups', () => {
    const store = useAIPanelStore();
    const baseTime = Date.UTC(2026, 2, 27, 9, 0, 0);
    const appliedAt = baseTime + 1000;
    const undoneAt = baseTime + 2000;
    const task = createRichTextTask({
      conversationId: 88,
      taskId: 'rich-text-task-bound',
    });

    vi.setSystemTime(baseTime);
    store.setPendingRichTextTask({
      ...task,
      state: 'queued',
    });
    store.queueRichTextTask(task);
    store.bindRichTextConversation({
      agentId: task.agentId,
      conversationId: 88,
      editorInstanceId: task.editorInstanceId,
      messageIndex: 6,
      pageKey: task.pageKey,
      task,
    });

    expect(store.pendingRichTextTask?.state).toBe('ready');

    const binding = store.getRichTextConversationBinding(
      task.pageKey,
      task.editorInstanceId,
      task.agentId,
    );

    expect(binding).not.toBeNull();
    expect(binding?.task.taskId).toBe('rich-text-task-bound');

    if (!binding) {
      throw new Error('Expected rich text binding to exist');
    }

    binding.task.draft.markdown = 'mutated binding copy';
    expect(
      store.getRichTextConversationBinding(
        task.pageKey,
        task.editorInstanceId,
        task.agentId,
      )?.task.draft.markdown,
    ).toBe('AI Draft');

    vi.setSystemTime(appliedAt);
    store.markRichTextTaskApplied(task.taskId, {
      conversationId: 88,
      lastAppliedMode: 'plain',
    });

    expect(store.pendingRichTextTask).toMatchObject({
      state: 'applied',
      lastAppliedMode: 'plain',
      updatedAt: appliedAt,
    });
    expect(store.queuedRichTextTask).toMatchObject({
      state: 'applied',
      lastAppliedMode: 'plain',
      updatedAt: appliedAt,
    });
    expect(
      store.getRichTextConversationBinding(
        task.pageKey,
        task.editorInstanceId,
        task.agentId,
      )?.task,
    ).toMatchObject({
      state: 'applied',
      lastAppliedMode: 'plain',
      updatedAt: appliedAt,
    });

    vi.setSystemTime(undoneAt);
    store.markRichTextTaskUndone(task.taskId, {
      conversationId: 88,
      lastAppliedMode: 'formatted',
    });

    expect(store.pendingRichTextTask).toMatchObject({
      state: 'undone',
      lastAppliedMode: 'formatted',
      updatedAt: undoneAt,
    });
    expect(
      store.getRichTextConversationBinding(
        task.pageKey,
        task.editorInstanceId,
        task.agentId,
      )?.task,
    ).toMatchObject({
      state: 'undone',
      lastAppliedMode: 'formatted',
      updatedAt: undoneAt,
    });

    store.clearRichTextConversationBinding(
      task.pageKey,
      task.editorInstanceId,
      task.agentId,
    );

    expect(
      store.getRichTextConversationBinding(
        task.pageKey,
        task.editorInstanceId,
        task.agentId,
      ),
    ).toBeNull();
  });
});
