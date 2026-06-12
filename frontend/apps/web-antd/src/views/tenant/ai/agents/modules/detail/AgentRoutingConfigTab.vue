<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { getTenantAIModelsApi } from '#/api/tenant/ai';
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
  agent: AgentInfo;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const routingState = ref(createAgentRoutingState());
const routingModelOptions = ref(createEmptyAgentRoutingModelOptions());

const tierOptions = [
  { label: $t('tenant.ai.agent.routing.tier.fast'), value: 'fast' },
  { label: $t('tenant.ai.agent.routing.tier.standard'), value: 'standard' },
  { label: $t('tenant.ai.agent.routing.tier.premium'), value: 'premium' },
];

async function loadRoutingModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    const chatModels = models.filter(
      (model) => model.type === 'chat' && model.is_active,
    );
    routingModelOptions.value = buildAgentRoutingModelOptions(chatModels);
  } catch {
    routingModelOptions.value = createEmptyAgentRoutingModelOptions();
  }
}

function initRouting() {
  applyAgentRoutingConfig(
    routingState.value,
    (props.agent.routing_config ?? {}) as Record<string, unknown>,
  );
}

async function saveRouting() {
  await props.onSaveFields({
    routing_config: buildAgentRoutingPayload(routingState.value),
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initRouting();
      void loadRoutingModelOptions();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initRouting();
      void loadRoutingModelOptions();
    }
  },
);
</script>

<template>
  <AgentRoutingTab
    v-model:state="routingState"
    :can-edit="isTenantOwned"
    i18n-prefix="tenant.ai.agent"
    :model-options="routingModelOptions"
    :saving="saving"
    :show-save-button="isTenantOwned"
    :tier-options="tierOptions"
    @save="saveRouting"
  />
</template>
