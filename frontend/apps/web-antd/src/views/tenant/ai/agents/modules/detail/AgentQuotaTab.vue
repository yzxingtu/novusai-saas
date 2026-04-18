<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { Button, InputNumber } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{
  active: boolean;
  agent: AgentInfo;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const quotaConversationsPerDay = ref(0);
const quotaTokensPerDay = ref(0);
const quotaTokensPerMonth = ref(0);
const quotaMaxTurns = ref(50);
const quotaMaxConcurrent = ref(10);
const quotaUserConversationsPerDay = ref(0);

function initQuota() {
  const qc = (props.agent.quota_config ?? {}) as Record<string, number>;
  quotaConversationsPerDay.value = qc.conversations_per_day ?? 0;
  quotaTokensPerDay.value = qc.daily_token_limit ?? 0;
  quotaTokensPerMonth.value = qc.monthly_token_limit ?? 0;
  quotaMaxTurns.value = qc.max_turns_per_conversation ?? 50;
  quotaMaxConcurrent.value = qc.max_concurrent ?? 10;
  quotaUserConversationsPerDay.value = qc.user_conversations_per_day ?? 0;
}

async function saveQuota() {
  if (!props.isTenantOwned) return;
  await props.onSaveFields({
    quota_config: {
      conversations_per_day: quotaConversationsPerDay.value,
      daily_token_limit: quotaTokensPerDay.value,
      monthly_token_limit: quotaTokensPerMonth.value,
      max_turns_per_conversation: quotaMaxTurns.value,
      max_concurrent: quotaMaxConcurrent.value,
      user_conversations_per_day: quotaUserConversationsPerDay.value,
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
    <div class="mb-4 flex flex-wrap items-center gap-2">
      <p class="text-xs text-muted-foreground">
        {{ $t('tenant.ai.agent.detail.noQuotaLimit') }}
      </p>
      <span
        v-if="!isTenantOwned"
        class="rounded-full bg-warning/15 px-2 py-px text-[10px] font-medium text-warning"
        >{{ $t('tenant.ai.agent.readonlyHint') }}</span
      >
    </div>
    <div class="grid max-w-2xl grid-cols-1 gap-3 md:grid-cols-2">
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.conversationsPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaConversationsPerDay"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.tokensPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaTokensPerDay"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.tokensPerMonth')
        }}</label>
        <InputNumber
          v-model:value="quotaTokensPerMonth"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.maxTurnsPerConversation')
        }}</label>
        <InputNumber
          v-model:value="quotaMaxTurns"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.maxConcurrent')
        }}</label>
        <InputNumber
          v-model:value="quotaMaxConcurrent"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label class="mb-2 block text-xs text-muted-foreground">{{
          $t('tenant.ai.agent.quotaConfig.userConversationsPerDay')
        }}</label>
        <InputNumber
          v-model:value="quotaUserConversationsPerDay"
          :min="0"
          :disabled="!isTenantOwned"
          class="w-full"
        />
      </div>
    </div>
    <div class="mt-5">
      <Button
        type="primary"
        :loading="saving"
        :disabled="!isTenantOwned"
        @click="saveQuota"
      >
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
