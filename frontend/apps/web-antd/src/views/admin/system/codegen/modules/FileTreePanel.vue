<script lang="ts" setup>
/**
 * 文件树面板 / File tree panel
 *
 * 树形展示生成文件列表，文件状态标记，点击 emit 选中
 */
import type { PreviewFile } from '#/api/admin/codegen';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { Tree } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'FileTreePanel' });

const props = withDefaults(
  defineProps<{
    files: PreviewFile[];
    selectedPath?: string;
  }>(),
  { selectedPath: '' },
);

const emit = defineEmits<{
  select: [path: string];
}>();

interface TreeNode {
  key: string;
  path: string;
  title: string;
  isLeaf: boolean;
  children?: TreeNode[];
  type?: string;
}

function normalizePath(p: string): string {
  return (p || '').replace(/\\/g, '/').replace(/\/+/g, '/').replace(/^\//, '').replace(/\/$/, '');
}

function buildTree(files: PreviewFile[]): TreeNode[] {
  const fileMap = new Map<string, PreviewFile>();
  for (const f of files) {
    const np = normalizePath(f.path);
    if (np) fileMap.set(np, f);
  }
  const root: Record<string, { node: TreeNode; children: Record<string, unknown> }> = {};
  for (const f of files) {
    const normalizedPath = normalizePath(f.path);
    if (!normalizedPath) continue;
    const parts = normalizedPath.split('/').filter((p) => p.length > 0);
    let curr = root;
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      const fullPath = parts.slice(0, i + 1).join('/');
      const isLeaf = i === parts.length - 1;
      if (!curr[p]) {
        const node: TreeNode = {
          key: fullPath,
          path: fullPath,
          title: p,
          isLeaf,
          type: isLeaf ? fileMap.get(fullPath)?.type ?? '' : undefined,
        };
        curr[p] = {
          node,
          children: {},
        };
      }
      if (!isLeaf) {
        const entry = curr[p] as { node: TreeNode; children: Record<string, unknown> };
        if (entry.node.isLeaf) {
          entry.node.isLeaf = false;
          entry.node.type = undefined;
        }
        curr = entry.children as Record<string, { node: TreeNode; children: Record<string, unknown> }>;
      }
    }
  }
  function toArray(obj: Record<string, { node: TreeNode; children: Record<string, unknown> }>): TreeNode[] {
    return Object.entries(obj)
      .map(([, v]) => {
        const n = v.node;
        const children = v.children as Record<string, { node: TreeNode; children: Record<string, unknown> }>;
        if (Object.keys(children).length > 0) {
          n.children = toArray(children);
        }
        return n;
      })
      .sort((a, b) => {
        if (a.isLeaf !== b.isLeaf) return a.isLeaf ? 1 : -1;
        return a.title.localeCompare(b.title);
      });
  }
  return toArray(root);
}

const treeData = computed(() => buildTree(props.files));

const createCount = computed(
  () => props.files.filter((f) => f.type === 'create').length,
);
const modifyCount = computed(
  () => props.files.filter((f) => f.type === 'modify' || f.type === 'append').length,
);

function onSelect(
  _keys: string[],
  info: { node: { key?: string; path?: string; isLeaf?: boolean; type?: string } },
) {
  const node = info?.node;
  if (node?.isLeaf && (node.path ?? node.key)) {
    emit('select', node.path ?? node.key ?? '');
  }
}
</script>

<template>
  <div class="flex flex-col">
    <div class="text-muted-foreground mb-2 text-xs">
      {{ $t('admin.system.codegen.generate.fileCount', {
        total: props.files.length,
        create: createCount,
        modify: modifyCount,
      }) }}
    </div>
    <Tree
      :tree-data="treeData"
      :selected-keys="(props.selectedPath ?? '') ? [props.selectedPath!] : []"
      :field-names="{ title: 'title', key: 'key', children: 'children' }"
      block-node
      show-line
      @select="onSelect"
    >
      <template #title="{ title, path, isLeaf, type }">
        <span
          class="inline-flex items-center gap-1.5 cursor-pointer hover:bg-muted/50 rounded px-1 -mx-1"
        >
          <IconifyIcon
            v-if="type === 'create'"
            icon="lucide:file-plus"
            class="size-3.5 text-green-600"
          />
          <IconifyIcon
            v-else-if="type === 'modify' || type === 'append'"
            icon="lucide:file-pen"
            class="size-3.5 text-amber-600"
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
</template>
