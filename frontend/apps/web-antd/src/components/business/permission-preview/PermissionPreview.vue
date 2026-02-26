<script lang="ts" setup>
/**
 * 权限预览 Popover 组件
 * 点击触发，显示节点已分配的权限树
 */
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Empty, Popover, Skeleton, Tag, Tree } from 'ant-design-vue';

import { adminApi as admin, tenantApi as tenant } from '#/api';
import { $t } from '#/locales';

/** 权限节点通用类型 */
interface PermissionNode {
  id: number;
  code: string;
  name: string;
  type: string;
  icon?: null | string;
  children?: PermissionNode[];
}

const props = defineProps<{
  /** API 前缀: admin 或 tenant */
  apiPrefix?: 'admin' | 'tenant';
  /** 节点 ID */
  nodeId: number;
  /** 权限数量 */
  permissionsCount: number;
}>();

const open = ref(false);
const loading = ref(false);
const permissionIdSet = ref<Set<number>>(new Set());
const permissionTree = ref<PermissionNode[]>([]);
const expandedKeys = ref<number[]>([]);

/**
 * 加载节点权限
 */
async function loadPermissions() {
  // 权限数为 0 时不需要加载
  if (props.permissionsCount === 0) return;
  // 已加载过
  if (permissionIdSet.value.size > 0) return;

  loading.value = true;
  try {
    let permIds: number[] = [];

    if (props.apiPrefix === 'tenant') {
      // 租户端 API
      const detail = await tenant.getTenantRoleDetailApi(props.nodeId);
      // 优先使用 permissionIds，否则从 permissions 提取
      permIds =
        detail.permissionIds || detail.permissions?.map((p) => p.id) || [];
      permissionTree.value = await tenant.getTenantPermissionTreeApi();
    } else {
      // 平台端 API
      const detail = await admin.getRoleDetailApi(props.nodeId);
      permIds =
        detail.permissionIds || detail.permissions?.map((p) => p.id) || [];
      permissionTree.value = await admin.getPermissionTreeApi();
    }

    permissionIdSet.value = new Set(permIds);

    // 默认展开所有节点
    expandedKeys.value = getAllKeys(permissionTree.value);
  } catch (error) {
    console.error('Load permissions error:', error);
    permissionIdSet.value = new Set();
    permissionTree.value = [];
  } finally {
    loading.value = false;
  }
}

/**
 * 获取所有节点 keys
 */
function getAllKeys(nodes: PermissionNode[]): number[] {
  const keys: number[] = [];
  for (const node of nodes) {
    keys.push(node.id);
    if (node.children && node.children.length > 0) {
      keys.push(...getAllKeys(node.children));
    }
  }
  return keys;
}

/**
 * 过滤权限树，只保留已分配的权限及其父节点
 */
interface FilteredPermNode {
  key: number;
  title: string;
  code: string;
  type: string;
  icon?: string;
  hasPermission: boolean;
  children?: FilteredPermNode[];
}

function filterPermissionTree(nodes: PermissionNode[]): FilteredPermNode[] {
  const result: FilteredPermNode[] = [];
  for (const node of nodes) {
    const children = node.children ? filterPermissionTree(node.children) : [];
    const hasPermission = permissionIdSet.value.has(node.id);
    const hasChildWithPermission = children.length > 0;

    if (hasPermission || hasChildWithPermission) {
      result.push({
        key: node.id,
        title: node.name,
        code: node.code,
        type: node.type,
        icon: node.icon ?? undefined,
        hasPermission,
        children: children.length > 0 ? children : undefined,
      });
    }
  }
  return result;
}

const filteredTreeData = computed(() =>
  filterPermissionTree(permissionTree.value),
);

/**
 * 获取权限类型图标
 */
function getTypeIcon(type: string): string {
  switch (type) {
    case 'api': {
      return 'mdi:api';
    }
    case 'button': {
      return 'lucide:square';
    }
    case 'menu': {
      return 'lucide:layout-dashboard';
    }
    case 'operation': {
      return 'lucide:mouse-pointer-click';
    }
    default: {
      return 'lucide:folder';
    }
  }
}

/**
 * 获取权限类型颜色
 */
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

function handleOpenChange(visible: boolean) {
  open.value = visible;
  if (visible) {
    loadPermissions();
  }
}

// 当 nodeId 变化时重置状态
watch(
  () => props.nodeId,
  () => {
    permissionIdSet.value = new Set();
    permissionTree.value = [];
  },
);
</script>

<template>
  <Popover
    :open="open"
    trigger="click"
    placement="bottomLeft"
    overlay-class-name="permission-preview-popover"
    @open-change="handleOpenChange"
  >
    <template #content>
      <div class="max-h-[400px] min-w-[280px] max-w-[480px] overflow-auto">
        <!-- 骨架加载 -->
        <div v-if="loading" class="space-y-2 p-1">
          <Skeleton
            v-for="i in 4"
            :key="i"
            active
            :title="false"
            :paragraph="{ rows: 1, width: '100%' }"
            class="!mb-0"
          />
        </div>
        <!-- 空状态 -->
        <Empty
          v-else-if="filteredTreeData.length === 0"
          :description="$t('admin.system.role.noPermissions')"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
        />
        <!-- 权限树 -->
        <Tree
          v-else
          v-model:expanded-keys="expandedKeys"
          :tree-data="filteredTreeData"
          :selectable="false"
          block-node
          default-expand-all
        >
          <template #title="{ code, hasPermission, icon, title, type }">
            <div
              class="flex items-center gap-1.5 whitespace-nowrap"
              :class="{ 'opacity-50': !hasPermission }"
            >
              <IconifyIcon
                :icon="icon || getTypeIcon(type)"
                class="flex-shrink-0 text-sm"
              />
              <span class="text-sm">{{ title }}</span>
              <Tag
                v-if="hasPermission"
                :color="getTypeColor(type)"
                size="small"
              >
                {{ type }}
              </Tag>
              <span v-if="hasPermission" class="text-xs text-muted-foreground">
                {{ code }}
              </span>
            </div>
          </template>
        </Tree>
      </div>
    </template>
    <span
      class="inline-flex cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-accent"
    >
      <IconifyIcon
        icon="lucide:shield-check"
        class="h-3.5 w-3.5 text-primary"
      />
      <span>{{ permissionsCount ?? 0 }}</span>
      <span>{{ $t('admin.system.organization.permissionsUnit') }}</span>
    </span>
  </Popover>
</template>

<style>
.permission-preview-popover .ant-popover-inner {
  padding: 12px;
}
</style>
