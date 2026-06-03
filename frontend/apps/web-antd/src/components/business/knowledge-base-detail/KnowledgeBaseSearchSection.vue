<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  InputNumber,
  Select,
  Spin,
} from 'ant-design-vue';

export interface KnowledgeBaseSearchResultRow {
  chunk_id: number;
  content: string;
  document_name: string;
  score: number;
}

interface SearchOption {
  label: string;
  value: string;
}

interface Props {
  i18nPrefix: string;
  loading: boolean;
  results: KnowledgeBaseSearchResultRow[];
  searchModeOptions: SearchOption[];
}

defineProps<Props>();

const emit = defineEmits<{
  search: [];
}>();

const query = defineModel<string>('query', { required: true });
const scoreThreshold = defineModel<number>('scoreThreshold', {
  required: true,
});
const searchMode = defineModel<string>('searchMode', { required: true });
const topK = defineModel<number>('topK', { required: true });
</script>

<template>
  <div class="mb-4">
    <Input
      v-model:value="query"
      :placeholder="$t(`${i18nPrefix}.searchTest.placeholder`)"
      allow-clear
      @press-enter="emit('search')"
    >
      <template #prefix>
        <IconifyIcon
          icon="lucide:search"
          class="size-4 text-muted-foreground"
        />
      </template>
      <template #suffix>
        <Button
          type="primary"
          size="small"
          :loading="loading"
          @click="emit('search')"
        >
          {{ $t(`${i18nPrefix}.searchTest.search`) }}
        </Button>
      </template>
    </Input>
  </div>

  <div
    class="mb-4 flex items-center gap-6 rounded-lg border border-border/60 bg-accent/20 px-4 py-3"
  >
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-muted-foreground">Top K</span>
      <InputNumber
        v-model:value="topK"
        :min="1"
        :max="20"
        size="small"
        class="!w-[72px]"
      />
    </div>
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-muted-foreground">
        {{ $t(`${i18nPrefix}.field.scoreThreshold`) }}
      </span>
      <InputNumber
        v-model:value="scoreThreshold"
        :min="0"
        :max="1"
        :step="0.1"
        :precision="2"
        size="small"
        class="!w-20"
      />
    </div>
    <div class="flex items-center gap-2">
      <span class="text-xs font-medium text-muted-foreground">
        {{ $t(`${i18nPrefix}.field.searchMode`) }}
      </span>
      <Select
        v-model:value="searchMode"
        size="small"
        class="!w-28"
        :options="searchModeOptions"
      />
    </div>
  </div>

  <Spin :spinning="loading">
    <Empty
      v-if="results.length === 0 && !loading"
      :description="$t(`${i18nPrefix}.searchTest.noResults`)"
    />
    <div v-else class="space-y-3">
      <div
        v-for="(result, idx) in results"
        :key="result.chunk_id"
        class="overflow-hidden rounded-lg border border-border/60 transition-colors hover:border-border"
      >
        <div
          class="flex items-center justify-between border-b border-border/40 bg-accent/20 px-4 py-2"
        >
          <div class="flex items-center gap-2.5 text-xs">
            <span
              class="flex size-5 items-center justify-center rounded bg-primary/10 font-mono font-semibold text-primary"
            >
              {{ idx + 1 }}
            </span>
            <IconifyIcon
              icon="lucide:file-text"
              class="size-3.5 text-muted-foreground"
            />
            <span class="font-medium text-foreground">{{
              result.document_name
            }}</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full bg-primary transition-all"
                :style="{ width: `${Math.min(result.score * 100, 100)}%` }"
              ></div>
            </div>
            <span class="font-mono text-xs font-medium text-primary">
              {{ (result.score * 100).toFixed(1) }}%
            </span>
          </div>
        </div>
        <div class="px-4 py-3">
          <div
            class="whitespace-pre-wrap text-sm leading-relaxed text-foreground"
          >
            {{ result.content }}
          </div>
        </div>
      </div>
    </div>
  </Spin>
</template>
