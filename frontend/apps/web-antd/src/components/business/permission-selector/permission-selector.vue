<script lang="ts" setup>
/**
 * PermissionSelector 权限选择器组件
 * 支持显示继承权限和自有权限区分
 * 可复用于 admin 和 tenant 两端
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

// Props
const props = withDefaults(
  defineProps<{
    /** 默认展开层级 */
    defaultExpandedLevel?: number;
    /** 继承权限的来源映射 Map<permissionId, roleName> */
    inheritedFromMap?: Map<number, string>;
    /** 继承的权限 ID 列表（灰色锁定显示） */
    inheritedPermissionIds?: number[];
    /** 加载状态 */
    loading?: boolean;
    /** 选中的权限 ID 列表（v-model） */
    modelValue?: number[];
    /** 权限树数据 */
    permissions: PermissionNode[];
    /** 是否显示继承标识 */
    showInheritedBadge?: boolean;
    /** 是否显示全选/取消按钮 */
    showSelectAll?: boolean;
  }>(),
  {
    modelValue: () => [],
    inheritedPermissionIds: () => [],
    inheritedFromMap: () => new Map(),
    loading: false,
    showInheritedBadge: true,
    defaultExpandedLevel: 2,
    showSelectAll: true,
  },
);

// Emits
const emit = defineEmits<{
  change: [value: number[]];
  'update:modelValue': [value: number[]];
}>();

// 内部状态
const expandedKeys = ref<Key[]>([]);
const checkedKeys = ref<number[]>([]);

// 计算属性：继承权限 ID 集合
const inheritedIdSet = computed(() => new Set(props.inheritedPermissionIds));

// 计算属性：树形数据
const treeData = computed(() =>
  transformToAntTreeData(
    props.permissions,
    inheritedIdSet.value,
    props.inheritedFromMap,
  ),
);

// 计算属性：所有权限 ID
const allPermissionIds = computed(() => getAllPermissionIds(props.permissions));

// 计算属性：可选权限 ID（排除继承权限）
const selectableIds = computed(() =>
  allPermissionIds.value.filter((id) => !inheritedIdSet.value.has(id)),
);

// 计算属性：是否全选
const isAllSelected = computed(() => {
  if (selectableIds.value.length === 0) return false;
  return selectableIds.value.every((id) => checkedKeys.value.includes(id));
});

// 统计：总数与已选数量（不含继承）
const totalCount = computed(() => allPermissionIds.value.length);
const selectedCount = computed(() => checkedKeys.value.length);

// 监听 props.modelValue 变化（深度监听以确保数组变化时更新）
watch(
  () => props.modelValue,
  (newVal) => {
    // 只有当值真正变化时才更新，避免无限循环
    const newKeys = [...newVal];
    if (JSON.stringify(checkedKeys.value) !== JSON.stringify(newKeys)) {
      checkedKeys.value = newKeys;
    }
  },
  { immediate: true, deep: true },
);

// 监听权限数据变化，初始化展开状态
watch(
  () => props.permissions,
  () => {
    if (props.permissions.length > 0 && expandedKeys.value.length === 0) {
      expandedKeys.value = getExpandedKeys(
        props.permissions,
        props.defaultExpandedLevel,
      );
    }
  },
  { immediate: true },
);

/**
 * 处理选中变化
 */
function handleCheck(
  checked: Key[] | { checked: Key[]; halfChecked: Key[] },
  _info: any,
) {
  // 处理严格模式和非严格模式
  const keys = Array.isArray(checked) ? checked : checked.checked;
  // 过滤出数字类型的 key，并排除继承权限
  const numericKeys = keys
    .filter((key): key is number => typeof key === 'number')
    .filter((id) => !inheritedIdSet.value.has(id));

  checkedKeys.value = numericKeys;
  emit('update:modelValue', numericKeys);
  emit('change', numericKeys);
}

/**
 * 全选
 */
function selectAll() {
  const newKeys = [...new Set([...checkedKeys.value, ...selectableIds.value])];
  checkedKeys.value = newKeys;
  emit('update:modelValue', newKeys);
  emit('change', newKeys);
}

/**
 * 取消全选
 */
function deselectAll() {
  // 只保留继承的权限
  const newKeys = checkedKeys.value.filter((id) =>
    inheritedIdSet.value.has(id),
  );
  checkedKeys.value = newKeys;
  emit('update:modelValue', newKeys);
  emit('change', newKeys);
}

/**
 * 切换全选状态
 */
function toggleSelectAll() {
  if (isAllSelected.value) {
    deselectAll();
  } else {
    selectAll();
  }
}

/**
 * 获取按层级分组的节点 key
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
 * 展开所有节点（平滑过渡）
 */
function expandAll() {
  const levelMap = getKeysByLevel(treeData.value);
  const levels = [...levelMap.keys()].toSorted((a, b) => a - b);

  // 逐层展开，每层间隔 80ms
  let currentKeys: Key[] = [];
  levels.forEach((level, index) => {
    setTimeout(() => {
      currentKeys = [...currentKeys, ...(levelMap.get(level) || [])];
      expandedKeys.value = [...currentKeys];
    }, index * 80);
  });
}

/**
 * 折叠所有节点（平滑过渡）
 */
function collapseAll() {
  const levelMap = getKeysByLevel(treeData.value);
  const levels = [...levelMap.keys()].toSorted((a, b) => b - a); // 从最深层开始折叠

  // 逐层折叠，每层间隔 60ms
  let currentKeys = [...expandedKeys.value];
  levels.forEach((level, index) => {
    setTimeout(() => {
      const keysToRemove = new Set(levelMap.get(level) || []);
      currentKeys = currentKeys.filter((k) => !keysToRemove.has(k));
      expandedKeys.value = [...currentKeys];
    }, index * 60);
  });
}

// 暴露方法
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
      <!-- 工具栏 -->
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
      >
        <template #title="nodeData">
          <div class="permission-node flex items-center gap-2 py-0.5">
            <!-- 权限图标：优先使用自定义图标，否则根据类型显示默认图标 -->
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

            <!-- 权限名称 -->
            <span
              :class="{
                'text-muted-foreground': nodeData.isInherited,
              }"
            >
              {{ nodeData.title }}
            </span>

            <!-- 权限代码 -->
            <span
              class="font-mono text-xs"
              :class="{
                'text-muted-foreground/50': nodeData.isInherited,
                'text-muted-foreground': !nodeData.isInherited,
              }"
            >
              {{ nodeData.code }}
            </span>

            <!-- 继承标识 -->
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
