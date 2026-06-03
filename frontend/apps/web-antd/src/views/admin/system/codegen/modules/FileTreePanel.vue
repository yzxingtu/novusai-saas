<script lang="ts" setup>
import type { TreeProps as AntTreeProps } from 'ant-design-vue';
import type { Key } from 'ant-design-vue/es/_util/type';

/**
 * 文件树面板 / File tree panel
 *
 * 支持问题摘要入口与多维过滤：
 * - 全部
 * - 冲突
 * - 已修改
 * - backend/frontend
 */
import type { PreviewFile } from '#/api/admin/codegen';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Tree } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'FileTreePanel' });

const props = withDefaults(
  defineProps<{
    conflicts?: Array<Record<string, string>>;
    files: PreviewFile[];
    selectedPath?: string;
  }>(),
  {
    selectedPath: '',
    conflicts: () => [],
  },
);

const emit = defineEmits<{
  select: [path: string];
}>();

type FilterMode = 'all' | 'backend' | 'conflicts' | 'frontend' | 'modified';

interface TreeNode {
  key: string;
  path: string;
  title: string;
  isLeaf: boolean;
  children?: TreeNode[];
  type?: string;
}

interface TreeEntry {
  children: TreeBranch;
  node: TreeNode;
}

type TreeBranch = Record<string, TreeEntry>;

const filterMode = ref<FilterMode>('all');

function normalizePath(path: string): string {
  return (path || '')
    .replaceAll('\\', '/')
    .replaceAll(/\/+/g, '/')
    .replace(/^\//, '')
    .replace(/\/$/, '');
}

function buildTree(files: PreviewFile[]): TreeNode[] {
  const fileMap = new Map<string, PreviewFile>();
  for (const file of files) {
    const normalizedPath = normalizePath(file.path);
    if (normalizedPath) fileMap.set(normalizedPath, file);
  }

  const root: TreeBranch = {};
  for (const file of files) {
    const normalizedPath = normalizePath(file.path);
    if (!normalizedPath) continue;
    const parts = normalizedPath.split('/').filter(Boolean);
    let current = root;

    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      if (!part) continue;
      const fullPath = parts.slice(0, index + 1).join('/');
      const isLeaf = index === parts.length - 1;
      if (!current[part]) {
        current[part] = {
          node: {
            key: fullPath,
            path: fullPath,
            title: part,
            isLeaf,
            type: isLeaf ? (fileMap.get(fullPath)?.type ?? '') : undefined,
          },
          children: {},
        };
      }
      if (!isLeaf) {
        current = current[part]!.children;
      }
    }
  }

  function toArray(branch: TreeBranch): TreeNode[] {
    return Object.entries(branch)
      .map(([, entry]) => {
        const node = entry.node;
        if (Object.keys(entry.children).length > 0) {
          node.children = toArray(entry.children);
        }
        return node;
      })
      .toSorted((left, right) => {
        if (left.isLeaf !== right.isLeaf) return left.isLeaf ? 1 : -1;
        return left.title.localeCompare(right.title);
      });
  }

  return toArray(root);
}

const conflictPathSet = computed(
  () =>
    new Set(
      props.conflicts
        .map((item) => normalizePath(String(item.path || '')))
        .filter(Boolean),
    ),
);

const createCount = computed(
  () => props.files.filter((file) => file.type === 'create').length,
);
const modifyCount = computed(
  () =>
    props.files.filter(
      (file) => file.type === 'modify' || file.type === 'append',
    ).length,
);

const filteredFiles = computed(() => {
  const conflicts = conflictPathSet.value;
  return props.files.filter((file) => {
    const normalizedPath = normalizePath(file.path);
    switch (filterMode.value) {
      case 'backend': {
        return normalizedPath.startsWith('backend/');
      }
      case 'conflicts': {
        return conflicts.has(normalizedPath);
      }
      case 'frontend': {
        return normalizedPath.startsWith('frontend/');
      }
      case 'modified': {
        return file.type === 'modify' || file.type === 'append';
      }
      default: {
        return true;
      }
    }
  });
});

