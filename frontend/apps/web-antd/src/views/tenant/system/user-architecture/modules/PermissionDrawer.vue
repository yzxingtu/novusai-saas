<script lang="ts" setup>
/**
 * 用户角色权限分配抽屉 / User role permission assignment drawer
 * 加载权限树 + 勾选已分配权限 + 保存
 */
import type { TreeProps as AntTreeProps } from 'ant-design-vue';

import type { TenantPermissionNode } from '#/api/tenant/permission';
import type { TenantUserRoleInfo } from '#/api/tenant/tenant-user-roles';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Drawer,
  Empty,
  message,
  Skeleton,
  Space,
  Tag,
  Tree,
} from 'ant-design-vue';

import { getTenantPermissionTreeApi } from '#/api/tenant/permission';
import {
  assignTenantUserRolePermissionsApi,
  getTenantUserRoleDetailApi,
} from '#/api/tenant/tenant-user-roles';
import { $t } from '#/locales';

const props = defineProps<{
  open: boolean;
  role: null | TenantUserRoleInfo;
}>();

const emit = defineEmits<{
  saved: [];
  'update:open': [value: boolean];
}>();

// ============================================================
// State / 状态
// ============================================================

const loading = ref(false);
const saving = ref(false);
const permissionTree = ref<TreeNode[]>([]);
const checkedKeys = ref<number[]>([]);
const expandedKeys = ref<number[]>([]);
const halfCheckedKeys = ref<number[]>([]);
const parentKeyMap = ref<Map<number, null | number>>(new Map());
const descendantKeyMap = ref<Map<number, number[]>>(new Map());

// ============================================================
// Tree node type / 树节点类型
// ============================================================

interface TreeNode {
  key: number;
  title: string;
  code: string;
  type: string;
  icon?: string;
  children?: TreeNode[];
}

// ============================================================
// Computed / 计算属性
// ============================================================

const drawerTitle = computed(() => {
  if (!props.role) return $t('tenant.system.userRole.assignPermissions');
  return `${$t('tenant.system.userRole.assignPermissions')} - ${props.role.name}`;
});

// ============================================================
// Load data / 加载数据
// ============================================================

function transformToTreeNodes(nodes: TenantPermissionNode[]): TreeNode[] {
  return nodes.map((node) => ({
    key: node.id,
    title: node.name,
    code: node.code,
    type: node.type,
    icon: node.icon ?? undefined,
    children: node.children ? transformToTreeNodes(node.children) : undefined,
  }));
}

function getAllKeys(nodes: TreeNode[]): number[] {
  const keys: number[] = [];
  for (const node of nodes) {
    keys.push(node.key);
    if (node.children && node.children.length > 0) {
      keys.push(...getAllKeys(node.children));
    }
  }
  return keys;
}

function buildTreeRelations(nodes: TreeNode[], parentId: null | number = null) {
  for (const node of nodes) {
    parentKeyMap.value.set(node.key, parentId);
    const descendants: number[] = [];
    for (const child of node.children || []) {
      descendants.push(child.key);
      buildTreeRelations([child], node.key);
      descendants.push(...(descendantKeyMap.value.get(child.key) || []));
    }
    descendantKeyMap.value.set(node.key, descendants);
  }
}

function getBranchKeys(targetKey: number): number[] {
  const branch: number[] = [];
  let current: null | number = targetKey;

  while (typeof current === 'number') {
    branch.push(current);
    current = parentKeyMap.value.get(current) ?? null;
  }

  return branch.toReversed();
}

async function loadData() {
  if (!props.role) return;
  loading.value = true;
  try {
    const [tree, detail] = await Promise.all([
      getTenantPermissionTreeApi(),
      getTenantUserRoleDetailApi(props.role.id),
    ]);

    permissionTree.value = transformToTreeNodes(tree);
    expandedKeys.value = [];
    parentKeyMap.value = new Map();
    descendantKeyMap.value = new Map();
    buildTreeRelations(permissionTree.value);

    const permIds = detail.permissionIds || [];
    checkedKeys.value = filterLeafKeys(permissionTree.value, new Set(permIds));
  } catch {
    permissionTree.value = [];
    checkedKeys.value = [];
  } finally {
    loading.value = false;
  }
}

/**
 * 只返回叶子节点 ID（Ant Tree 的 checkStrictly=false 模式需要）
 */
function filterLeafKeys(nodes: TreeNode[], idSet: Set<number>): number[] {
  const result: number[] = [];
  for (const node of nodes) {
    if (!node.children || node.children.length === 0) {
      if (idSet.has(node.key)) {
        result.push(node.key);
      }
    } else {
      result.push(...filterLeafKeys(node.children, idSet));
    }
  }
  return result;
}

