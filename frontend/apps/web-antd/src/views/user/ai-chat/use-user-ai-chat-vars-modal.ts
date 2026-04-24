import type { Ref } from 'vue';

import type { AgentItem } from '#/types/ai-chat';

import type { VarsModalAgent } from './modules/ai-chat-context';

import type { InputVariable } from '#/types/ai-chat';

import { computed, reactive, ref } from 'vue';

import { message } from 'ant-design-vue';

import { usePanelVarsEditor } from '#/components/business/ai-slide-panel/use-panel-vars-editor';
import { formatLocalizedList } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { getAgentInputVariables } from '#/types/ai-chat';

interface PendingSendState {
  agentId: number;
  routeSource: null | string;
}

interface UseUserAIChatVarsModalOptions {
  agentsWithVarsInConversation: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist: boolean,
  ) => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  selectedAgent: Ref<AgentItem | null>;
  sendMessage: (options: {
    agentId: number;
    routeSource?: null | string;
  }) => boolean | Promise<boolean> | Promise<undefined> | undefined;
}

export function useUserAIChatVarsModal(options: UseUserAIChatVarsModalOptions) {
  const varsModalVisible = ref(false);
  const varsFormValues = reactive<Record<string, string>>({});
  const varsModalAgent = ref<null | VarsModalAgent>(null);
  const varsPersist = ref(false);
  const pendingSendState = ref<null | PendingSendState>(null);

  const {
    multiVarsModalVisible,
    multiVarsFormValues,
    multiVarsPersist,
    onMultiPersistChange,
    onMultiVarValueChange,
    onMultiVarsCancel,
    onMultiVarsConfirm,
    onSinglePersistChange,
    onSingleVarValueChange,
    openMultiVarsEditor,
  } = usePanelVarsEditor({
    agentsWithVarsInConversation: options.agentsWithVarsInConversation,
    allAgentsVariables: options.allAgentsVariables,
    applyVariables: options.applyVariables,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    varsFormValues,
    varsPersist,
  });

  function hasConfiguredVariables(agentId: number) {
    return (
      Object.keys(options.allAgentsVariables.value[agentId] ?? {}).length > 0
    );
  }

  const showHeaderVarsButton = computed(() => {
    return (
      options.agentsWithVarsInConversation.value.length > 0 ||
      getAgentInputVariables(options.selectedAgent.value).length > 0
    );
  });

  const headerVariablesConfigured = computed(() => {
    if (
      options.agentsWithVarsInConversation.value.some((agent) =>
        hasConfiguredVariables(agent.id),
      )
    ) {
      return true;
    }

    const selectedAgentId = options.selectedAgent.value?.id;
    if (!selectedAgentId) {
      return false;
    }

    return hasConfiguredVariables(selectedAgentId);
  });

  function openVarsModal(
    vars: InputVariable[],
    agentId: number,
    agentName: string,
  ) {
    varsModalAgent.value = { id: agentId, name: agentName, vars };
    options.ensureAgentVarsLoaded(agentId);
    vars.forEach((item) => {
      varsFormValues[item.name] =
        options.allAgentsVariables.value[agentId]?.[item.name] ??
        item.default ??
        '';
    });
    varsPersist.value = false;
    varsModalVisible.value = true;
  }

  function openSelectedAgentVarsModal() {
    const agent = options.selectedAgent.value;
    if (!agent) {
      return;
    }
    openVarsModal(getAgentInputVariables(agent), agent.id, agent.name);
  }

  function openHeaderVarsModal() {
    if (options.agentsWithVarsInConversation.value.length > 0) {
      openMultiVarsEditor();
      return;
    }
    openSelectedAgentVarsModal();
  }

  function onVarsConfirm() {
    const required =
      varsModalAgent.value?.vars.filter((item) => item.required) ?? [];
    const missing = required.filter(
      (item) => !varsFormValues[item.name]?.trim(),
    );
    if (missing.length > 0) {
      message.warning(
        $t('user.aiChat.varsModal.fillRequired', {
          fields: formatLocalizedList(
            missing.map((item) => item.label || item.name),
          ),
        }),
      );
      return;
    }

    const currentAgentId = varsModalAgent.value?.id;
    if (!currentAgentId) {
      return;
    }

    options.applyVariables(
      currentAgentId,
      { ...varsFormValues },
      varsPersist.value,
    );
    varsModalVisible.value = false;

    if (pendingSendState.value) {
      const { agentId, routeSource } = pendingSendState.value;
      pendingSendState.value = null;
      void options.sendMessage({ agentId, routeSource });
    }
  }

  function onVarsCancel() {
    varsModalVisible.value = false;
    pendingSendState.value = null;
  }

  return {
    headerVariablesConfigured,
    multiVarsFormValues,
    multiVarsModalVisible,
    multiVarsPersist,
    onMultiPersistChange,
    onMultiVarValueChange,
    onMultiVarsCancel,
    onMultiVarsConfirm,
    onSinglePersistChange,
    onSingleVarValueChange,
    openVarsModal,
    openHeaderVarsModal,
    openSelectedAgentVarsModal,
    onVarsCancel,
    onVarsConfirm,
    pendingSendState,
    showHeaderVarsButton,
    varsFormValues,
    varsModalAgent,
    varsModalVisible,
    varsPersist,
  };
}
