<script lang="ts" setup>
import type { AIAgentInfo } from '#/api/admin/ai';

import { ref, watch } from 'vue';

import { Button, InputNumber } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{
  active: boolean;
  agent: AIAgentInfo;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const quotaConversationsPerDay = ref<number | undefined>(undefined);
const quotaTokensPerDay = ref<number | undefined>(undefined);
const quotaTokensPerMonth = ref<number | undefined>(undefined);
const quotaMaxTurns = ref<number | undefined>(undefined);
const quotaMaxConcurrent = ref<number | undefined>(undefined);
const quotaUserConversationsPerDay = ref<number | undefined>(undefined);

function initQuota() {
  const qc = (props.agent.quota_config ?? {}) as Record<string, unknown>;
  quotaConversationsPerDay.value =
    (qc.conversations_per_day as number | undefined) ?? undefined;
  quotaTokensPerDay.value =
    (qc.tokens_per_day as number | undefined) ?? undefined;
  quotaTokensPerMonth.value =
    (qc.tokens_per_month as number | undefined) ?? undefined;
  quotaMaxTurns.value =
    (qc.max_turns_per_conversation as number | undefined) ?? undefined;
  quotaMaxConcurrent.value =
    (qc.max_concurrent as number | undefined) ?? undefined;
  quotaUserConversationsPerDay.value =
    (qc.user_conversations_per_day as number | undefined) ?? undefined;
}

async function saveQuota() {
  await props.onSaveFields({
    quota_config: {
      conversations_per_day: quotaConversationsPerDay.value ?? 0,
      tokens_per_day: quotaTokensPerDay.value ?? 0,
      tokens_per_month: quotaTokensPerMonth.value ?? 0,
      max_turns_per_conversation: quotaMaxTurns.value ?? 0,
      max_concurrent: quotaMaxConcurrent.value ?? 0,
      user_conversations_per_day: quotaUserConversationsPerDay.value ?? 0,
    },
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initQuota();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initQuota();
    }
  },
);
</script>

<template>
  <div class="p-5 pt-3">
    <p class="mb-4 text-xs text-muted-foreground">
      {{ $t('admin.ai.agent.detail.noQuotaLimit') }}
    </p>
    <div class="grid max-w-2xl grid-cols-1 gap-3 md:grid-cols-2">
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.conversationsPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaConversationsPerDay"
          :min="0"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.tokensPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaTokensPerDay"
          :min="0"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.tokensPerMonth')
        }}</label>
        <InputNumber
          v-model:value="quotaTokensPerMonth"
          :min="0"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.maxTurnsPerConversation')
        }}</label>
        <InputNumber v-model:value="quotaMaxTurns" :min="0" class="w-full" />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.maxConcurrent')
        }}</label>
        <InputNumber
          v-model:value="quotaMaxConcurrent"
          :min="0"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('admin.ai.agent.quotaConfig.userConversationsPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaUserConversationsPerDay"
          :min="0"
          class="w-full"
        />
      </div>
    </div>
    <div class="mt-5">
      <Button type="primary" :loading="saving" @click="saveQuota">
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
