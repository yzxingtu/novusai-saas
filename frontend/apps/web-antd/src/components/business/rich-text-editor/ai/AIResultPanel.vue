<script lang="ts" setup>
import { computed } from 'vue';

import { Button } from 'ant-design-vue';
import MarkdownIt from 'markdown-it';
import { $t } from '@vben/locales';

const props = withDefaults(
  defineProps<{
    result: string;
    loading?: boolean;
    maxHeight?: number | string;
  }>(),
  { maxHeight: 200 },
);

defineEmits<{
  acceptWithFormat: [];
  acceptPlain: [];
  discard: [];
}>();

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const renderedHTML = computed(() => {
  if (!props.result) return '';
  return md.render(props.result);
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
      class="rte-ai-result-content mb-2 overflow-y-auto text-sm"
      :style="{ maxHeight: maxH }"
      v-html="renderedHTML"
    />
    <div class="flex items-center justify-end gap-2">
      <Button size="small" @click="$emit('discard')">
        {{ $t('common.discard') }}
      </Button>
      <Button
        size="small"
        :disabled="loading || !result"
        @click="$emit('acceptPlain')"
      >
        {{ $t('common.aiPlainText') }}
      </Button>
      <Button
        size="small"
        type="primary"
        :disabled="loading || !result"
        @click="$emit('acceptWithFormat')"
      >
        {{ $t('common.aiWithFormat') }}
      </Button>
    </div>
  </div>
</template>
