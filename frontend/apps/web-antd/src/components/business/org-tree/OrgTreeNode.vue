<script lang="ts" setup>
import type { OrgTreeNodeData } from './types';

/**
 * 组织架构树节点组件（递归）
 * 支持 department/position/role 三种节点类型
 */
import type { OrgNodeType } from '#/api/admin/organization';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Spin, Tag, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { getLevelColor } from '#/utils/common';

import { NODE_TYPE_CONFIG } from './types';

const props = withDefaults(
  defineProps<{
    expandedIds: Set<number>;
    i18nPrefix?: 'admin' | 'tenant';
    isExpanded: (id: number) => boolean;
    level: number;
    node: OrgTreeNodeData;
    selectedId?: null | number;
  }>(),
  {
    selectedId: null,
    i18nPrefix: 'admin',
  },
);

const emit = defineEmits<{
  addChild: [node: OrgTreeNodeData, type: OrgNodeType];
  contextmenu: [event: MouseEvent, node: OrgTreeNodeData];
  delete: [node: OrgTreeNodeData];
  edit: [node: OrgTreeNodeData];
  select: [node: OrgTreeNodeData];
  toggle: [id: number];
}>();

// 计算属性
const hasChildren = computed(
  () => props.node.hasChildren || props.node.children.length > 0,
);
const expanded = computed(() => props.isExpanded(props.node.id));
const isSelected = computed(() => props.selectedId === props.node.id);
const colors = computed(() => getLevelColor(props.level));
const typeConfig = computed(
  () => NODE_TYPE_CONFIG[props.node.type] || NODE_TYPE_CONFIG.role,
);

/**
 * 处理节点点击
 */
function handleClick() {
  emit('select', props.node);
}

/**
 * 处理右键菜单
 */
function handleContextMenu(event: MouseEvent) {
  event.preventDefault();
  emit('contextmenu', event, props.node);
}
</script>

<script lang="ts">
// 递归组件需要显式命名
export default {
  name: 'OrgTreeNode',
};
</script>

