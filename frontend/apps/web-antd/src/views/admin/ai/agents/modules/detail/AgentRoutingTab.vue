<script lang="ts" setup>
import type { AIAgentInfo } from '#/api/admin/ai-agents';

import { ref, watch } from 'vue';

import { getAIModelListApi } from '#/api/admin/ai-models';
import AgentRoutingTab from '#/components/business/agent-routing-tab/AgentRoutingTab.vue';
import {
  applyAgentRoutingConfig,
  buildAgentRoutingModelOptions,
  buildAgentRoutingPayload,
  createAgentRoutingState,
  createEmptyAgentRoutingModelOptions,
} from '#/composables/use-agent-routing';
import { $t } from '#/locales';

const props = defineProps<{
  active: boolean;
  agent: AIAgentInfo;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const routingState = ref(createAgentRoutingState());
const routingModelOptions = ref(createEmptyAgentRoutingModelOptions());

const tierOptions = [
  { label: $t('admin.ai.agent.routing.tier.fast'), value: 'fast' },
  { label: $t('admin.ai.agent.routing.tier.standard'), value: 'standard' },
  { label: $t('admin.ai.agent.routing.tier.premium'), value: 'premium' },
];

function initAdminRouting() {
  applyAgentRoutingConfig(
    routingState.value,
    (props.agent.routing_config ?? {}) as Record<string, unknown>,
  );
}

async function loadAdminRoutingModelOptions() {
  try {
    const chatRes = await getAIModelListApi({
      'page[size]': 200,
      'filter[type][eq]': 'chat',
      'filter[is_active][eq]': true,
    });
    const chatModels = chatRes.items || [];
    routingModelOptions.value = buildAgentRoutingModelOptions(chatModels);
  } catch {
    routingModelOptions.value = createEmptyAgentRoutingModelOptions();
  }
}

async function saveAdminRouting() {
  await props.onSaveFields({
    routing_config: buildAgentRoutingPayload(routingState.value),
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initAdminRouting();
      void loadAdminRoutingModelOptions();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initAdminRouting();
      void loadAdminRoutingModelOptions();
    }
  },
);
</script>

<template>
  <AgentRoutingTab
    v-model:state="routingState"
    i18n-prefix="admin.ai.agent"
    :model-options="routingModelOptions"
    :saving="saving"
    :tier-options="tierOptions"
    @save="saveAdminRouting"
  />
</template>
