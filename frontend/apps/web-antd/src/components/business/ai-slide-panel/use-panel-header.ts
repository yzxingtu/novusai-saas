import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { ConversationTimelineItem } from '#/api/shared/ai-chat';
import type { AgentItem, ChatMessage, InputVariable } from '#/types/ai-chat';

import { computed, ref, unref } from 'vue';

import { message, Modal } from 'ant-design-vue';

import {
  compactChatConversationApi,
  getChatConversationTimelineApi,
} from '#/api/shared/ai-chat';
import { useDiagnosticsPolicy } from '#/composables/use-diagnostics-policy';
import { $t } from '#/locales';
import { getAgentInputVariables } from '#/types/ai-chat';
import { getErrorMessage } from '#/utils/error-helpers';

interface UsePanelHeaderOptions {
  activeConversationId: Ref<null | number>;
  agentsWithVarsInConversation: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  apiPrefix: Ref<string> | string;
  chatMessages: Ref<ChatMessage[]>;
  clearConversationMemory: () => boolean | Promise<boolean>;
  currentConversationAgentName: ComputedRef<string>;
  exportMenuItems: ComputedRef<ItemType[]>;
  fetchConversationMemory: () => Promise<unknown> | unknown;
  forceRerouteNextTurn: Ref<boolean>;
  isPinned: ComputedRef<boolean>;
  lastMemoryUpdated: Ref<boolean | null | number | string>;
  loadConversationMessages: (
    conversationId: number,
  ) => Promise<unknown> | unknown;
  onOpenMultiVarsEditor: () => void;
  onOpenVarsModal: (
    vars: InputVariable[],
    agentId: number,
    agentName: string,
  ) => void;
  routing: Ref<boolean>;
  selectedAgent: Ref<AgentItem | null>;
  showMemoryPanel: Ref<boolean>;
  totalTokensUsed: Ref<number>;
  unpinAgent: () => void;
}

