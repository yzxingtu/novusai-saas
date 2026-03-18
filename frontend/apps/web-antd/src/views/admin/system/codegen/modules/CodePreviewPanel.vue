<script lang="ts" setup>
/**
 * 代码预览面板 / Code preview panel
 *
 * Monaco Editor 只读，有 original/new 时自动切换 Diff 模式，支持复制
 * Monaco Editor read-only, auto-switches to Diff mode when original/new available, copy button.
 */
import type { PreviewFile } from '#/api/admin/codegen';

import { computed, defineAsyncComponent } from 'vue';

import { useClipboard } from '@vueuse/core';
import { usePreferences } from '@vben/preferences';

import { Button } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'CodePreviewPanel' });

const props = withDefaults(
  defineProps<{
    selectedFile?: PreviewFile | null;
    /** 预览失败时的错误信息 / Error when preview failed */
    previewError?: string;
  }>(),
  { selectedFile: null, previewError: undefined },
);

const MonacoEditor = defineAsyncComponent({
  loader: () =>
    import('@guolao/vue-monaco-editor').then((m) => m.VueMonacoEditor ?? m.default),
  loadingComponent: { render: () => null },
});

const MonacoDiffEditor = defineAsyncComponent({
  loader: () =>
    import('@guolao/vue-monaco-editor').then((m) => m.VueMonacoDiffEditor),
  loadingComponent: { render: () => null },
});

const { isDark } = usePreferences();
const monacoTheme = computed(() => (isDark.value ? 'vs-dark' : 'vs'));

const language = computed(() => {
  const path = props.selectedFile?.path ?? '';
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
  if (path.endsWith('.vue')) return 'html';
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.yaml') || path.endsWith('.yml')) return 'yaml';
  return 'plaintext';
});

const showDiff = computed(
  () =>
    !!(
      props.selectedFile?.original_content !== undefined &&
      props.selectedFile?.new_content !== undefined &&
      props.selectedFile.original_content !== null &&
      props.selectedFile.new_content !== null
    ),
);

const editorOptions = {
  readOnly: true,
  minimap: { enabled: false },
  fontSize: 12,
  lineNumbers: 'on' as const,
  scrollBeyondLastLine: false,
  wordWrap: 'on' as const,
};

const diffEditorOptions = {
  readOnly: true,
  renderSideBySide: true,
  automaticLayout: true,
};

const contentToCopy = computed(() => {
  const f = props.selectedFile;
  if (!f || props.previewError) return '';
  if (f.new_content !== undefined && f.new_content !== null) return f.new_content;
  return f.content ?? '';
});

const { copy, copied } = useClipboard({ source: contentToCopy });

function onCopy() {
  if (!contentToCopy.value) return;
  copy();
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="border-border flex items-center justify-between gap-2 border-b px-2 py-1.5 text-xs">
      <span class="font-mono text-muted-foreground min-w-0 flex-1 truncate">
        {{ selectedFile?.path ?? '—' }}
      </span>
      <span class="flex shrink-0 items-center gap-1">
        <Button
          v-if="selectedFile && !previewError"
          type="text"
          size="small"
          class="!h-6 !px-1.5 !py-0 text-xs"
          :title="$t('common.copy')"
          @click="onCopy"
        >
          <IconifyIcon :icon="copied ? 'lucide:check' : 'lucide:copy'" class="size-3.5" />
        </Button>
        <span class="text-muted-foreground">{{ showDiff ? $t('admin.system.codegen.preview.diff') : language }}</span>
      </span>
    </div>
    <div class="min-h-64 flex-1 overflow-hidden">
      <MonacoDiffEditor
        v-if="selectedFile && !previewError && showDiff"
        :original="selectedFile.original_content ?? ''"
        :modified="selectedFile.new_content ?? ''"
        :language="language"
        :theme="monacoTheme"
        :options="diffEditorOptions"
        class="h-full w-full"
      />
      <MonacoEditor
        v-else-if="selectedFile && !previewError"
        :value="selectedFile.content ?? ''"
        :language="language"
        :theme="monacoTheme"
        :options="editorOptions"
        class="h-full w-full"
      />
      <div
        v-else-if="previewError"
        class="text-destructive flex h-full flex-col items-center justify-center gap-2 px-4 text-sm"
      >
        <span class="font-medium">{{ $t('admin.system.codegen.generate.previewError') }}</span>
        <span class="text-muted-foreground max-w-md truncate text-xs">{{ previewError }}</span>
      </div>
      <div
        v-else
        class="text-muted-foreground flex h-full items-center justify-center text-sm"
      >
        {{ $t('admin.system.codegen.generate.noPreview') }}
      </div>
    </div>
  </div>
</template>
