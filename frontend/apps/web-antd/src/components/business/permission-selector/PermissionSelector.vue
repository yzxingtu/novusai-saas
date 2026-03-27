<script lang="ts" setup>
/**
 * PermissionSelector Component
 * 权限选择器组件
 *
 * Supports displaying inherited vs own permissions.
 * 支持显示继承权限和自有权限区分。
 * Reusable for both admin and tenant sides.
 * 可复用于 admin 和 tenant 两端。
 */
import type { TreeProps as AntTreeProps } from 'ant-design-vue';
import type { Key } from 'ant-design-vue/es/_util/type';

import type { AntTreeNode, PermissionNode } from './types';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Empty, Spin, Tag, Tooltip, Tree } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  getAllPermissionIds,
  getExpandedKeys,
  transformToAntTreeData,
} from './types';

// Props / 属性
const props = withDefaults(
  defineProps<{
    /** Default expanded level / 默认展开层级 */
    defaultExpandedLevel?: number;
    /** Inherited permission source mapping Map<permissionId, roleName> / 继承权限的来源映射 */
    inheritedFromMap?: Map<number, string>;
    /** Inherited permission ID list (shown as grey locked) / 继承的权限 ID 列表 */
    inheritedPermissionIds?: number[];
    /** Loading state / 加载状态 */
    loading?: boolean;
    /** Selected permission ID list (v-model) / 选中的权限 ID 列表 */
    modelValue?: number[];
    /** Permission tree data / 权限树数据 */
    permissions: PermissionNode[];
    /** Whether to show inherited badge / 是否显示继承标识 */
    showInheritedBadge?: boolean;
    /** Whether to show select all/deselect buttons / 是否显示全选/取消按钮 */
    showSelectAll?: boolean;
  }>(),
  {
    modelValue: () => [],
    inheritedPermissionIds: () => [],
    inheritedFromMap: () => new Map(),
    loading: false,
    showInheritedBadge: true,
    defaultExpandedLevel: 0,
    showSelectAll: true,
  },
);

// Emits / 事件
const emit = defineEmits<{
  change: [value: number[]];
  'update:modelValue': [value: number[]];
}>();

// Internal state / 内部状态
const expandedKeys = ref<Key[]>([]);
const checkedKeys = ref<number[]>([]);

// Key relations / 节点关系
const parentKeyMap = computed(() => {
  const map = new Map<number, null | number>();

  function walk(nodes: PermissionNode[], parentId: null | number = null) {
    for (const node of nodes) {
      map.set(node.id, parentId);
      if (node.children && node.children.length > 0) {
        walk(node.children, node.id);
      }
    }
  }

  walk(props.permissions);
  return map;
});

const descendantKeyMap = computed(() => {
  const map = new Map<number, number[]>();

  function collect(node: PermissionNode): number[] {
    const descendants: number[] = [];
    for (const child of node.children || []) {
      descendants.push(child.id, ...collect(child));
    }
    map.set(node.id, descendants);
    return descendants;
  }

  for (const node of props.permissions) {
    collect(node);
  }

  return map;
});

// Computed: inherited permission ID set / 继承权限 ID 集合
const inheritedIdSet = computed(() => new Set(props.inheritedPermissionIds));

// Computed: tree data / 树形数据
const treeData = computed(() =>
  transformToAntTreeData(
    props.permissions,
    inheritedIdSet.value,
    props.inheritedFromMap,
  ),
);

// Computed: all permission IDs / 所有权限 ID
const allPermissionIds = computed(() => getAllPermissionIds(props.permissions));

// Computed: selectable permission IDs (excluding inherited) / 可选权限 ID
const selectableIds = computed(() =>
  allPermissionIds.value.filter((id) => !inheritedIdSet.value.has(id)),
);

// Computed: whether all selected / 是否全选
const isAllSelected = computed(() => {
  if (selectableIds.value.length === 0) return false;
  return selectableIds.value.every((id) => checkedKeys.value.includes(id));
});

// Stats: total and selected count (excluding inherited) / 统计：总数与已选数量
const totalCount = computed(() => allPermissionIds.value.length);
const selectedCount = computed(() => checkedKeys.value.length);

// Watch props.modelValue changes (deep watch to ensure array updates) / 监听 props.modelValue 变化
watch(
  () => props.modelValue,
  (newVal) => {
    // Only update when value truly changes, avoid infinite loop / 只有当值真正变化时才更新
    const newKeys = [...newVal];
    if (JSON.stringify(checkedKeys.value) !== JSON.stringify(newKeys)) {
      checkedKeys.value = newKeys;
    }
  },
  { immediate: true, deep: true },
);

