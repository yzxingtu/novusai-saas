<script lang="ts" setup>
/**
 * 平台权限查看页面
 * 只读展示权限树结构
 */
import type { adminApi } from '#/api';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Spin, Tag, Tree } from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';

type PermissionNode = adminApi.PermissionNode;

// 权限树数据
const permissions = ref<PermissionNode[]>([]);
const loading = ref(false);
const expandedKeys = ref<number[]>([]);

/**
 * 加载权限树
 */
async function loadPermissions() {
  loading.value = true;
  try {
    permissions.value = await admin.getPermissionTreeApi();
    // 默认展开前两层
    expandedKeys.value = getExpandedKeys(permissions.value, 2);
  } catch {
    permissions.value = [];
  } finally {
    loading.value = false;
  }
}

/**
 * 获取默认展开的 keys
 */
function getExpandedKeys(nodes: PermissionNode[], level: number): number[] {
  if (level <= 0) return [];
  const keys: number[] = [];
  for (const node of nodes) {
    keys.push(node.id);
    if (node.children) {
      keys.push(...getExpandedKeys(node.children, level - 1));
    }
  }
  return keys;
}

/**
 * 转换权限树为 Tree 组件需要的格式
 */
function transformTreeData(nodes: PermissionNode[]): any[] {
  return nodes.map((node) => ({
    key: node.id,
    title: node.name,
    code: node.code,
    type: node.type,
    children: node.children ? transformTreeData(node.children) : undefined,
  }));
}

/**
 * 获取权限类型图标
 */
function getTypeIcon(type: string): string {
  switch (type) {
    case 'api': {
      return 'mdi:api';
    }
    case 'button': {
      return 'mdi:gesture-tap-button';
    }
    case 'menu': {
      return 'mdi:menu';
    }
    default: {
      return 'mdi:folder';
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
      return 'green';
    }
    case 'menu': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 获取权限类型文本
 */
function getTypeText(type: string): string {
  switch (type) {
    case 'api': {
      return $t('admin.system.permission.type.api');
    }
    case 'button': {
      return $t('admin.system.permission.type.button');
    }
    case 'menu': {
      return $t('admin.system.permission.type.menu');
    }
    default: {
      return type;
    }
  }
}

onMounted(() => {
  loadPermissions();
});
</script>

<template>
  <Page
    :description="$t('admin.system.permission.description')"
    :title="$t('admin.system.permission.list')"
  >
    <Card>
      <Spin :spinning="loading">
        <Empty
          v-if="!loading && permissions.length === 0"
          :description="$t('admin.system.permission.noData')"
        />
        <Tree
          v-else
          v-model:expanded-keys="expandedKeys"
          :tree-data="transformTreeData(permissions)"
          :selectable="false"
          block-node
        >
          <template #title="{ code, title, type }">
            <div class="flex items-center gap-2">
              <IconifyIcon :icon="getTypeIcon(type)" class="text-lg" />
              <span>{{ title }}</span>
              <Tag :color="getTypeColor(type)" class="ml-2">
                {{ getTypeText(type) }}
              </Tag>
              <span class="ml-2 text-xs text-gray-400">{{ code }}</span>
            </div>
          </template>
        </Tree>
      </Spin>
    </Card>
  </Page>
</template>
