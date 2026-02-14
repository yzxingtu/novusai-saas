<script setup lang="ts">
import { computed, shallowRef } from 'vue';

import { Alert, Button, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import type { WritePlanItem } from '../types';

const props = defineProps<{
  file: WritePlanItem | null;
  existingContent: string;
  generatedContent: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const T = 'admin.dev.crudGenerator.previewEnhanced';
const MAX_LINES = 5000;

// ---- Lazy-load Monaco DiffEditor ----
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const DiffEditor = shallowRef<unknown>(null);

import('@guolao/vue-monaco-editor').then((mod) => {
  DiffEditor.value = (mod as Record<string, unknown>).DiffEditor;
});

// ---- Language detection from file path ----
function detectLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    py: 'python',
    ts: 'typescript',
    tsx: 'typescriptreact',
    js: 'javascript',
    jsx: 'javascriptreact',
    vue: 'html',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    sql: 'sql',
    html: 'html',
    css: 'css',
    scss: 'scss',
  };
  return map[ext] ?? 'plaintext';
}

const language = computed(() => {
  if (!props.file) return 'plaintext';
  return detectLanguage(props.file.path);
});

const isCreateMode = computed(() => !props.existingContent);

const lineCount = computed(() => {
  const lines = props.generatedContent.split('\n').length;
  return lines;
});

const isTooLarge = computed(() => lineCount.value > MAX_LINES);

const truncatedGenerated = computed(() => {
  if (!isTooLarge.value) return props.generatedContent;
  return props.generatedContent.split('\n').slice(0, MAX_LINES).join('\n');
});

const truncatedExisting = computed(() => {
  if (!isTooLarge.value) return props.existingContent;
  return props.existingContent.split('\n').slice(0, MAX_LINES).join('\n');
});

const editorOptions = {
  readOnly: true,
  minimap: { enabled: false },
  lineNumbers: 'on' as const,
  scrollBeyondLastLine: false,
  renderSideBySide: true,
  fontSize: 12,
};
</script>

<template>
  <div v-if="file" class="flex flex-col gap-2">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="icon-[lucide--file-diff] size-4 text-primary" />
        <span class="font-mono text-sm font-medium">{{ file.path }}</span>
        <Tag v-if="isCreateMode" color="green" size="small">
          {{ $t(`${T}.createMode`) }}
        </Tag>
        <Tag v-else color="blue" size="small">
          {{ $t(`${T}.diffTitle`) }}
        </Tag>
      </div>
      <Button size="small" type="text" @click="emit('close')">
        <template #icon>
          <span class="icon-[lucide--x] size-4" />
        </template>
        {{ $t(`${T}.closeDiff`) }}
      </Button>
    </div>

    <!-- Too large warning -->
    <Alert
      v-if="isTooLarge"
      :message="$t(`${T}.tooLarge`, { max: MAX_LINES })"
      show-icon
      type="warning"
    />

    <!-- Diff Editor -->
    <div class="h-[400px] overflow-hidden rounded-lg border">
      <component
        :is="DiffEditor as unknown"
        v-if="DiffEditor"
        :language="language"
        :modified="truncatedGenerated"
        :options="editorOptions"
        :original="truncatedExisting"
        theme="vs"
        class="h-full w-full"
      />
      <div v-else class="flex h-full items-center justify-center text-muted-foreground">
        Loading editor...
      </div>
    </div>

    <!-- File info -->
    <div class="flex gap-4 text-xs text-muted-foreground">
      <span>{{ $t(`${T}.lineCount`, { count: lineCount }) }}</span>
      <span>{{ $t(`${T}.fileSize`, { size: file.size }) }}</span>
    </div>
  </div>
</template>
