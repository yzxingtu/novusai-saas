import type { Ref } from 'vue';

import type { InputVariable } from '#/types/ai-chat';

import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import { useDebounceFn } from '@vueuse/core';
import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import { collectCurrentPageContext } from '#/utils/page-context-collector';

interface DeferredSendContext {
  agentId: number;
  consumeMention?: boolean;
}

interface VarsModalAgentState {
  id: number;
  name: string;
  vars: InputVariable[];
}

interface UsePanelContextBridgeOptions {
  agents: Ref<Array<{ id: number }>>;
  activeConversationId: Ref<null | number>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  apiPrefix: Ref<string>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist: boolean,
  ) => void;
  clearMentionedAgent: () => void;
  chatMessages: Ref<ArrayLike<unknown>>;
  consumePendingAgentId: () => null | number;
  ensureAgentVarsLoaded: (agentId: number) => void;
  forceRerouteNextTurn: Ref<boolean>;
  handleSendMessage: () => boolean | Promise<boolean>;
  inputMessage: Ref<string>;
  loadAgents: (selectedAgentId?: number) => Promise<unknown> | unknown;
  loadConversationMessages: (
    conversationId: number,
  ) => Promise<unknown> | unknown;
  loadConversations: () => Promise<unknown> | unknown;
  manualNewConversationAgentId: Ref<null | number>;
  onConversationRestored: () => void;
  onMessageSent: () => void;
  pendingConversationId: Ref<null | number | undefined>;
  pendingMessage: Ref<null | string | undefined>;
  sendMessage: (options: {
    agentId: number;
    consumeMention?: boolean;
  }) => Promise<unknown> | unknown;
  selectedAgentId: Ref<null | number>;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
  startNewConversation: (forceReset?: boolean) => void;
  resetEndpointCaches: () => void;
  storePendingAgentId: Ref<number | undefined>;
  storePendingConversationId: Ref<null | number>;
  storePendingMessage: Ref<null | string>;
  visible: Ref<boolean>;
  /** Callback to update page context in the AI panel store */
  onPageContextCollected?: (ctx: unknown) => void;
}