// ============================================================
// Actions / 操作
// ============================================================

function onCheck(
  checked:
    | (number | string)[]
    | { checked: (number | string)[]; halfChecked: (number | string)[] },
) {
  if (Array.isArray(checked)) {
    checkedKeys.value = checked.filter(
      (k): k is number => typeof k === 'number',
    );
    halfCheckedKeys.value = [];
  } else {
    checkedKeys.value = checked.checked.filter(
      (k): k is number => typeof k === 'number',
    );
    halfCheckedKeys.value = checked.halfChecked.filter(
      (k): k is number => typeof k === 'number',
    );
  }
}

async function onSave() {
  if (!props.role) return;
  saving.value = true;
  try {
    const allIds = [...checkedKeys.value, ...halfCheckedKeys.value];
    await assignTenantUserRolePermissionsApi(props.role.id, {
      permission_ids: allIds,
    });
    message.success($t('tenant.system.userRole.messages.permissionsSaved'));
    emit('saved');
    emit('update:open', false);
  } finally {
    saving.value = false;
  }
}

function onClose() {
  emit('update:open', false);
}

function onExpandAll() {
  expandedKeys.value = getAllKeys(permissionTree.value);
}

function onCollapseAll() {
  expandedKeys.value = [];
}

const onExpand: NonNullable<AntTreeProps['onExpand']> = (
  nextExpandedKeys,
  info,
) => {
  const nodeKey = info.node.key;

  if (typeof nodeKey !== 'number') {
    expandedKeys.value = nextExpandedKeys.filter(
      (key): key is number => typeof key === 'number',
    );
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
  expandedKeys.value = nextExpandedKeys.filter(
    (key): key is number => typeof key === 'number' && !removedKeys.has(key),
  );
};

// ============================================================
// Watch / 监听
// ============================================================

watch(
  () => props.open,
  (val) => {
    if (val && props.role) {
      loadData();
    }
  },
);

// ============================================================
// Permission type helpers / 权限类型辅助
// ============================================================

function getTypeIcon(type: string): string {
  switch (type) {
    case 'api': {
      return 'lucide:route';
    }
    case 'button': {
      return 'lucide:square';
    }
    case 'menu': {
      return 'lucide:menu';
    }
    case 'operation': {
      return 'lucide:mouse-pointer-click';
    }
    default: {
      return 'lucide:folder';
    }
  }
}

function getTypeColor(type: string): string {
  switch (type) {
    case 'api': {
      return 'orange';
    }
    case 'button': {
      return 'cyan';
    }
    case 'menu': {
      return 'blue';
    }
    case 'operation': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

function getTypeLabel(type: string): string {
  const key = `tenant.system.userRole.permissionTypes.${type}`;
  const label = $t(key);
  return label === key ? type : label;
}
</script>

<template>
  <Drawer
    :open="open"
    :title="drawerTitle"
    :width="520"
    :destroy-on-close="true"
    @close="onClose"
  >
    <template #extra>
      <Space>
        <Button size="small" @click="onExpandAll">
          {{ $t('tenant.system.organization.expandAll') }}
        </Button>
        <Button size="small" @click="onCollapseAll">
          {{ $t('tenant.system.organization.collapseAll') }}
        </Button>
      </Space>
    </template>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3 p-2">
      <Skeleton
        v-for="i in 6"
        :key="i"
        active
        :title="false"
        :paragraph="{ rows: 1, width: '80%' }"
        class="!mb-0"
      />
    </div>

    <!-- Empty -->
    <Empty
      v-else-if="permissionTree.length === 0"
      :description="$t('tenant.system.userRole.noPermissions')"
    />

    <!-- Permission Tree -->
    <Tree
      v-else
      v-model:expanded-keys="expandedKeys"
      :checked-keys="checkedKeys"
      :tree-data="permissionTree"
      checkable
      :selectable="false"
      block-node
      @check="onCheck"
      @expand="onExpand"
    >
      <template #title="{ code, icon, title, type }">
        <div class="flex items-center gap-1.5">
          <IconifyIcon
            :icon="icon || getTypeIcon(type)"
            class="flex-shrink-0 text-sm"
          />
          <span class="text-sm">{{ title }}</span>
          <Tag :color="getTypeColor(type)" size="small">
            {{ getTypeLabel(type) }}
          </Tag>
          <span class="text-xs text-muted-foreground">
            {{ code }}
          </span>
        </div>
      </template>
    </Tree>

    <!-- Footer -->
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="onClose">
          {{ $t('shared.common.cancel') }}
        </Button>
        <Button
          type="primary"
          :loading="saving"
          :disabled="loading"
          @click="onSave"
        >
          {{ $t('shared.common.save') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
