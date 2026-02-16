<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import {
  Button,
  Card,
  Empty,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Tree,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { PreviewFileItem } from '#/api/admin/crud-generator';

import { previewCrudGenerateApi } from '#/api/admin/crud-generator';

import type { CrudConfig } from '../types';

const props = defineProps<{
  config: CrudConfig;
}>();

const T = 'admin.dev.crudGenerator.preview';

// ============================================================
// 状态
// ============================================================

const activeTab = ref<'code' | 'migration'>('code');
const selectedFileKey = ref<string>('');
const copied = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);
const previewFiles = ref<PreviewFileItem[]>([]);
const migrationContent = ref('');
const migrationPath = ref('');
const warnings = ref<string[]>([]);

// ============================================================
// 从后端获取真实预览
// ============================================================

async function fetchPreview() {
  if (!props.config.module || props.config.fields.length === 0) {
    previewFiles.value = [];
    migrationContent.value = '';
    migrationPath.value = '';
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    const res = await previewCrudGenerateApi(props.config);
    const allFiles = res.files || [];
    // Extract migration file from preview files
    const migFile = allFiles.find((f) => f.path.includes('migrations/versions/crud/'));
    if (migFile) {
      migrationContent.value = migFile.content || '';
      migrationPath.value = migFile.path;
    } else {
      migrationContent.value = '';
      migrationPath.value = '';
    }
    // Show all files (including migration) in the code tree
    previewFiles.value = allFiles;
    warnings.value = res.warnings || [];

    // 自动选中第一个文件
    if (previewFiles.value.length > 0 && !selectedFileKey.value) {
      selectedFileKey.value = previewFiles.value[0]!.path;
    }
  } catch (e: unknown) {
    error.value = (e as Error).message || String(e);
    previewFiles.value = [];
    migrationContent.value = '';
    migrationPath.value = '';
  } finally {
    loading.value = false;
  }
}

// 当配置变化时自动刷新（防抖）
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => [props.config.module, props.config.fields.length, props.config.scope],
  () => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fetchPreview, 800);
  },
  { immediate: true },
);

// ============================================================
// 文件分组与语言推断
// ============================================================

function inferGroup(path: string): string {
  if (path.startsWith('backend/tests/')) return 'test';
  if (path.startsWith('backend/')) return 'backend';
  if (path.includes('/locales/') || path.includes('/i18n/')) return 'i18n';
  if (path.startsWith('frontend/')) return 'frontend';
  return 'backend';
}

function inferLang(path: string): string {
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.ts')) return 'typescript';
  if (path.endsWith('.vue')) return 'vue';
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.sql')) return 'sql';
  return 'text';
}

/** 文件树数据 */
const treeData = computed(() => {
  const groups: Record<string, { title: string; key: string; icon: string; children: { title: string; key: string; isLeaf: boolean }[] }> = {};

  const groupMeta: Record<string, { titleKey: string; icon: string }> = {
    backend: { titleKey: 'groupBackend', icon: 'icon-[lucide--server]' },
    frontend: { titleKey: 'groupFrontend', icon: 'icon-[lucide--monitor]' },
    i18n: { titleKey: 'groupI18n', icon: 'icon-[lucide--languages]' },
    test: { titleKey: 'groupTest', icon: 'icon-[lucide--flask-conical]' },
  };

  for (const file of previewFiles.value) {
    const group = inferGroup(file.path);
    if (!groups[group]) {
      const meta = groupMeta[group] ?? { titleKey: group, icon: 'icon-[lucide--folder]' };
      groups[group] = {
        title: $t(`${T}.${meta.titleKey}`),
        key: `group-${group}`,
        icon: meta.icon,
        children: [],
      };
    }
    groups[group]!.children.push({
      title: file.path.split('/').pop() ?? file.path,
      key: file.path,
      isLeaf: true,
    });
  }

  return Object.values(groups);
});

const selectedFile = computed(() =>
  previewFiles.value.find((f) => f.path === selectedFileKey.value),
);


const lineCount = computed(() =>
  selectedFile.value?.content ? selectedFile.value.content.split('\n').length : 0,
);

function onTreeSelect(keys: (string | number)[]) {
  if (keys.length > 0 && typeof keys[0] === 'string' && !keys[0].startsWith('group-')) {
    selectedFileKey.value = keys[0];
  }
}

async function copyCode() {
  const content = activeTab.value === 'migration' ? migrationContent.value : selectedFile.value?.content;
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch {
    // clipboard not available
  }
}
</script>