<template>
  <div class="org-tree-node relative">
    <!-- 树形连接线 -->
    <div
      v-if="level > 0"
      class="absolute left-0 top-0 h-full"
      :style="{ width: `${level * 24}px` }"
    >
      <!-- 水平连接线 -->
      <div
        class="absolute top-1/2 h-px bg-border/40"
        :style="{ left: `${(level - 1) * 24 + 12}px`, width: '12px' }"
      ></div>
      <!-- 垂直连接线 -->
      <div
        class="absolute w-px bg-border/40"
        :style="{ left: `${(level - 1) * 24 + 12}px`, top: 0, height: '50%' }"
      ></div>
    </div>

    <!-- 节点卡片 -->
    <div
      class="group relative mb-1 flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-all duration-200"
      :class="[
        isSelected
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-transparent bg-card/50 hover:border-primary/20 hover:shadow-sm',
      ]"
      :style="{ marginLeft: `${level * 24}px` }"
      @click="handleClick"
      @contextmenu="handleContextMenu"
    >
      <!-- 左侧装饰条 -->
      <div
        class="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full transition-[height] duration-200 group-hover:h-8"
        :class="colors.bar"
      ></div>

      <!-- 展开按钮 -->
      <button
        class="flex size-6 flex-shrink-0 items-center justify-center rounded transition-all duration-150"
        :class="
          hasChildren
            ? 'cursor-pointer bg-accent/50 text-muted-foreground hover:bg-primary/10 hover:text-primary'
            : 'opacity-0'
        "
        @click.stop="hasChildren && emit('toggle', node.id)"
      >
        <Spin v-if="node.loading" size="small" />
        <IconifyIcon
          v-else
          :icon="expanded ? 'lucide:chevron-down' : 'lucide:chevron-right'"
          class="size-3.5 transition-transform duration-150"
        />
      </button>

      <!-- 节点类型图标 -->
      <div
        class="flex size-7 flex-shrink-0 items-center justify-center rounded bg-primary/10 text-primary"
      >
        <IconifyIcon :icon="typeConfig.icon" class="size-4" />
      </div>

      <!-- 节点信息 -->
      <div class="min-w-0 flex-1 overflow-hidden">
        <div class="flex items-center gap-1.5">
          <!-- 节点名称 -->
          <Tooltip :title="node.name" placement="topLeft">
            <span class="truncate text-sm font-medium text-foreground">{{
              node.name
            }}</span>
          </Tooltip>
          <!-- 节点类型标签 -->
          <Tag
            class="!m-0 flex-shrink-0 !border-primary/30 !bg-primary/10 !px-1.5 !py-0.5 !text-[10px] !leading-none !text-primary"
          >
            {{ $t(`${i18nPrefix}.system.${typeConfig.label}`) }}
          </Tag>
          <!-- 层级徽章 -->
          <span
            v-if="level > 0"
            class="inline-flex size-4 flex-shrink-0 items-center justify-center rounded text-[9px] font-bold"
            :class="colors.badge"
          >
            L{{ level }}
          </span>
        </div>
        <Tooltip
          v-if="node.description"
          :title="node.description"
          placement="topLeft"
        >
          <p class="mt-0.5 truncate text-xs text-muted-foreground/80">
            {{ node.description }}
          </p>
        </Tooltip>
      </div>

      <!-- 成员数量 -->
      <Tooltip
        v-if="node.allowMembers"
        :title="$t(`${i18nPrefix}.system.organization.memberCount`)"
      >
        <div
          class="flex flex-shrink-0 items-center gap-1 text-xs text-muted-foreground"
        >
          <IconifyIcon icon="lucide:users" class="size-3.5" />
          <span>{{ node.memberCount || 0 }}</span>
        </div>
      </Tooltip>

      <!-- 权限数量 -->
      <Tooltip
        :title="$t(`${i18nPrefix}.system.organization.permissionsCount`)"
      >
        <div
          class="flex flex-shrink-0 items-center gap-1 text-xs text-muted-foreground"
        >
          <IconifyIcon icon="lucide:shield-check" class="size-3.5" />
          <span>{{ node.permissionsCount ?? 0 }}</span>
        </div>
      </Tooltip>

      <!-- 负责人 -->
      <div v-if="node.leader" class="flex flex-shrink-0 items-center gap-1.5">
        <Tooltip :title="$t(`${i18nPrefix}.system.organization.leader`)">
          <div
            class="flex items-center gap-1 rounded-lg bg-warning/10 px-2 py-1 text-xs text-warning"
          >
            <IconifyIcon icon="lucide:crown" class="size-3.5" />
            <span>{{ node.leader.username }}</span>
          </div>
        </Tooltip>
      </div>

      <!-- 操作按钮 -->
      <div
        class="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      >
        <Tooltip :title="$t('shared.common.addChild')">
          <Button
            type="text"
            size="small"
            class="!size-6 !rounded hover:!bg-primary/10"
            @click.stop="emit('addChild', node, 'department')"
          >
            <IconifyIcon icon="lucide:plus" class="size-3.5 text-primary" />
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.edit')">
          <Button
            type="text"
            size="small"
            class="!size-6 !rounded hover:!bg-primary/10"
            @click.stop="emit('edit', node)"
          >
            <IconifyIcon icon="lucide:pencil" class="size-3.5 text-primary" />
          </Button>
        </Tooltip>
        <Tooltip :title="$t('common.delete')">
          <Button
            type="text"
            size="small"
            class="!size-6 !rounded hover:!bg-destructive/10"
            @click.stop="emit('delete', node)"
          >
            <IconifyIcon
              icon="lucide:trash-2"
              class="size-3.5 text-destructive"
            />
          </Button>
        </Tooltip>
      </div>
    </div>

    <!-- 子节点 (带动画) -->
    <Transition name="tree-slide">
      <div v-if="hasChildren && expanded" class="org-tree-children relative">
        <!-- 子节点之间的垂直连接线 -->
        <div
          class="absolute w-px bg-border/40"
          :style="{ left: `${level * 24 + 12}px`, top: 0, bottom: '50%' }"
        ></div>
        <OrgTreeNode
          v-for="child in node.children"
          :key="child.id"
          :node="child"
          :level="level + 1"
          :expanded-ids="expandedIds"
          :selected-id="selectedId"
          :is-expanded="isExpanded"
          :i18n-prefix="i18nPrefix"
          @toggle="(id) => emit('toggle', id)"
          @select="(n) => emit('select', n)"
          @edit="(n) => emit('edit', n)"
          @add-child="(n, t) => emit('addChild', n, t)"
          @delete="(n) => emit('delete', n)"
          @contextmenu="(e, n) => emit('contextmenu', e, n)"
        />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* 展开/收起过渡动画 */
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