export function usePanelHeader(options: UsePanelHeaderOptions) {
  const showContextDrawer = ref(false);
  const showTimelineDrawer = ref(false);
  const timelineItems = ref<ConversationTimelineItem[]>([]);
  const timelineLoading = ref(false);
  const timelineRefreshing = ref(false);
  const compactingContext = ref(false);
  const { showDiagnostics } = useDiagnosticsPolicy({
    apiPrefix: options.apiPrefix,
  });

  async function onToggleMemory() {
    if (options.showMemoryPanel.value) {
      options.showMemoryPanel.value = false;
      return;
    }
    await options.fetchConversationMemory();
    options.showMemoryPanel.value = true;
  }

  function openContextDrawer() {
    showContextDrawer.value = true;
  }

  async function openTimelineDrawer() {
    if (!options.activeConversationId.value) {
      return;
    }
    timelineLoading.value = true;
    showTimelineDrawer.value = true;
    try {
      timelineItems.value = await getChatConversationTimelineApi(
        unref(options.apiPrefix),
        options.activeConversationId.value,
      );
    } catch (error) {
      timelineItems.value = [];
      message.error(getErrorMessage(error, $t('common.loadFailed')));
    } finally {
      timelineLoading.value = false;
    }
  }

  async function refreshTimeline() {
    if (!options.activeConversationId.value) {
      return;
    }
    timelineRefreshing.value = true;
    try {
      timelineItems.value = await getChatConversationTimelineApi(
        unref(options.apiPrefix),
        options.activeConversationId.value,
      );
    } catch (error) {
      message.error(getErrorMessage(error, $t('common.loadFailed')));
    } finally {
      timelineRefreshing.value = false;
    }
  }

  async function rebuildContextSnapshot() {
    if (!options.activeConversationId.value) {
      return;
    }
    compactingContext.value = true;
    try {
      await compactChatConversationApi(
        unref(options.apiPrefix),
        options.activeConversationId.value,
      );
      await options.loadConversationMessages(
        options.activeConversationId.value,
      );
      message.success($t('common.saveSuccess'));
    } catch (error) {
      message.error(getErrorMessage(error, $t('common.saveFailed')));
    } finally {
      compactingContext.value = false;
    }
  }

  function onClearMemory() {
    Modal.confirm({
      title: $t('common.globalAiChat.clearMemoryConfirm'),
      onOk: async () => {
        const ok = await options.clearConversationMemory();
        if (ok) {
          message.success($t('common.globalAiChat.clearMemorySuccess'));
          options.showMemoryPanel.value = false;
        } else {
          message.error($t('common.globalAiChat.clearMemoryFailed'));
        }
      },
    });
  }

  function onEditHeaderVars() {
    if (options.agentsWithVarsInConversation.value.length > 0) {
      options.onOpenMultiVarsEditor();
      return;
    }
    const agent = options.selectedAgent.value;
    if (!agent) {
      return;
    }
    options.onOpenVarsModal(
      getAgentInputVariables(agent),
      agent.id,
      agent.name,
    );
  }

  const showHeaderVarsButton = computed(() => {
    return (
      options.agentsWithVarsInConversation.value.length > 0 ||
      getAgentInputVariables(options.selectedAgent.value).length > 0
    );
  });

  const hasHeaderVariableValues = computed(() =>
    options.agentsWithVarsInConversation.value.some(
      (agent) =>
        Object.keys(options.allAgentsVariables.value[agent.id] ?? {}).length >
        0,
    ),
  );

  const headerConversationSummary = computed(() => {
    if (
      options.activeConversationId.value &&
      options.currentConversationAgentName.value
    ) {
      return $t('common.globalAiChat.currentConversationAgent', {
        agent: options.currentConversationAgentName.value,
      });
    }
    if (options.routing.value) {
      return '';
    }
    return options.selectedAgent.value?.name ?? '';
  });

  const headerMoreMenuItems = computed(() => {
    const items: ItemType[] = [];

    if (options.isPinned.value) {
      items.push({
        key: 'unpin-agent',
        label: $t('common.aiPanel.unpinAgent'),
        onClick: () => {
          options.unpinAgent();
        },
      });
    }

    if (options.activeConversationId.value) {
      const conversationItems: ItemType[] = [];

      if (showDiagnostics.value) {
        conversationItems.push(
          {
            key: 'context-diagnostics',
            label: $t('common.globalAiChat.contextDiagnostics'),
            onClick: () => {
              openContextDrawer();
            },
          },
          {
            key: 'run-timeline',
            label: $t('common.globalAiChat.runTimeline'),
            onClick: () => {
              void openTimelineDrawer();
            },
          },
          {
            key: 'rebuild-context',
            label: $t('common.globalAiChat.rebuildContextCompact'),
            onClick: () => {
              void rebuildContextSnapshot();
            },
          },
        );
      }

      conversationItems.push({
        key: 'memory',
        label: $t('common.aiPanel.memory'),
        onClick: () => {
          void onToggleMemory();
        },
      });

      items.push(...conversationItems);
    }

    if (options.totalTokensUsed.value > 0) {
      items.push({
        disabled: true,
        key: 'token-usage',
        label: `${options.chatMessages.value.length} ${$t('common.globalAiChat.messages')} · ${options.totalTokensUsed.value.toLocaleString()} ${$t('common.globalAiChat.tokens')}`,
      });
    }

    if (options.chatMessages.value.length > 0) {
      items.push({
        children: options.exportMenuItems.value,
        key: 'export-conversation',
        label: $t('common.export'),
      });
    }

    return items;
  });

  const showHeaderMoreMenu = computed(
    () => headerMoreMenuItems.value.length > 0,
  );

  const headerMoreHasAttention = computed(
    () =>
      options.isPinned.value ||
      options.forceRerouteNextTurn.value ||
      !!(
        options.activeConversationId.value &&
        (options.showMemoryPanel.value || options.lastMemoryUpdated.value)
      ),
  );

  return {
    compactingContext,
    headerConversationSummary,
    headerMoreHasAttention,
    headerMoreMenuItems,
    hasHeaderVariableValues,
    onClearMemory,
    onEditHeaderVars,
    openContextDrawer,
    openTimelineDrawer,
    refreshTimeline,
    rebuildContextSnapshot,
    showContextDrawer,
    showHeaderMoreMenu,
    showHeaderVarsButton,
    showTimelineDrawer,
    timelineItems,
    timelineLoading,
    timelineRefreshing,
  };
}

export type UsePanelHeaderReturn = ReturnType<typeof usePanelHeader>;
