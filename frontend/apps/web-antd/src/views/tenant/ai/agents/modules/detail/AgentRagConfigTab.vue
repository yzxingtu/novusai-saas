<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { Select as ASelect, Button, InputNumber, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{
  active: boolean;
  agent: AgentInfo;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const ragTopK = ref(5);
const ragScoreThreshold = ref(0.5);
const ragSearchMode = ref<'hybrid' | 'keyword' | 'vector'>('hybrid');
const ragRewriteStrategy = ref<'hyde' | 'multi' | 'none'>('none');
const ragRerankerEnabled = ref(false);
const ragContextTokenRatio = ref(0.6);

const ragSearchModeOptions = [
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.hybrid'),
    value: 'hybrid',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.vector'),
    value: 'vector',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.keyword'),
    value: 'keyword',
  },
];

const ragRewriteOptions = [
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.none'),
    value: 'none',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.multi'),
    value: 'multi',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.hyde'),
    value: 'hyde',
  },
];

function initRagConfig() {
  const rc = (props.agent.rag_config ?? {}) as Record<string, unknown>;
  ragTopK.value = (rc.top_k as number | undefined) ?? 5;
  ragScoreThreshold.value = (rc.score_threshold as number | undefined) ?? 0.5;
  ragSearchMode.value =
    (rc.search_mode as 'hybrid' | 'keyword' | 'vector' | undefined) ?? 'hybrid';
  ragRewriteStrategy.value =
    (rc.rewrite_strategy as 'hyde' | 'multi' | 'none' | undefined) ?? 'none';
  ragRerankerEnabled.value = Boolean(rc.reranker_enabled);
  ragContextTokenRatio.value =
    (rc.context_token_ratio as number | undefined) ?? 0.6;
}

async function saveRagConfig() {
  if (!props.isTenantOwned) return;
  await props.onSaveFields({
    rag_config: {
      search_mode: ragSearchMode.value,
      top_k: ragTopK.value,
      score_threshold: ragScoreThreshold.value,
      rewrite_strategy: ragRewriteStrategy.value,
      reranker_enabled: ragRerankerEnabled.value,
      context_token_ratio: ragContextTokenRatio.value,
    },
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initRagConfig();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initRagConfig();
    }
  },
);
</script>

<template>
  <div class="p-5 pt-3">
    <div class="mb-4 flex flex-wrap items-center gap-2">
      <p class="text-xs text-muted-foreground">
        {{ $t('tenant.ai.agent.detail.ragHint') }}
      </p>
      <span
        v-if="!isTenantOwned"
        class="rounded-full bg-warning/15 px-2 py-px text-[10px] font-medium text-warning"
        >{{ $t('tenant.ai.agent.readonlyHint') }}</span
      >
    </div>
    <div class="grid max-w-3xl grid-cols-1 gap-3 md:grid-cols-2">
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="tenant-agent-rag-search-mode"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.knowledgeBase.searchMode') }}</label
        >
        <ASelect
          id="tenant-agent-rag-search-mode"
          v-model:value="ragSearchMode"
          :options="ragSearchModeOptions"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.searchMode')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="tenant-agent-rag-rewrite-strategy"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.knowledgeBase.rewriteStrategy') }}</label
        >
        <ASelect
          id="tenant-agent-rag-rewrite-strategy"
          v-model:value="ragRewriteStrategy"
          :options="ragRewriteOptions"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.rewriteStrategy')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="tenant-agent-rag-top-k"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.knowledgeBase.topK') }}</label
        >
        <InputNumber
          id="tenant-agent-rag-top-k"
          v-model:value="ragTopK"
          :min="1"
          :max="20"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.topK')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="tenant-agent-rag-score-threshold"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.knowledgeBase.scoreThreshold') }}</label
        >
        <InputNumber
          id="tenant-agent-rag-score-threshold"
          v-model:value="ragScoreThreshold"
          :min="0"
          :max="1"
          :step="0.05"
          :precision="2"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.scoreThreshold')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="tenant-agent-rag-context-token-ratio"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.knowledgeBase.contextTokenRatio') }}</label
        >
        <InputNumber
          id="tenant-agent-rag-context-token-ratio"
          v-model:value="ragContextTokenRatio"
          :min="0.1"
          :max="0.9"
          :step="0.05"
          :precision="2"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.contextTokenRatio')"
          class="w-full"
        />
      </div>
      <div
        class="flex flex-col items-start gap-3 rounded-xl border bg-accent/30 p-4"
      >
        <div class="min-w-0">
          <label class="mb-2 block text-xs text-muted-foreground">{{
            $t('tenant.ai.agent.knowledgeBase.rerankerEnabled')
          }}</label>
          <p class="text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.knowledgeBase.rerankerEnabledHelp') }}
          </p>
        </div>
        <Switch
          v-model:checked="ragRerankerEnabled"
          :disabled="!isTenantOwned"
          class="self-start"
          :aria-label="$t('tenant.ai.agent.knowledgeBase.rerankerEnabled')"
        />
      </div>
    </div>
    <div class="mt-5">
      <Button
        type="primary"
        :loading="saving"
        :disabled="!isTenantOwned"
        @click="saveRagConfig"
      >
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
