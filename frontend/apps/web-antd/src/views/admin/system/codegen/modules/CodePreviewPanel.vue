<script lang="ts" setup>
/**
 * 代码预览面板 / Code preview panel
 *
 * 除了文件内容本身，还承载问题摘要与风险标签。
 */
import type { PreviewFile } from '#/api/admin/codegen';

import { computed, defineAsyncComponent } from 'vue';

import { useClipboard } from '@vueuse/core';
import { usePreferences } from '@vben/preferences';

import { Button, Tag } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'CodePreviewPanel' });

const props = withDefaults(
  defineProps<{
    selectedFile?: PreviewFile | null;
    previewError?: string;
    summary?: {
      create_count: number;
      modify_count: number;
      backend_files: number;
      frontend_files: number;
      total_lines: number;
    } | null;
    warnings?: string[];
    conflicts?: Array<Record<string, string>>;
  }>(),
  {
    selectedFile: null,
    previewError: undefined,
    summary: null,
    warnings: () => [],
    conflicts: () => [],
  },
);

const MonacoEditor = defineAsyncComponent({
  loader: () =>
    import('@guolao/vue-monaco-editor').then((module) => module.VueMonacoEditor ?? module.default),
  loadingComponent: { render: () => null },
});

const MonacoDiffEditor = defineAsyncComponent({
  loader: () => import('@guolao/vue-monaco-editor').then((module) => module.VueMonacoDiffEditor),
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

const conflictPathSet = computed(
  () =>
    new Set(
      props.conflicts
        .map((item) => String(item.path || '').replace(/\\/g, '/'))
        .filter(Boolean),
    ),
);

const riskTags = computed(() => {
  const file = props.selectedFile;
  if (!file) return [];
  const path = String(file.path || '').replace(/\\/g, '/');
  const items: Array<{ color: string; label: string }> = [];
  if (conflictPathSet.value.has(path)) {
    items.push({ color: 'warning', label: $t('admin.system.codegen.preview.riskConflict') });
  }
  if (file.type === 'create') {
    items.push({ color: 'success', label: $t('admin.system.codegen.preview.riskCreate') });
  }
  if (file.type === 'modify' || file.type === 'append') {
    items.push({ color: 'processing', label: $t('admin.system.codegen.preview.riskModify') });
  }
  return items;
});

const contentToCopy = computed(() => {
  const file = props.selectedFile;
  if (!file || props.previewError) return '';
  if (file.new_content !== undefined && file.new_content !== null) return file.new_content;
  return file.content ?? '';
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
      <span class="min-w-0 flex-1 truncate font-mono text-muted-foreground">
        {{ selectedFile?.path ?? $t('admin.system.codegen.preview.problemSummary') }}
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
        <span class="text-muted-foreground">
          {{ showDiff ? $t('admin.system.codegen.preview.diff') : language }}
        </span>
      </span>
    </div>

    <div class="min-h-64 flex-1 overflow-hidden">
      <div
        v-if="previewError"
        class="text-destructive flex h-full flex-col items-center justify-center gap-2 px-4 text-sm"
      >
        <span class="font-medium">{{ $t('admin.system.codegen.generate.previewError') }}</span>
        <span class="max-w-md truncate text-xs text-muted-foreground">{{ previewError }}</span>
      </div>

      <div
        v-else-if="!selectedFile"
        class="h-full overflow-y-auto px-4 py-4"
      >
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div class="rounded-2xl border border-border bg-muted/20 p-4">
            <div class="text-xs text-muted-foreground">{{ $t('admin.system.codegen.generate.summaryCreate') }}</div>
            <div class="mt-2 text-2xl font-semibold">{{ summary?.create_count ?? 0 }}</div>
          </div>
          <div class="rounded-2xl border border-border bg-muted/20 p-4">
            <div class="text-xs text-muted-foreground">{{ $t('admin.system.codegen.generate.summaryModify') }}</div>
            <div class="mt-2 text-2xl font-semibold">{{ summary?.modify_count ?? 0 }}</div>
          </div>
          <div class="rounded-2xl border border-border bg-muted/20 p-4">
            <div class="text-xs text-muted-foreground">{{ $t('admin.system.codegen.preview.filterBackend') }}</div>
            <div class="mt-2 text-2xl font-semibold">{{ summary?.backend_files ?? 0 }}</div>
          </div>
          <div class="rounded-2xl border border-border bg-muted/20 p-4">
            <div class="text-xs text-muted-foreground">{{ $t('admin.system.codegen.preview.filterFrontend') }}</div>
            <div class="mt-2 text-2xl font-semibold">{{ summary?.frontend_files ?? 0 }}</div>
          </div>
          <div class="rounded-2xl border border-border bg-muted/20 p-4">
            <div class="text-xs text-muted-foreground">{{ $t('admin.system.codegen.generate.summaryLines') }}</div>
            <div class="mt-2 text-2xl font-semibold">{{ summary?.total_lines ?? 0 }}</div>
          </div>
        </div>

        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <div class="rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
            <div class="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-800">
              <IconifyIcon icon="lucide:file-warning" class="size-4" />
              <span>{{ $t('admin.system.codegen.generate.conflicts') }}</span>
            </div>
            <div v-if="conflicts.length === 0" class="text-sm text-amber-700/80">
              {{ $t('admin.system.codegen.preview.noConflicts') }}
            </div>
            <ul v-else class="m-0 list-disc space-y-1 pl-5 text-sm text-amber-800">
              <li v-for="(item, index) in conflicts" :key="`${item.path}-${index}`">
                {{ item.path }}
              </li>
            </ul>
          </div>

          <div class="rounded-2xl border border-sky-200 bg-sky-50/70 p-4">
            <div class="mb-2 flex items-center gap-2 text-sm font-semibold text-sky-800">
              <IconifyIcon icon="lucide:badge-info" class="size-4" />
              <span>{{ $t('admin.system.codegen.preview.warnings') }}</span>
            </div>
            <div v-if="warnings.length === 0" class="text-sm text-sky-700/80">
              {{ $t('admin.system.codegen.preview.noWarnings') }}
            </div>
            <ul v-else class="m-0 list-disc space-y-1 pl-5 text-sm text-sky-800">
              <li v-for="(item, index) in warnings" :key="`${item}-${index}`">
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <template v-else>
        <div class="border-border flex flex-wrap items-center gap-2 border-b px-3 py-2">
          <Tag
            v-for="item in riskTags"
            :key="item.label"
            :color="item.color"
            class="!mr-0"
          >
            {{ item.label }}
          </Tag>
        </div>
        <MonacoDiffEditor
          v-if="showDiff"
          :original="selectedFile.original_content ?? ''"
          :modified="selectedFile.new_content ?? ''"
          :language="language"
          :theme="monacoTheme"
          :options="diffEditorOptions"
          class="h-[calc(100%-41px)] w-full"
        />
        <MonacoEditor
          v-else
          :value="selectedFile.content ?? ''"
          :language="language"
          :theme="monacoTheme"
          :options="editorOptions"
          class="h-[calc(100%-41px)] w-full"
        />
      </template>
    </div>
  </div>
</template>
