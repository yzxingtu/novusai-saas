<script lang="ts" setup>
import type { AIAgentInfo } from '#/api/admin/ai';

import { ref, watch } from 'vue';

import { Button, InputNumber, Select as ASelect, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{
  agent: AIAgentInfo;
  saving: boolean;
  active: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
}>();

const ragTopK = ref(5);
const ragScoreThreshold = ref(0.5);
const ragSearchMode = ref<'hybrid' | 'keyword' | 'vector'>('hybrid');
const ragRewriteStrategy = ref<'hyde' | 'multi' | 'none'>('none');
const ragRerankerEnabled = ref(false);
const ragContextTokenRatio = ref(0.6);

const ragSearchModeOptions = [
  {
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.hybrid'),
    value: 'hybrid',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.vector'),
    value: 'vector',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.keyword'),
    value: 'keyword',
  },
];

const ragRewriteOptions = [
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.none'),
    value: 'none',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.multi'),
    value: 'multi',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.hyde'),
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
    <p class="mb-4 text-xs text-muted-foreground">
      {{ $t('admin.ai.agent.detail.ragHint') }}
    </p>
    <div class="grid max-w-3xl grid-cols-1 gap-3 md:grid-cols-2">
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="admin-agent-rag-search-mode"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('admin.ai.agent.knowledgeBase.searchMode') }}</label
        >
        <ASelect
          id="admin-agent-rag-search-mode"
          v-model:value="ragSearchMode"
          :options="ragSearchModeOptions"
          :aria-label="$t('admin.ai.agent.knowledgeBase.searchMode')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="admin-agent-rag-rewrite-strategy"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('admin.ai.agent.knowledgeBase.rewriteStrategy') }}</label
        >
        <ASelect
          id="admin-agent-rag-rewrite-strategy"
          v-model:value="ragRewriteStrategy"
          :options="ragRewriteOptions"
          :aria-label="$t('admin.ai.agent.knowledgeBase.rewriteStrategy')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="admin-agent-rag-top-k"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('admin.ai.agent.knowledgeBase.topK') }}</label
        >
        <InputNumber
          id="admin-agent-rag-top-k"
          v-model:value="ragTopK"
          :min="1"
          :max="20"
          :aria-label="$t('admin.ai.agent.knowledgeBase.topK')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="admin-agent-rag-score-threshold"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('admin.ai.agent.knowledgeBase.scoreThreshold') }}</label
        >
        <InputNumber
          id="admin-agent-rag-score-threshold"
          v-model:value="ragScoreThreshold"
          :min="0"
          :max="1"
          :step="0.05"
          :precision="2"
          :aria-label="$t('admin.ai.agent.knowledgeBase.scoreThreshold')"
          class="w-full"
        />
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <label
          for="admin-agent-rag-context-token-ratio"
          class="mb-2 block text-xs text-muted-foreground"
          >{{ $t('admin.ai.agent.knowledgeBase.contextTokenRatio') }}</label
        >
        <InputNumber
          id="admin-agent-rag-context-token-ratio"
          v-model:value="ragContextTokenRatio"
          :min="0.1"
          :max="0.9"
          :step="0.05"
          :precision="2"
          :aria-label="$t('admin.ai.agent.knowledgeBase.contextTokenRatio')"
          class="w-full"
        />
      </div>
      <div
        class="flex flex-col items-start gap-3 rounded-xl border bg-accent/30 p-4"
      >
        <div class="min-w-0">
          <label class="mb-2 block text-xs text-muted-foreground">{{
            $t('admin.ai.agent.knowledgeBase.rerankerEnabled')
          }}</label>
          <p class="text-xs text-muted-foreground">
            {{ $t('admin.ai.agent.knowledgeBase.rerankerEnabledHelp') }}
          </p>
        </div>
        <Switch
          v-model:checked="ragRerankerEnabled"
          class="!w-auto shrink-0"
          :aria-label="$t('admin.ai.agent.knowledgeBase.rerankerEnabled')"
        />
      </div>
    </div>
    <div class="mt-5">
      <Button type="primary" :loading="saving" @click="saveRagConfig">
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