export function usePanelContextBridge(options: UsePanelContextBridgeOptions) {
  // Capture route during setup so it remains usable in watcher callbacks
  // 在 setup 阶段捕获路由引用，以便在 watcher 回调中可用
  const route = useRoute();

  const varsModalVisible = ref(false);
  const varsFormValues = reactive<Record<string, string>>({});
  const varsModalAgent = ref<null | VarsModalAgentState>(null);
  const varsPersist = ref(false);
  const pendingSendContext = ref<DeferredSendContext | null>(null);

  const hasQueuedConversationRestore = computed(
    () =>
      (typeof options.pendingConversationId.value === 'number' &&
        Number.isFinite(options.pendingConversationId.value)) ||
      (typeof options.storePendingConversationId.value === 'number' &&
        Number.isFinite(options.storePendingConversationId.value)),
  );

  const hasQueuedExternalContext = computed(() => {
    const queuedMessage =
      options.pendingMessage.value?.trim() ||
      options.storePendingMessage.value?.trim?.() ||
      '';
    return (
      hasQueuedConversationRestore.value ||
      Boolean(queuedMessage) ||
      peekQueuedPendingAgentId() !== null
    );
  });

  const applyingExternalContext = ref(false);
  const openingPanelContext = ref(false);

  function resetAuxiliaryPanels() {
    options.showHistory.value = false;
    options.showMemoryPanel.value = false;
  }

  function clearVarsFormValues() {
    Object.keys(varsFormValues).forEach((key) => {
      Reflect.deleteProperty(varsFormValues, key);
    });
  }

  function resetEndpointScopedState() {
    options.startNewConversation(false);
    options.resetEndpointCaches();
    options.agents.value = [];
    options.allAgentsVariables.value = {};
    options.selectedAgentId.value = null;
    options.manualNewConversationAgentId.value = null;
    options.forceRerouteNextTurn.value = false;
    options.inputMessage.value = '';
    options.storePendingAgentId.value = undefined;
    options.storePendingConversationId.value = null;
    options.storePendingMessage.value = null;
    pendingSendContext.value = null;
    varsModalAgent.value = null;
    varsModalVisible.value = false;
    varsPersist.value = false;
    clearVarsFormValues();
    resetAuxiliaryPanels();
  }

  function peekQueuedPendingAgentId(): null | number {
    return typeof options.storePendingAgentId.value === 'number' &&
      Number.isFinite(options.storePendingAgentId.value)
      ? options.storePendingAgentId.value
      : null;
  }

  function consumeQueuedPendingAgentId(): null | number {
    const queuedPendingAgentId = peekQueuedPendingAgentId();
    if (queuedPendingAgentId === null) {
      return null;
    }

    const consumedAgentId = options.consumePendingAgentId();
    return typeof consumedAgentId === 'number' &&
      Number.isFinite(consumedAgentId)
      ? consumedAgentId
      : queuedPendingAgentId;
  }

  async function applyPendingAgentSelection(
    pendingAgentId: null | number,
    forceFreshConversation: boolean,
  ) {
    if (pendingAgentId === null) {
      return;
    }

    resetAuxiliaryPanels();
    options.forceRerouteNextTurn.value = false;
    options.manualNewConversationAgentId.value = pendingAgentId;

    await options.loadAgents(pendingAgentId);

    if (
      options.agents.value.some((agent) => agent.id === pendingAgentId) &&
      options.selectedAgentId.value !== pendingAgentId
    ) {
      options.selectedAgentId.value = pendingAgentId;
    }

    if (forceFreshConversation) {
      options.startNewConversation(true);
    }
  }

  function shouldResumeExistingConversation(pendingAgentId: null | number) {
    return (
      !pendingAgentId &&
      !hasQueuedExternalContext.value &&
      (options.activeConversationId.value !== null ||
        options.chatMessages.value.length > 0)
    );
  }

  function openVarsModal(
    vars: InputVariable[],
    agentId: number,
    agentName: string,
  ) {
    varsModalAgent.value = { id: agentId, name: agentName, vars };
    options.ensureAgentVarsLoaded(agentId);
    vars.forEach((variable) => {
      varsFormValues[variable.name] =
        options.allAgentsVariables.value[agentId]?.[variable.name] ??
        variable.default ??
        '';
    });
    varsPersist.value = false;
    varsModalVisible.value = true;
  }

  function deferSendForMissingVariables(payload: {
    agentId: number;
    agentName: string;
    consumeMention?: boolean;
    requiredVars: InputVariable[];
  }) {
    pendingSendContext.value = {
      agentId: payload.agentId,
      consumeMention: payload.consumeMention,
    };
    openVarsModal(payload.requiredVars, payload.agentId, payload.agentName);
  }

  function onVarsConfirm() {
    const varsAgent = varsModalAgent.value;
    if (!varsAgent) {
      return;
    }

    const required = varsModalAgent.value?.vars.filter((v) => v.required) ?? [];
    const missing = required.filter((v) => !varsFormValues[v.name]?.trim());
    if (missing.length > 0) {
      message.warning(
        $t('user.aiChat.varsModal.fillRequired', {
          fields: missing.map((v) => v.label || v.name).join('、'),
        }),
      );
      return;
    }

    const agentId = varsAgent.id;
    options.applyVariables(agentId, { ...varsFormValues }, varsPersist.value);
    varsModalVisible.value = false;

    if (!pendingSendContext.value) {
      return;
    }

    const { agentId: pendingAgentId, consumeMention } =
      pendingSendContext.value;
    pendingSendContext.value = null;

    if (consumeMention) {
      options.clearMentionedAgent();
    }
    void options.sendMessage({
      agentId: pendingAgentId,
    });
  }

  function onVarsCancel() {
    varsModalVisible.value = false;
    pendingSendContext.value = null;
  }

  async function applyExternalContext(): Promise<void> {
    if (
      !options.visible.value ||
      applyingExternalContext.value ||
      openingPanelContext.value
    ) {
      return;
    }

    let queuedConversationId: null | number = null;
    if (
      typeof options.pendingConversationId.value === 'number' &&
      Number.isFinite(options.pendingConversationId.value)
    ) {
      queuedConversationId = options.pendingConversationId.value;
    } else if (
      typeof options.storePendingConversationId.value === 'number' &&
      Number.isFinite(options.storePendingConversationId.value)
    ) {
      queuedConversationId = options.storePendingConversationId.value;
    }

    const queuedMessage =
      options.pendingMessage.value?.trim() ||
      options.storePendingMessage.value?.trim?.() ||
      '';
    const pendingAgentId = consumeQueuedPendingAgentId();

    if (!queuedConversationId && !queuedMessage && pendingAgentId === null) {
      return;
    }

    applyingExternalContext.value = true;
    try {
      if (!queuedConversationId && pendingAgentId !== null) {
        const hasExistingConversation =
          options.activeConversationId.value !== null ||
          options.chatMessages.value.length > 0;
        await applyPendingAgentSelection(
          pendingAgentId,
          hasExistingConversation || Boolean(queuedMessage),
        );
      }

      if (queuedConversationId) {
        options.showHistory.value = false;
        options.showMemoryPanel.value = false;
        if (options.activeConversationId.value !== queuedConversationId) {
          await options.loadConversationMessages(queuedConversationId);
        }
        if (options.activeConversationId.value === queuedConversationId) {
          options.onConversationRestored();
        }
      }

      if (queuedMessage) {
        if (!queuedConversationId && pendingAgentId !== null) {
          options.manualNewConversationAgentId.value = pendingAgentId;
          if (options.selectedAgentId.value !== pendingAgentId) {
            options.selectedAgentId.value = pendingAgentId;
          }
        }
        options.inputMessage.value = queuedMessage;
        const sent = await options.handleSendMessage();
        if (sent) {
          options.onMessageSent();
        }
      }
    } finally {
      applyingExternalContext.value = false;
    }
  }

  async function initializePanelOnOpen(): Promise<void> {
    if (!options.visible.value) {
      return;
    }

    // 收集当前页面上下文并存入 store / Collect current page context
    try {
      const ctx = collectCurrentPageContext(route);
      options.onPageContextCollected?.(ctx);
    } catch (error) {
      // collectCurrentPageContext may fail outside Vue component context
      console.warn('[AI Panel] Failed to collect page context:', error);
    }

    const pendingAgentId = consumeQueuedPendingAgentId();
    options.forceRerouteNextTurn.value = false;
    openingPanelContext.value = true;

    try {
      if (
        shouldResumeExistingConversation(pendingAgentId) ||
        hasQueuedConversationRestore.value
      ) {
        options.manualNewConversationAgentId.value = null;
      } else {
        options.manualNewConversationAgentId.value = pendingAgentId ?? null;
        // Starting a fresh routed thread should clear the local draft state,
        // while queued restore flows are handled by the external context pass.
        options.startNewConversation(true);
      }

      resetAuxiliaryPanels();
      await options.loadAgents(
        pendingAgentId ?? options.selectedAgentId.value ?? undefined,
      );

      if (
        pendingAgentId &&
        options.agents.value.some((agent) => agent.id === pendingAgentId) &&
        options.selectedAgentId.value !== pendingAgentId
      ) {
        options.selectedAgentId.value = pendingAgentId;
      }

      await options.loadConversations();
    } finally {
      openingPanelContext.value = false;
    }

    await applyExternalContext();
  }

  async function hydrateVisiblePanel(): Promise<void> {
    if (!options.visible.value) {
      return;
    }

    await options.loadAgents();
    await options.loadConversations();
    await applyExternalContext();
  }

  watch(
    [
      options.pendingConversationId,
      options.pendingMessage,
      options.storePendingConversationId,
      options.storePendingMessage,
      options.visible,
    ],
    () => {
      void applyExternalContext();
    },
    { flush: 'post' },
  );

  watch(
    options.apiPrefix,
    async (nextPrefix, previousPrefix) => {
      if (nextPrefix === previousPrefix) {
        return;
      }

      resetEndpointScopedState();
      if (options.visible.value) {
        await hydrateVisiblePanel();
      }
    },
    { flush: 'sync' },
  );

  // ── Route change watcher: refresh pageContext when route changes while panel is open ──
  // ── 路由变化监听器：面板打开期间路由切换时自动刷新页面上下文 ──
  const debouncedRefreshPageContext = useDebounceFn(() => {
    if (!options.visible.value) {
      return;
    }
    try {
      const ctx = collectCurrentPageContext(route);
      options.onPageContextCollected?.(ctx);
    } catch (error) {
      console.warn(
        '[AI Panel] Failed to refresh page context on route change:',
        error,
      );
    }
  }, 300);

  watch(
    () => route.path,
    () => {
      // Only refresh when panel is visible; next open will re-collect anyway
      // 仅在面板可见时刷新；下次打开时会重新采集
      if (options.visible.value) {
        void debouncedRefreshPageContext();
      }
    },
    { flush: 'post' },
  );

  watch(options.visible, (visible) => {
    if (visible) {
      void initializePanelOnOpen();
    }
  });

  onMounted(() => {
    if (options.visible.value) {
      void hydrateVisiblePanel();
    }
  });

  return {
    applyExternalContext,
    deferSendForMissingVariables,
    onVarsCancel,
    onVarsConfirm,
    openVarsModal,
    varsFormValues,
    varsModalAgent,
    varsModalVisible,
    varsPersist,
  };
}