const treeData = computed(() => buildTree(filteredFiles.value));

const filterOptions = computed<
  Array<{ count?: number; key: FilterMode; label: string }>
>(() => [
  { key: 'all', label: $t('admin.system.codegen.preview.filterAll') },
  {
    key: 'conflicts',
    label: $t('admin.system.codegen.preview.filterConflicts'),
    count: props.conflicts.length,
  },
  {
    key: 'modified',
    label: $t('admin.system.codegen.preview.filterModified'),
    count: modifyCount.value,
  },
  {
    key: 'backend',
    label: $t('admin.system.codegen.preview.filterBackend'),
    count: props.files.filter((file) =>
      normalizePath(file.path).startsWith('backend/'),
    ).length,
  },
  {
    key: 'frontend',
    label: $t('admin.system.codegen.preview.filterFrontend'),
    count: props.files.filter((file) =>
      normalizePath(file.path).startsWith('frontend/'),
    ).length,
  },
]);

function onSelect(
  _keys: Key[],
  info: Parameters<NonNullable<AntTreeProps['onSelect']>>[1],
) {
  const node = info?.node as Partial<TreeNode>;
  if (node?.isLeaf && (node.path ?? node.key)) {
    emit('select', node.path ?? node.key ?? '');
  }
}

function openProblemSummary() {
  emit('select', '');
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="rounded-2xl border border-border bg-muted/20 p-3">
      <Button block class="justify-start" @click="openProblemSummary">
        <IconifyIcon icon="lucide:shield-alert" class="mr-1 size-4" />
        {{ $t('admin.system.codegen.preview.problemSummary') }}
      </Button>
      <div class="mt-3 text-xs leading-5 text-muted-foreground">
        {{
          $t('admin.system.codegen.generate.fileCount', {
            total: props.files.length,
            create: createCount,
            modify: modifyCount,
          })
        }}
      </div>
    </div>

    <div class="flex flex-wrap gap-2">
      <Button
        v-for="item in filterOptions"
        :key="item.key"
        size="small"
        :type="filterMode === item.key ? 'primary' : 'default'"
        @click="filterMode = item.key"
      >
        {{ item.label }}
        <span v-if="typeof item.count === 'number'" class="ml-1 opacity-80">{{
          item.count
        }}</span>
      </Button>
    </div>

    <div class="min-h-0 rounded-2xl border border-border p-2">
      <div
        v-if="filteredFiles.length === 0"
        class="px-2 py-8 text-center text-sm text-muted-foreground"
      >
        {{ $t('admin.system.codegen.preview.noPreview') }}
      </div>

      <Tree
        v-else
        :tree-data="treeData"
        :selected-keys="(props.selectedPath ?? '') ? [props.selectedPath!] : []"
        :field-names="{ title: 'title', key: 'key', children: 'children' }"
        block-node
        show-line
        @select="onSelect"
      >
        <template #title="{ title, isLeaf, type, path }">
          <span
            class="-mx-1 inline-flex cursor-pointer items-center gap-1.5 rounded px-1 hover:bg-muted/60"
          >
            <IconifyIcon
              v-if="conflictPathSet.has(normalizePath(path))"
              icon="lucide:file-warning"
              class="size-3.5 text-amber-600"
            />
            <IconifyIcon
              v-else-if="type === 'create'"
              icon="lucide:file-plus"
              class="size-3.5 text-emerald-600"
            />
            <IconifyIcon
              v-else-if="type === 'modify' || type === 'append'"
              icon="lucide:file-pen"
              class="size-3.5 text-sky-600"
            />
            <IconifyIcon
              v-else-if="isLeaf"
              icon="lucide:file"
              class="size-3.5 text-muted-foreground"
            />
            <IconifyIcon
              v-else
              icon="lucide:folder"
              class="size-3.5 text-muted-foreground"
            />
            <span>{{ title }}</span>
          </span>
        </template>
      </Tree>
    </div>
  </div>
</template>
