<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, InputNumber, message } from 'ant-design-vue';

import { getTenantAIModelsApi } from '#/api/tenant/ai';
import {
  buildAgentRoutingModelOptions,
  createEmptyAgentRoutingModelOptions,
} from '#/composables/use-agent-routing';
import { $t } from '#/locales';

const props = defineProps<{
  agent: AgentInfo;
  saving: boolean;
  active: boolean;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
}>();

const modelTemp = ref(0.7);
const modelMaxTokens = ref<number | undefined>(undefined);
const modelTopP = ref<number | undefined>(undefined);
const chatModelMaxOutputTokens = ref<Record<number, number | undefined>>({});

function initModelParams() {
  modelTemp.value = props.agent.temperature ?? 0.7;
  modelMaxTokens.value = props.agent.max_tokens ?? undefined;
  modelTopP.value = props.agent.top_p ?? undefined;
}

async function loadModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    const chatModels = models.filter((model) => model.type === 'chat');
    chatModelMaxOutputTokens.value =
      buildAgentRoutingModelOptions(chatModels).chatModelMaxOutputTokens;
  } catch {
    chatModelMaxOutputTokens.value =
      createEmptyAgentRoutingModelOptions().chatModelMaxOutputTokens;
  }
}

async function saveModelParams() {
  if (!props.isTenantOwned) return;
  const modelLimit = props.agent.model_id
    ? chatModelMaxOutputTokens.value[props.agent.model_id]
    : undefined;
  if (
    modelLimit !== null &&
    modelLimit !== undefined &&
    modelMaxTokens.value !== null &&
    modelMaxTokens.value !== undefined &&
    modelMaxTokens.value > modelLimit
  ) {
    message.warning(
      $t('tenant.ai.agent.validation.maxTokensExceedsModelLimit', {
        limit: modelLimit,
      }),
    );
    return;
  }
  await props.onSaveFields({
    temperature: modelTemp.value,
    max_tokens: modelMaxTokens.value ?? null,
    top_p: modelTopP.value ?? null,
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initModelParams();
      void loadModelOptions();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initModelParams();
      void loadModelOptions();
    }
  },
);
</script>

<template>
  <div class="p-5 pt-3">
    <div class="grid max-w-2xl grid-cols-1 gap-4 md:grid-cols-3">
      <div class="rounded-xl border bg-accent/30 p-5">
        <div class="mb-3 flex items-center gap-2">
          <div
            class="flex size-7 items-center justify-center rounded-lg bg-orange-500/10"
          >
            <IconifyIcon
              icon="lucide:thermometer"
              class="size-4 text-orange-500"
            />
          </div>
          <label class="text-sm font-medium">{{ $t('tenant.ai.agent.temperature') }}</label>
        </div>
        <p class="mb-2 text-xs text-muted-foreground">
          {{ $t('tenant.ai.agent.help.temperature') }}
        </p>
        <InputNumber
          v-model:value="modelTemp"
          :min="0"
          :max="2"
          :step="0.1"
          :disabled="!isTenantOwned"
          :placeholder="$t('tenant.ai.agent.placeholder.inputTemperature')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-5">
        <div class="mb-3 flex items-center gap-2">
          <div
            class="flex size-7 items-center justify-center rounded-lg bg-blue-500/10"
          >
            <IconifyIcon icon="lucide:hash" class="size-4 text-blue-500" />
          </div>
          <label class="text-sm font-medium">{{ $t('tenant.ai.agent.maxTokens') }}</label>
        </div>
        <p class="mb-2 text-xs text-muted-foreground">
          {{ $t('tenant.ai.agent.help.maxTokens') }}
        </p>
        <InputNumber
          v-model:value="modelMaxTokens"
          :min="1"
          :max="128000"
          :disabled="!isTenantOwned"
          :placeholder="$t('tenant.ai.agent.placeholder.inputMaxTokens')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-5">
        <div class="mb-3 flex items-center gap-2">
          <div
            class="flex size-7 items-center justify-center rounded-lg bg-purple-500/10"
          >
            <IconifyIcon icon="lucide:percent" class="size-4 text-purple-500" />
          </div>
          <label class="text-sm font-medium">{{ $t('tenant.ai.agent.topP') }}</label>
        </div>
        <p class="mb-2 text-xs text-muted-foreground">
          {{ $t('tenant.ai.agent.help.topP') }}
        </p>
        <InputNumber
          v-model:value="modelTopP"
          :min="0"
          :max="1"
          :step="0.1"
          :disabled="!isTenantOwned"
          :placeholder="$t('tenant.ai.agent.placeholder.inputTopP')"
          class="w-full"
        />
      </div>
    </div>
    <div v-if="isTenantOwned" class="mt-5">
      <Button type="primary" :loading="saving" @click="saveModelParams">
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
