<script lang="ts" setup>
import type { RoleTreeNodeData } from './types';

/**
 * 角色树节点组件（递归）
 * 通用组件，支持 admin 和 tenant 两端
 */
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Switch, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

const props = withDefaults(
  defineProps<{
    expandedIds: Set<number>;
    getLevelColor: (level: number) => { badge: string; bar: string };
    /** i18n 前缀，用于区分 admin/tenant */
    i18nPrefix?: 'admin' | 'tenant';
    isExpanded: (id: number) => boolean;
    level: number;
    node: RoleTreeNodeData;
  }>(),
  {
    i18nPrefix: 'admin',
  },
);

const emit = defineEmits<{
  addChild: [row: RoleTreeNodeData];
  delete: [row: RoleTreeNodeData];
  edit: [row: RoleTreeNodeData];
  toggle: [id: number];
  toggleStatus: [row: RoleTreeNodeData, isActive: boolean];
}>();

const hasChildren = computed(
  () => props.node.children && props.node.children.length > 0,
);
const expanded = computed(() => props.isExpanded(props.node.id));
const colors = computed(() => props.getLevelColor(props.level));
</script>

<script lang="ts">
// 递归组件需要显式命名
export default {
  name: 'RoleTreeNode',
};
</script>

<template>
  <div class="tree-node relative">
    <!-- 树形连接线 -->
    <div
      v-if="level > 0"
      class="absolute left-0 top-0 h-full"
      :style="{ width: `${level * 28}px` }"
    >
      <!-- 水平连接线 -->
      <div
        class="absolute top-1/2 h-px bg-border/60"
        :style="{ left: `${(level - 1) * 28 + 14}px`, width: '14px' }"
      ></div>
      <!-- 垂直连接线 -->
      <div
        class="absolute w-px bg-border/60"
        :style="{ left: `${(level - 1) * 28 + 14}px`, top: 0, height: '50%' }"
      ></div>
    </div>

    <!-- 节点卡片 -->
    <div
      class="group relative mb-1 flex items-center gap-4 rounded-xl border border-transparent bg-card/50 px-4 py-3 transition-[border-color,box-shadow] duration-200 hover:border-primary/20 hover:shadow-md"
      :style="{ marginLeft: `${level * 28}px` }"
    >
      <!-- 左侧装饰条 -->
      <div
        class="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full transition-[height] duration-200 group-hover:h-10"
        :class="colors.bar"
      ></div>

      <!-- 展开按钮 -->
      <button
        class="flex size-7 flex-shrink-0 items-center justify-center rounded-lg transition-transform duration-150"
        :class="
          hasChildren
            ? 'cursor-pointer bg-accent/50 text-muted-foreground hover:scale-110 hover:bg-primary/10 hover:text-primary'
            : 'opacity-0'
        "
        @click.stop="hasChildren && emit('toggle', node.id)"
      >
        <IconifyIcon
          :icon="expanded ? 'lucide:chevron-down' : 'lucide:chevron-right'"
          class="size-4 transition-transform duration-150"
          :class="{ 'rotate-0': expanded }"
        />
      </button>

      <!-- 角色信息 -->
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-3">
          <!-- 角色名称 -->
          <span class="text-sm font-semibold text-foreground">{{
            node.name
          }}</span>
          <!-- 层级徽章 -->
          <span
            v-if="level > 0"
            class="inline-flex size-5 items-center justify-center rounded-md text-[10px] font-bold shadow-sm"
            :class="colors.badge"
          >
            L{{ level }}
          </span>
          <!-- 角色编码 -->
          <code
            class="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
          >
            {{ node.code }}
          </code>
        </div>
        <p
          v-if="node.description"
          class="mt-1 truncate text-xs text-muted-foreground/80"
        >
          {{ node.description }}
        </p>
      </div>

      <!-- 权限数量 -->
      <div class="flex-shrink-0">
        <div
          v-if="(node.permissionsCount ?? 0) > 0"
          class="flex items-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
        >
          <IconifyIcon icon="lucide:key-round" class="size-3.5" />
          <span>{{ node.permissionsCount }}</span>
        </div>
        <div
          v-else
          class="rounded-lg bg-muted/50 px-2.5 py-1 text-xs text-muted-foreground"
        >
          {{ $t('shared.common.noPermissions') }}
        </div>
      </div>

      <!-- 状态开关 -->
      <div class="flex-shrink-0" @click.stop>
        <Tooltip
          :title="
            node.isActive
              ? $t('shared.common.clickToDisable')
              : $t('shared.common.clickToEnable')
          "
        >
          <Switch
            :checked="node.isActive"
            size="small"
            :checked-children="$t('shared.common.enabled')"
            :un-checked-children="$t('shared.common.disabled')"
            @change="(checked) => emit('toggleStatus', node, Boolean(checked))"
          />
        </Tooltip>
      </div>

      <!-- 时间 -->
      <div
        class="w-32 flex-shrink-0 text-right text-xs text-muted-foreground/70"
      >
        {{ node.createdAt ? formatDate(node.createdAt) : '-' }}
      </div>

      <!-- 操作按钮 -->
      <div
        class="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      >
        <Tooltip :title="$t('shared.common.addChild')">
          <Button
            type="text"
            size="small"
            class="!size-8 !rounded-lg hover:!bg-primary/10"
            @click.stop="emit('addChild', node)"
          >
            <IconifyIcon icon="lucide:plus" class="size-4 text-primary" />
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.edit')">
          <Button
            type="text"
            size="small"
            class="!size-8 !rounded-lg hover:!bg-primary/10"
            @click.stop="emit('edit', node)"
          >
            <IconifyIcon icon="lucide:pencil" class="size-4 text-primary" />
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.delete')">
          <Button
            type="text"
            size="small"
            class="!size-8 !rounded-lg hover:!bg-destructive/10"
            @click.stop="emit('delete', node)"
          >
            <IconifyIcon
              icon="lucide:trash-2"
              class="size-4 text-destructive"
            />
          </Button>
        </Tooltip>
      </div>
    </div>

    <!-- 子节点 (带动画) -->
    <Transition name="tree-slide">
      <div v-if="hasChildren && expanded" class="tree-children relative">
        <!-- 子节点之间的垂直连接线 -->
        <div
          class="absolute w-px bg-border/60"
          :style="{ left: `${level * 28 + 14}px`, top: 0, bottom: '50%' }"
        ></div>
        <RoleTreeNode
          v-for="child in node.children"
          :key="child.id"
          :node="child"
          :level="level + 1"
          :expanded-ids="expandedIds"
          :get-level-color="getLevelColor"
          :is-expanded="isExpanded"
          :i18n-prefix="i18nPrefix"
          @toggle="(id) => emit('toggle', id)"
          @edit="(row) => emit('edit', row)"
          @add-child="(row) => emit('addChild', row)"
          @delete="(row) => emit('delete', row)"
          @toggle-status="
            (row, isActive) => emit('toggleStatus', row, isActive)
          "
        />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* 展开/收起过渡动画 - 只过渡必要属性 */
.tree-slide-enter-active,
.tree-slide-leave-active {
  overflow: hidden;
  transition:
    opacity 0.25s ease-out,
    max-height 0.25s ease-out,
    transform 0.25s ease-out;
}

.tree-slide-enter-from {
  max-height: 0;
  opacity: 0;
  transform: translateX(-12px);
}

.tree-slide-enter-to {
  max-height: 2000px;
  opacity: 1;
  transform: translateX(0);
}

.tree-slide-leave-from {
  max-height: 2000px;
  opacity: 1;
  transform: translateX(0);
}

.tree-slide-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateX(-12px);
}
</style>