<template>
  <Spin :spinning="loading">
    <div class="step-code-preview flex gap-4" style="min-height: 500px;">
      <!-- Left: File Tree -->
      <Card
        :bordered="false"
        class="w-64 shrink-0"
        size="small"
      >
        <template #title>
          <span class="flex items-center gap-1.5 text-sm">
            <span class="icon-[lucide--folder-tree] size-4" />
            {{ $t(`${T}.fileTree`) }}
            <Tag v-if="previewFiles.length > 0" size="small">
              {{ previewFiles.length }}
            </Tag>
          </span>
        </template>

        <Tree
          :selected-keys="selectedFileKey ? [selectedFileKey] : []"
          :tree-data="treeData"
          block-node
          default-expand-all
          @select="onTreeSelect"
        >
          <template #title="{ title, isLeaf }">
            <span class="flex items-center gap-1 text-xs">
              <span
                v-if="!isLeaf"
                class="icon-[lucide--folder] size-3.5 text-primary"
              />
              <span
                v-else
                class="icon-[lucide--file-code] size-3.5 opacity-50"
              />
              {{ title }}
            </span>
          </template>
        </Tree>
      </Card>

      <!-- Right: Code Viewer -->
      <Card :bordered="false" class="flex-1" size="small">
        <template #title>
          <Tabs
            v-model:activeKey="activeTab"
            size="small"
            type="card"
          >
            <Tabs.TabPane key="code" :tab="$t(`${T}.code`)" />
            <Tabs.TabPane key="migration" :tab="$t(`${T}.migration`)" />
          </Tabs>
        </template>

        <template #extra>
          <div class="flex items-center gap-2">
            <Tag v-if="selectedFile && activeTab === 'code'" color="blue">
              {{ inferLang(selectedFile.path) }}
            </Tag>
            <span v-if="activeTab === 'code' && selectedFile" class="text-muted-foreground text-xs">
              {{ lineCount }} {{ $t(`${T}.lines`, { count: lineCount }) }}
            </span>
            <Tooltip :title="copied ? $t(`${T}.copied`) : $t(`${T}.copyCode`)">
              <Button size="small" type="text" @click="copyCode">
                <template #icon>
                  <span :class="copied ? 'icon-[lucide--check]' : 'icon-[lucide--copy]'" class="size-3.5" />
                </template>
              </Button>
            </Tooltip>
          </div>
        </template>

        <!-- Error State -->
        <div v-if="error" class="py-8 text-center text-destructive">
          <span class="icon-[lucide--alert-circle] mb-2 block size-8 mx-auto" />
          <p class="text-sm">{{ error }}</p>
          <Button size="small" class="mt-2" @click="fetchPreview">
            {{ $t(`${T}.retry`) }}
          </Button>
        </div>

        <!-- Code Tab -->
        <template v-else-if="activeTab === 'code'">
          <div v-if="selectedFile" class="code-viewer">
            <div class="text-muted-foreground mb-2 flex items-center gap-1 text-xs">
              <span class="icon-[lucide--file-code] size-3" />
              {{ selectedFile.path }}
              <Tag v-if="selectedFile.operation === 'create'" color="green" size="small">new</Tag>
              <Tag v-else-if="selectedFile.operation === 'merge'" color="blue" size="small">merge</Tag>
              <Tag v-else-if="selectedFile.operation === 'conflict'" color="orange" size="small">conflict</Tag>
            </div>
            <pre class="bg-accent/50 overflow-auto rounded-lg border p-4 text-sm leading-relaxed"><code>{{ selectedFile.content }}</code></pre>
          </div>
          <Empty
            v-else
            :description="$t(`${T}.noFile`)"
            class="py-20"
          >
            <template #image>
              <span class="icon-[lucide--file-code] mx-auto block size-12 opacity-20" />
            </template>
          </Empty>
        </template>

        <!-- Migration Tab -->
        <template v-else-if="activeTab === 'migration'">
          <div v-if="migrationContent" class="code-viewer">
            <div class="text-muted-foreground mb-2 flex items-center gap-1 text-xs">
              <span class="icon-[lucide--database] size-3" />
              {{ migrationPath }}
              <Tag color="green" size="small">Alembic</Tag>
            </div>
            <pre class="bg-accent/50 overflow-auto rounded-lg border p-4 text-sm leading-relaxed"><code>{{ migrationContent }}</code></pre>
          </div>
          <Empty
            v-else
            :description="$t(`${T}.noMigration`)"
            class="py-20"
          >
            <template #image>
              <span class="icon-[lucide--database] mx-auto block size-12 opacity-20" />
            </template>
          </Empty>
        </template>
      </Card>
    </div>
  </Spin>
</template>