// Watch permission data changes, initialize expanded state / 监听权限数据变化，初始化展开状态
watch(
  () => [props.defaultExpandedLevel, props.permissions],
  () => {
    expandedKeys.value =
      props.permissions.length > 0 && props.defaultExpandedLevel > 0
        ? getExpandedKeys(props.permissions, props.defaultExpandedLevel)
        : [];
  },
  { immediate: true },
);

function getBranchKeys(targetKey: Key): Key[] {
  if (typeof targetKey !== 'number') {
    return [];
  }

  const branch: number[] = [];
  let current: null | number = targetKey;

  while (typeof current === 'number') {
    branch.push(current);
    current = parentKeyMap.value.get(current) ?? null;
  }

  return branch.toReversed();
}

/**
 * Keep only one expanded branch / 仅保留一个展开分支
 */
const handleExpand: NonNullable<AntTreeProps['onExpand']> = (
  nextExpandedKeys,
  info,
) => {
  const nodeKey = info.node.key;

  if (typeof nodeKey !== 'number') {
    expandedKeys.value = [...nextExpandedKeys];
    return;
  }

  if (info.expanded) {
    expandedKeys.value = getBranchKeys(nodeKey);
    return;
  }

  const removedKeys = new Set<number>([
    nodeKey,
    ...(descendantKeyMap.value.get(nodeKey) || []),
  ]);
  expandedKeys.value = expandedKeys.value.filter(
    (key) => typeof key !== 'number' || !removedKeys.has(key),
  );
};

/**
 * Handle check change / 处理选中变化
 */
function handleCheck(
  checked: Key[] | { checked: Key[]; halfChecked: Key[] },
  _info: unknown,
) {
  // Handle strict and non-strict mode / 处理严格模式和非严格模式
  const keys = Array.isArray(checked) ? checked : checked.checked;
  // Filter numeric keys and exclude inherited permissions / 过滤出数字类型的 key，并排除继承权限
  const numericKeys = keys
    .filter((key): key is number => typeof key === 'number')
    .filter((id) => !inheritedIdSet.value.has(id));

  checkedKeys.value = numericKeys;
  emit('update:modelValue', numericKeys);
  emit('change', numericKeys);
}

/**
 * Select all / 全选
 */
function selectAll() {
  const newKeys = [...new Set([...checkedKeys.value, ...selectableIds.value])];
  checkedKeys.value = newKeys;
  emit('update:modelValue', newKeys);
  emit('change', newKeys);
}

/**
 * Deselect all / 取消全选
 */
function deselectAll() {
  // Keep only inherited permissions / 只保留继承的权限
  const newKeys = checkedKeys.value.filter((id) =>
    inheritedIdSet.value.has(id),
  );
  checkedKeys.value = newKeys;
  emit('update:modelValue', newKeys);
  emit('change', newKeys);
}

/**
 * Toggle select all state / 切换全选状态
 */
function toggleSelectAll() {
  if (isAllSelected.value) {
    deselectAll();
  } else {
    selectAll();
  }
}

/**
 * Get node keys grouped by level / 获取按层级分组的节点 key
 */
function getKeysByLevel(nodes: AntTreeNode[], level = 0): Map<number, Key[]> {
  const levelMap = new Map<number, Key[]>();

  function traverse(nodeList: AntTreeNode[], currentLevel: number) {
    for (const node of nodeList) {
      if (!levelMap.has(currentLevel)) {
        levelMap.set(currentLevel, []);
      }
      levelMap.get(currentLevel)!.push(node.key);
      if (node.children && node.children.length > 0) {
        traverse(node.children, currentLevel + 1);
      }
    }
  }

  traverse(nodes, level);
  return levelMap;
}

/**
 * Expand all nodes (smooth transition) / 展开所有节点
 */
function expandAll() {
  const levelMap = getKeysByLevel(treeData.value);
  const levels = [...levelMap.keys()].toSorted((a, b) => a - b);

  // Expand layer by layer, 80ms interval / 逐层展开
  let currentKeys: Key[] = [];
  levels.forEach((level, index) => {
    setTimeout(() => {
      currentKeys = [...currentKeys, ...(levelMap.get(level) || [])];
      expandedKeys.value = [...currentKeys];
    }, index * 80);
  });
}

/**
 * Collapse all nodes (smooth transition) / 折叠所有节点
 */
function collapseAll() {
  const levelMap = getKeysByLevel(treeData.value);
  const levels = [...levelMap.keys()].toSorted((a, b) => b - a); // Start collapsing from deepest level / 从最深层开始折叠

  // Collapse layer by layer, 60ms interval / 逐层折叠
  let currentKeys = [...expandedKeys.value];
  levels.forEach((level, index) => {
    setTimeout(() => {
      const keysToRemove = new Set(levelMap.get(level) || []);
      currentKeys = currentKeys.filter((k) => !keysToRemove.has(k));
      expandedKeys.value = [...currentKeys];
    }, index * 60);
  });
}

