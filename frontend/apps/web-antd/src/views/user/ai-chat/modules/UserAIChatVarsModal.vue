<script lang="ts" setup>
import AgentVarsModal from '#/components/business/ai-slide-panel/AgentVarsModal.vue';

import { useUserAIChatContext } from './ai-chat-context';

const {
  agentsWithVarsInConversation,
  multiVarsFormValues,
  multiVarsModalVisible,
  multiVarsPersist,
  onMultiPersistChange,
  onMultiVarValueChange,
  onMultiVarsCancel,
  onMultiVarsConfirm,
  onSinglePersistChange,
  onSingleVarValueChange,
  varsModalVisible,
  varsModalAgent,
  varsFormValues,
  varsPersist,
  onVarsConfirm,
  onVarsCancel,
} = useUserAIChatContext();
</script>

<template>
  <AgentVarsModal
    :multi-agents="agentsWithVarsInConversation"
    :multi-open="multiVarsModalVisible"
    :multi-persist="multiVarsPersist"
    :multi-values="multiVarsFormValues"
    :single-agent="varsModalAgent"
    :single-open="varsModalVisible"
    :single-persist="varsPersist"
    :single-values="varsFormValues"
    @multi-cancel="onMultiVarsCancel"
    @multi-confirm="onMultiVarsConfirm"
    @multi-persist-change="onMultiPersistChange"
    @multi-value-change="onMultiVarValueChange"
    @single-cancel="onVarsCancel"
    @single-confirm="onVarsConfirm"
    @single-persist-change="onSinglePersistChange"
    @single-value-change="onSingleVarValueChange"
  />
</template>
