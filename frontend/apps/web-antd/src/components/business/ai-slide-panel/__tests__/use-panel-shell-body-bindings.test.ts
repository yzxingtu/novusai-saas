// @vitest-environment happy-dom
/**
 * Test type: behavioral
 * Verifies: panel body bindings propagate welcome loading state and block send/Enter event paths while welcome generation is pending.
 * Mock strategy: no child components are mounted; the real bindings composable computes props and listeners.
 */
import { computed, ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { usePanelShellBodyBindings } from '../use-panel-shell-body-bindings';

function createOptions() {
  const handleSendMessage = vi.fn(async () => true);
  return {
    actionClick: vi.fn(),
    activeConversationId: ref(null),
    agentKBBindings: ref([]),
    agents: ref([
      {
        avatar: null,
        description: null,
        id: 1,
        name: 'Copilot',
        status: 'published',
        tenant_id: 1,
      },
    ]),
    apiPrefix: ref('/tenant'),
    askSuggested: vi.fn(),
    attachDisabled: computed(() => true),
    attachmentAccept: computed(() => ''),
    attachmentLimitHint: computed(() => ''),
    attachments: computed(() => []),
    boundKnowledgeBases: computed(() => []),
    cancelEditTitle: vi.fn(),
    characterCount: computed(() => 4),
    chatMessages: ref([]),
    commitEditTitle: vi.fn(),
    compactMessages: computed(() => true),
    composerMentionCandidates: computed(() => []),
    confirmAction: vi.fn(),
    confirmConsent: vi.fn(),
    conversationSearch: ref(''),
    conversationsCount: computed(() => 0),
    conversationsLoading: ref(false),
    copyMessage: vi.fn(async () => undefined),
    editAndResend: vi.fn(),
    editingConversationId: ref(null),
    editingTitle: ref(''),
    effectiveSuggestedQuestions: ref(['建议一']),
    effectiveWelcomeMessage: ref('动态欢迎语'),
    ensureAgentKnowledgeBases: vi.fn(async () => []),
    ensureAgentSkills: vi.fn(async () => []),
    exportMenuItems: computed(() => []),
    fileSelect: vi.fn(),
    groupedConversations: computed(() => []),
    handleDragOver: vi.fn(),
    handleDrop: vi.fn(),
    handleInputKeyDown: vi.fn(() => false),
    handleMessagesScroll: vi.fn(),
    handleOpenUrl: vi.fn(),
    handleSendMessage,
    inputMessage: ref('问题'),
    mentionEmptyHint: computed(() => ''),
    mentionLoading: ref(false),
    mentionMixedHint: '',
    mentionOpen: ref(false),
    newChat: vi.fn(),
    onDeleteConversation: vi.fn(),
    onSelectConversation: vi.fn(),
    onSelectMentionCandidate: vi.fn(),
    paste: vi.fn(),
    registerMessagesContainer: vi.fn(),
    regenerateMessage: vi.fn(),
    rejectAction: vi.fn(),
    rejectConsent: vi.fn(),
    removeAttachment: vi.fn(),
    removeSelectedKnowledgeBase: vi.fn(),
    retryLastMessage: vi.fn(),
    routing: ref(false),
    scrollToBottom: vi.fn(),
    scrollToTop: vi.fn(),
    selectedAgent: ref({
      avatar: null,
      description: null,
      id: 1,
      name: 'Copilot',
      status: 'published',
      tenant_id: 1,
    }),
    selectedKnowledgeBases: computed(() => []),
    selectedSkillPackages: computed(() => []),
    sendDisabled: computed(() => true),
    sending: ref(false),
    sendState: computed(() => 'idle' as const),
    shiftEnterHint: '',
    showAttachments: ref(true),
    showHistory: ref(false),
    showScrollToBottom: ref(false),
    showScrollToTop: ref(false),
    startEditTitle: vi.fn(),
    stopGeneration: vi.fn(),
    streaming: ref(false),
    totalTokensUsed: ref(0),
    welcomeLoading: ref(true),
    welcomeLoadingHint: ref('Copilot 正在准备开场建议'),
  } satisfies Parameters<typeof usePanelShellBodyBindings>[0] & {
    handleSendMessage: typeof handleSendMessage;
  };
}

describe('usePanelShellBodyBindings welcome loading', () => {
  it('propagates welcome loading props and blocks send listener paths', async () => {
    const options = createOptions();
    const { panelBodyListeners, panelBodyProps } =
      usePanelShellBodyBindings(options);

    expect(panelBodyProps.value.welcomeLoading).toBe(true);
    expect(panelBodyProps.value.welcomeLoadingHint).toBe(
      'Copilot 正在准备开场建议',
    );
    expect(panelBodyProps.value.sendDisabled).toBe(true);
    expect(panelBodyProps.value.attachDisabled).toBe(true);

    await panelBodyListeners.send();

    expect(options.handleSendMessage).not.toHaveBeenCalled();

    const enterEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
    });
    const preventDefault = vi.spyOn(enterEvent, 'preventDefault');

    panelBodyListeners.keydown(enterEvent);

    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(options.handleSendMessage).not.toHaveBeenCalled();
  });
});