// Expose methods / 暴露方法
defineExpose({
  expandAll,
  collapseAll,
  selectAll,
  deselectAll,
});
</script>

<template>
  <div class="permission-selector">
    <Spin :spinning="loading">
      <!-- Toolbar / 工具栏 -->
      <div
        v-if="showSelectAll && permissions.length > 0"
        class="mb-2 flex items-center justify-between"
      >
        <div class="flex items-center gap-3">
          <Button size="small" type="link" @click="toggleSelectAll">
            <IconifyIcon
              :icon="isAllSelected ? 'lucide:square-check' : 'lucide:square'"
              class="mr-1"
            />
            {{
              isAllSelected
                ? $t('shared.common.deselectAll')
                : $t('shared.common.selectAll')
            }}
          </Button>
          <span class="text-xs text-muted-foreground">
            {{
              $t('component.permissionSelector.selectedSummary', {
                selected: selectedCount,
                total: totalCount,
              })
            }}
          </span>
        </div>
        <div class="flex gap-2">
          <Button size="small" type="text" @click="expandAll">
            <IconifyIcon icon="lucide:unfold-vertical" class="mr-1" />
            {{ $t('shared.common.expandAll') }}
          </Button>
          <Button size="small" type="text" @click="collapseAll">
            <IconifyIcon icon="lucide:fold-vertical" class="mr-1" />
            {{ $t('shared.common.collapseAll') }}
          </Button>
        </div>
      </div>

      <Empty
        v-if="!loading && permissions.length === 0"
        :description="$t('shared.common.noData')"
      />

      <Tree
        v-else
        v-model:expanded-keys="expandedKeys"
        :checked-keys="checkedKeys"
        :tree-data="treeData as AntTreeProps['treeData']"
        checkable
        :selectable="false"
        :block-node="true"
        :check-strictly="false"
        @check="handleCheck"
        @expand="handleExpand"
      >
        <template #title="nodeData">
          <div class="permission-node flex items-center gap-2 py-0.5">
            <!-- Permission icon: prefer custom icon, fallback to type-based default / 权限图标 -->
            <IconifyIcon
              :icon="
                nodeData.icon
                  ? nodeData.icon
                  : nodeData.type === 'menu'
                    ? 'lucide:layout-grid'
                    : nodeData.type === 'button'
                      ? 'lucide:mouse-pointer-click'
                      : 'lucide:plug'
              "
              class="size-4 flex-shrink-0"
              :class="{
                'text-primary': nodeData.type === 'menu',
                'text-success': nodeData.type === 'button',
                'text-warning': nodeData.type === 'api',
                'opacity-50': nodeData.isInherited,
              }"
            />

            <!-- Permission name / 权限名称 -->
            <span
              :class="{
                'text-muted-foreground': nodeData.isInherited,
              }"
            >
              {{ nodeData.title }}
            </span>

            <!-- Permission code / 权限代码 -->
            <span
              class="font-mono text-xs"
              :class="{
                'text-muted-foreground/50': nodeData.isInherited,
                'text-muted-foreground': !nodeData.isInherited,
              }"
            >
              {{ nodeData.code }}
            </span>

            <!-- Inherited badge / 继承标识 -->
            <Tooltip
              v-if="showInheritedBadge && nodeData.isInherited"
              :title="
                nodeData.inheritedFrom
                  ? $t('component.permissionSelector.inheritedFrom', {
                      role: nodeData.inheritedFrom,
                    })
                  : $t('component.permissionSelector.inherited')
              "
            >
              <Tag color="default" class="!m-0 !ml-auto text-xs">
                <IconifyIcon icon="lucide:link" class="mr-1 size-3" />
                {{ $t('component.permissionSelector.inherited') }}
              </Tag>
            </Tooltip>
          </div>
        </template>
      </Tree>
    </Spin>
  </div>
</template>

<style lang="scss" scoped>
.permission-selector {
  :deep(.ant-tree) {
    background: transparent;

    .ant-tree-treenode {
      width: 100%;
      padding: 2px 0;

      &:hover {
        background-color: hsl(var(--accent));
      }
    }

    .ant-tree-node-content-wrapper {
      flex: 1;
      min-width: 0;

      &:hover {
        background-color: transparent;
      }
    }

    .ant-tree-checkbox-disabled {
      .ant-tree-checkbox-inner {
        background-color: hsl(var(--muted));
        border-color: hsl(var(--border));
      }

      &.ant-tree-checkbox-checked .ant-tree-checkbox-inner {
        background-color: hsl(var(--muted));
        border-color: hsl(var(--border));

        &::after {
          border-color: hsl(var(--muted-foreground));
        }
      }
    }
  }
}

.permission-node {
  min-height: 24px;
}
</style>
