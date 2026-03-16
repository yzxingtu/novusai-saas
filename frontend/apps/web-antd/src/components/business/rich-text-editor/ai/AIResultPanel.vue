<script lang="ts" setup>
import { computed } from 'vue';

import { Button } from 'ant-design-vue';
import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';
import { $t } from '@vben/locales';

const props = withDefaults(
  defineProps<{
    result: string;
    loading?: boolean;
    error?: string | null;
    /** When false, retry button is disabled (e.g. no prior stream run). / 为 false 时禁用重试按钮 */
    canRetry?: boolean;
    maxHeight?: number | string;
  }>(),
  { maxHeight: 200, error: null, canRetry: true },
);

defineEmits<{
  acceptWithFormat: [];
  acceptPlain: [];
  discard: [];
  stop: [];
  retry: [];
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
</script>

<template>
  <div
    class="rte-result-enter sticky bottom-0 border-t border-border bg-background px-4 py-2"
  >
    <div
      v-if="error"
      class="mb-2 text-sm text-destructive"
    >
      {{ error }}
    </div>
    <div
      class="rte-ai-result-content mb-2 overflow-y-auto text-sm"
      :style="{ maxHeight: maxH }"
      v-html="renderedHTML"
    />
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
