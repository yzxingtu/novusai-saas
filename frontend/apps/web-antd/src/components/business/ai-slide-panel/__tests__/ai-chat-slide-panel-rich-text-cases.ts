import type { PanelMountOverrides } from './ai-chat-slide-panel-test-helpers';

import { defineComponent } from 'vue';

import { expect, it } from 'vitest';

import {
  activeConversationIdValue,
  antMessageMocks,
  createAIPanelStore,
  createRichTextMessage,
  createRichTextTask,
  createSourceEditorMock,
  flushPanel,
  mountRichTextOrchestrationHarness,
  requireElement,
  sendMessageMock,
  sourceEditorMockState,
  useAIChatState,
  visible,
} from './ai-chat-slide-panel-test-helpers';

type PanelStore = ReturnType<typeof createAIPanelStore>;

interface RegisterSlidePanelRichTextCasesOptions {
  getAiPanelStore: () => PanelStore;
  mountPanel: (overrides?: PanelMountOverrides) => {
    unmount: () => void;
  };
  setAiPanelStore: (store: PanelStore) => void;
}

export function registerSlidePanelRichTextCases(
  options: RegisterSlidePanelRichTextCasesOptions,
) {
  const { getAiPanelStore, mountPanel, setAiPanelStore } = options;

  it('dispatches a pending rich text task after reopening from the closed panel state', async () => {
    visible.value = false;
    const task = createRichTextTask({
      message: '[Rich Text Task] Rewrite from closed panel',
      taskId: 'rich-text-closed-task',
    });
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-closed',
          content: 'Draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });

    const nextStore = createAIPanelStore();
    nextStore.visible = false;
    nextStore.pendingRichTextTask = task;
    setAiPanelStore(nextStore);

    const wrapper = mountPanel();

    await flushPanel();

    expect(getAiPanelStore().open).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(getAiPanelStore().clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-closed-task',
    );
    expect(useAIChatState.chatMessages.value[0]?.richTextAI?.taskId).toBe(
      'rich-text-closed-task',
    );

    wrapper.unmount();
  });

  it('queues the latest pending rich text task while streaming', async () => {
    useAIChatState.streaming.value = true;

    const wrapper = mountPanel();

    await flushPanel();

    getAiPanelStore().pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] First queued draft',
      taskId: 'rich-text-queue-1',
    });
    await flushPanel();

    getAiPanelStore().pendingRichTextTask = createRichTextTask({
      draft: {
        html: '<p>Second</p>',
        markdown: 'Second',
        plainText: 'Second',
      },
      message: '[Rich Text Task] Latest queued draft',
      taskId: 'rich-text-queue-2',
    });
    await flushPanel();

    expect(getAiPanelStore().queueRichTextTask).toHaveBeenCalledTimes(2);
    expect(getAiPanelStore().queueRichTextTask).toHaveBeenLastCalledWith(
      expect.objectContaining({
        taskId: 'rich-text-queue-2',
      }),
    );
    expect(getAiPanelStore().queuedRichTextTask?.taskId).toBe(
      'rich-text-queue-2',
    );
    expect(getAiPanelStore().pendingRichTextTask).toBeNull();
    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(antMessageMocks.info).toHaveBeenCalledWith(
      'common.richTextTaskQueued',
    );

    wrapper.unmount();
  });

  it('flushes the queued rich text task once the panel returns to idle', async () => {
    useAIChatState.streaming.value = true;
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-queued',
          content: 'Queued draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });

    const wrapper = mountPanel();

    await flushPanel();

    getAiPanelStore().pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] Flush queued draft',
      taskId: 'rich-text-flush-1',
    });
    await flushPanel();

    expect(getAiPanelStore().queuedRichTextTask?.taskId).toBe(
      'rich-text-flush-1',
    );

    getAiPanelStore().clearPendingRichTextTask.mockClear();
    getAiPanelStore().promoteQueuedRichTextTask.mockClear();
    sendMessageMock.mockClear();
    useAIChatState.streaming.value = false;

    await flushPanel();

    expect(getAiPanelStore().promoteQueuedRichTextTask).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(getAiPanelStore().clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-flush-1',
    );
    expect(
      useAIChatState.chatMessages.value.some(
        (message) => message.richTextAI?.taskId === 'rich-text-flush-1',
      ),
    ).toBe(true);

    wrapper.unmount();
  });

  it('wires rich text apply, discard, and undo events through the slide panel', async () => {
    const task = createRichTextTask({
      taskId: 'rich-text-actions',
    });
    const sourceEditor = createSourceEditorMock(task);
    activeConversationIdValue.value = 42;
    useAIChatState.chatMessages.value = [createRichTextMessage(task)];

    const wrapper = mountPanel({
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            props: {
              index: {
                required: true,
                type: Number,
              },
              msg: {
                required: true,
                type: Object,
              },
              richTextState: {
                default: null,
                type: Object,
              },
            },
            emits: ['rich-text-apply', 'rich-text-discard', 'rich-text-undo'],
            template: `
              <div data-testid="rich-text-message-item">
                <div data-testid="rich-text-state">
                  {{
                    JSON.stringify({
                      canUndo: richTextState?.canUndo ?? false,
                      discarded: richTextState?.discarded ?? false,
                    })
                  }}
                </div>
                <button
                  data-testid="rich-text-discard-btn"
                  @click="$emit('rich-text-discard', index)"
                />
                <button
                  data-testid="rich-text-apply-btn"
                  @click="$emit('rich-text-apply', index, 'replace_selection', 'formatted')"
                />
                <button
                  data-testid="rich-text-undo-btn"
                  @click="$emit('rich-text-undo', index)"
                />
              </div>
            `,
          }),
        },
      },
    });

    await flushPanel();

    const getRichTextStateText = () =>
      requireElement(
        document.body.querySelector('[data-testid="rich-text-state"]'),
        'Expected rich text state output',
      ).textContent ?? '';
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":false');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-discard-btn"]'),
      'Expected discard trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(getRichTextStateText()).toContain('"discarded":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-apply-btn"]'),
      'Expected apply trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditorMockState.prepareRichTextContent).toHaveBeenCalledWith(
      'Draft',
      { mode: 'formatted' },
    );
    expect(sourceEditor.replaceRange).toHaveBeenCalledWith(
      4,
      12,
      'prepared::formatted::Draft',
    );
    expect(getAiPanelStore().markRichTextTaskApplied).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-undo-btn"]'),
      'Expected undo trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditor.undo).toHaveBeenCalled();
    expect(getAiPanelStore().markRichTextTaskUndone).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"canUndo":false');

    wrapper.unmount();
  });

  it('invalidates rich text undo once the active conversation changes', async () => {
    const task = createRichTextTask({
      taskId: 'rich-text-conversation-switch',
    });
    createSourceEditorMock(task);
    const { activeConversationId, wrapper } =
      await mountRichTextOrchestrationHarness({
        activeConversationId: 42,
        chatMessages: [createRichTextMessage(task)],
      });

    await flushPanel();

    const harness = wrapper.vm as unknown as {
      getRichTextDraftState: (index: number) => null | { canUndo: boolean };
      onRichTextApply: (
        index: number,
        target: 'replace_selection',
        mode: 'formatted',
      ) => void;
    };

    harness.onRichTextApply(0, 'replace_selection', 'formatted');
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(true);

    activeConversationId.value = 99;
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(false);

    wrapper.unmount();
  });

  it('keeps reopened rich text history messages read-only', async () => {
    const historyTask = createRichTextTask({
      messageClientKey: undefined,
      taskId: 'rich-text-history-readonly',
    });
    createSourceEditorMock(historyTask);
    const { wrapper } = await mountRichTextOrchestrationHarness({
      chatMessages: [
        createRichTextMessage(historyTask, {
          richTextAI: {
            ...historyTask,
            messageClientKey: undefined,
          },
        }),
      ],
    });

    await flushPanel();

    const harness = wrapper.vm as unknown as {
      getRichTextDraftState: (index: number) => unknown;
    };
    expect(harness.getRichTextDraftState(0)).toBeNull();

    wrapper.unmount();
  });
}
