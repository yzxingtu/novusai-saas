<script lang="ts" setup>
import type { EditorAIPreviewResult } from './editor-ai-adapter';

import type { RichTextAIApplyMode } from '#/types/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { $t } from '@vben/locales';

import { Button } from 'ant-design-vue';

const props = defineProps<{
  canUndo: boolean;
  loading?: boolean;
  preview: EditorAIPreviewResult;
}>();

const emit = defineEmits<{
  apply: [mode: RichTextAIApplyMode];
  close: [];
  undo: [];
}>();

const selectedMode = ref<RichTextAIApplyMode>(props.preview.mode);

const modeOptions = computed(() => [
  { label: $t('common.aiWithFormat'), value: 'formatted' as const },
  { label: $t('common.aiPlainText'), value: 'plain' as const },
]);

const targetLabel = computed(() => {
  const labelMap: Record<string, string> = {
    append_to_end: $t('common.appendContent'),
    insert_after_selection: $t('common.richTextInsertAfterSelection'),
    replace_selection: $t('common.richTextReplaceSelection'),
  };
  return labelMap[props.preview.target] ?? $t('common.preview');
});

const featureTitle = computed(() => {
  const titleMap: Record<string, string> = {
    continue: $t('common.aiContinue'),
    expand: $t('common.aiExpand'),
    optimize: $t('common.aiOptimize'),
    proofread: $t('common.aiProofread'),
    rewrite: $t('common.aiRewrite'),
    summarize: $t('common.aiSummarize'),
    translate: $t('common.aiTranslate'),
  };
  return titleMap[props.preview.feature] ?? $t('common.richTextEditor');
});

const activeVariant = computed(
  () =>
    props.preview.draft[selectedMode.value] ?? props.preview.draft.formatted,
);

watch(
  () => props.preview.mode,
  (nextMode) => {
    selectedMode.value = nextMode;
  },
  { immediate: true },
);
</script>

<template>
  <div
    class="absolute inset-0 z-20 flex items-center justify-center bg-background/70 p-4 backdrop-blur-[1px]"
  >
    <div
      class="w-full max-w-3xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl"
    >
      <div
        class="flex items-center justify-between border-b border-border px-4 py-3"
      >
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:sparkles" class="size-4 text-primary" />
            <span class="truncate text-sm font-medium text-foreground">
              {{ featureTitle }}
            </span>
            <span
              class="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
            >
              {{ targetLabel }}
            </span>
          </div>
          <p
            v-if="preview.selection.selectedText"
            class="mt-1 line-clamp-2 text-xs text-muted-foreground"
          >
            {{ preview.selection.selectedText }}
          </p>
        </div>

        <Button
          type="text"
          size="small"
          :aria-label="$t('common.close')"
          @click="emit('close')"
        >
          <IconifyIcon icon="lucide:x" class="size-4" />
        </Button>
      </div>

      <div class="border-b border-border px-4 py-3">
        <div class="grid gap-2 sm:grid-cols-2">
          <Button
            v-for="mode in modeOptions"
            :key="mode.value"
            size="small"
            :type="selectedMode === mode.value ? 'primary' : 'default'"
            @click="selectedMode = mode.value"
          >
            {{ mode.label }}
          </Button>
        </div>
      </div>

      <div class="max-h-[55vh] overflow-y-auto px-4 py-4">
        <!-- eslint-disable vue/no-v-html -->
        <!-- Sanitized HTML preview from adapter / 适配器已净化的 HTML 预览 -->
        <div
          class="prose prose-sm max-w-none rounded-xl border border-border/70 bg-muted/20 p-4 text-foreground"
          v-html="activeVariant.html"
        ></div>
        <!-- eslint-enable vue/no-v-html -->
      </div>

      <div
        class="flex flex-wrap items-center justify-end gap-2 border-t border-border px-4 py-3"
      >
        <Button size="small" @click="emit('close')">
          {{ $t('common.cancel') }}
        </Button>
        <Button size="small" :disabled="!canUndo" @click="emit('undo')">
          {{ $t('common.undo') }}
        </Button>
        <Button
          type="primary"
          size="small"
          :loading="loading"
          @click="emit('apply', selectedMode)"
        >
          {{ $t('common.accept') }}
        </Button>
      </div>
    </div>
  </div>
</template>
