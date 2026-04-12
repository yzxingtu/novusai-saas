import type { Ref } from 'vue';

import { reactive, ref } from 'vue';

interface AgentVariable {
  default?: null | string;
  name: string;
}

interface ConversationAgentWithVars {
  id: number;
  input_variables?: AgentVariable[];
}

interface UsePanelVarsEditorOptions {
  agentsWithVarsInConversation: Ref<ConversationAgentWithVars[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  applyVariables: (
    agentId: number,
    values: Record<string, string>,
    persist?: boolean,
  ) => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  varsFormValues: Record<string, string>;
  varsPersist: Ref<boolean>;
}

export function usePanelVarsEditor(options: UsePanelVarsEditorOptions) {
  const {
    agentsWithVarsInConversation,
    allAgentsVariables,
    applyVariables,
    ensureAgentVarsLoaded,
    varsFormValues,
    varsPersist,
  } = options;

  const multiVarsModalVisible = ref(false);
  const multiVarsFormValues = reactive<Record<number, Record<string, string>>>({});
  const multiVarsPersist = ref(false);

  function openMultiVarsEditor() {
    for (const agent of agentsWithVarsInConversation.value) {
      ensureAgentVarsLoaded(agent.id);
      multiVarsFormValues[agent.id] = { ...allAgentsVariables.value[agent.id] };
      for (const variable of agent.input_variables ?? []) {
        if (!multiVarsFormValues[agent.id]![variable.name]) {
          multiVarsFormValues[agent.id]![variable.name] = variable.default ?? '';
        }
      }
    }
    multiVarsPersist.value = false;
    multiVarsModalVisible.value = true;
  }

  function onMultiVarsConfirm() {
    for (const agent of agentsWithVarsInConversation.value) {
      const values = multiVarsFormValues[agent.id];
      if (values) {
        applyVariables(agent.id, { ...values }, multiVarsPersist.value);
      }
    }
    multiVarsModalVisible.value = false;
  }

  function onSingleVarValueChange(payload: { name: string; value: string }) {
    varsFormValues[payload.name] = payload.value;
  }

  function onSinglePersistChange(value: boolean) {
    varsPersist.value = value;
  }

  function onMultiVarValueChange(payload: {
    agentId: number;
    name: string;
    value: string;
  }) {
    if (!multiVarsFormValues[payload.agentId]) {
      multiVarsFormValues[payload.agentId] = {};
    }
    multiVarsFormValues[payload.agentId]![payload.name] = payload.value;
  }

  function onMultiPersistChange(value: boolean) {
    multiVarsPersist.value = value;
  }

  function onMultiVarsCancel() {
    multiVarsModalVisible.value = false;
  }

  return {
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
  };
}
