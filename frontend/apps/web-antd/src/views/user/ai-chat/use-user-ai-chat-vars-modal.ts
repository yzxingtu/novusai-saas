import type { Ref } from 'vue';

import type { VarsModalAgent } from './modules/ai-chat-context';

import type { InputVariable } from '#/types/ai-chat';

import { reactive, ref } from 'vue';

import { message } from 'ant-design-vue';

import { formatLocalizedList } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';

interface PendingSendState {
  agentId: number;
  routeSource: null | string;
}

interface UseUserAIChatVarsModalOptions {
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist: boolean,
  ) => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
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
    openVarsModal,
    onVarsCancel,
    onVarsConfirm,
    pendingSendState,
    varsFormValues,
    varsModalAgent,
    varsModalVisible,
    varsPersist,
  };
}
