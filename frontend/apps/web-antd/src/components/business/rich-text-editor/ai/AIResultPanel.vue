<script lang="ts" setup>
import type { AppErrorInfo } from '#/utils/request';

import { computed } from 'vue';

import { $t } from '@vben/locales';

import { Button } from 'ant-design-vue';
import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';

import { isDevErrorMode } from '#/utils/request';

const props = withDefaults(
  defineProps<{
    /** When false, retry button is disabled (e.g. no prior stream run). / 为 false 时禁用重试按钮 */
    canRetry?: boolean;
    error?: AppErrorInfo | null;
    loading?: boolean;
    maxHeight?: number | string;
    result: string;
  }>(),
  { maxHeight: 200, error: null, canRetry: true },
);

defineEmits<{
  acceptPlain: [];
  acceptWithFormat: [];
  discard: [];
  retry: [];
  stop: [];
}>();

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const renderedHTML = computed(() => {
  if (!props.result) return '';
  const raw = md.render(props.result);
  return DOMPurify.sanitize(raw);
});

const maxH = computed(() => {
  const v = props.maxHeight;
  return typeof v === 'number' ? `${v}px` : v;
});

const showErrorDebug = computed(
  () => isDevErrorMode() && !!props.error?.debugMessage,
);
</script>

<template>
  <div
    class="rte-result-enter sticky bottom-0 border-t border-border bg-background px-4 py-2"
  >
    <div
      v-if="error"
      class="mb-2 rounded border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
    >
      <p>{{ error.message }}</p>
      <p v-if="error.traceId" class="mt-1 text-xs text-muted-foreground">
        {{ `${$t('common.http.traceId')}: ${error.traceId}` }}
      </p>
      <pre
        v-if="showErrorDebug"
        class="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all rounded bg-black/5 p-2 text-xs text-red-500"
        >{{ error?.debugMessage }}</pre
      >
    </div>
    <!-- eslint-disable vue/no-v-html -->
    <div
      class="rte-ai-result-content mb-2 overflow-y-auto text-sm"
      :style="{ maxHeight: maxH }"
      v-html="renderedHTML"
    ></div>
    <!-- eslint-enable vue/no-v-html -->
    <div class="flex items-center justify-end gap-2">
      <Button
        v-if="loading"
        size="small"
        @click="$emit('stop')"
        :aria-label="$t('common.stopGeneration')"
      >
        {{ $t('common.stopGeneration') }}
      </Button>
      <Button
        v-if="error"
        size="small"
        :disabled="!canRetry"
        @click="$emit('retry')"
        :aria-label="$t('common.retry')"
      >
        {{ $t('common.retry') }}
      </Button>
      <Button
        size="small"
        @click="$emit('discard')"
        :aria-label="$t('common.discard')"
      >
        {{ $t('common.discard') }}
      </Button>
      <Button
        size="small"
        :disabled="loading || !result"
        @click="$emit('acceptPlain')"
        :aria-label="$t('common.aiPlainText')"
      >
        {{ $t('common.aiPlainText') }}
      </Button>
      <Button
        size="small"
        type="primary"
        :disabled="loading || !result"
        @click="$emit('acceptWithFormat')"
        :aria-label="$t('common.aiWithFormat')"
      >
        {{ $t('common.aiWithFormat') }}
      </Button>
    </div>
  </div>
</template>
