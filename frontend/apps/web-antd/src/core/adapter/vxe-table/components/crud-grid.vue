<script lang="ts" setup>
/**
 * CrudGrid - 声明式表格包装组件
 *
 * - toolbar-actions（左侧）：刷新按钮 + 创建按钮
 * - toolbar-tools（右侧）：回收站 + 导出 + 页面自定义工具
 */
import { computed, ref, useAttrs, useSlots } from 'vue';

import { Download, IconifyIcon, Plus } from '@vben/icons';

import { Badge, Button, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({
  name: 'CrudGrid',
  inheritAttrs: false,
});

const props = withDefaults(defineProps<Props>(), {
  showExport: true,
});

interface Props {
  /** 原始 Grid 组件 */
  grid: any;
  /** 是否显示导出按钮 */
  showExport?: boolean;
  /** 导出按钮点击回调 */
  onExport?: () => void;
  /** 是否显示回收站按钮 */
  showRecycleBin?: boolean;
  /** 回收站记录数量 */
  recycleBinCount?: number;
  /** 回收站按钮点击回调 */
  onRecycleBin?: () => void;
  /** 刷新回调 */
  onRefresh?: () => void;
  /** 创建回调（提供时显示创建按钮） */
  onCreate?: () => void;
  /** 创建按钮权限码 */
  createPermission?: string;
  /** 创建按钮文案 */
  createLabel?: string;
}

const attrs = useAttrs();

const slots = useSlots();

// 过滤掉 toolbar-tools / toolbar-actions 插槽，单独处理
const filteredSlots = computed(() => {
  const result: Record<string, any> = {};
  for (const name of Object.keys(slots)) {
    if (name !== 'toolbar-tools' && name !== 'toolbar-actions') {
      result[name] = slots[name];
    }
  }
  return result;
});

// 检查是否有 toolbar-tools 插槽
const hasToolbarToolsSlot = computed(() => 'toolbar-tools' in slots);
// 检查是否有 toolbar-actions 插槽
const hasToolbarActionsSlot = computed(() => 'toolbar-actions' in slots);

// 刷新按钮旋转动画
const refreshAngle = ref(0);
function handleRefresh() {
  refreshAngle.value += 360;
  props.onRefresh?.();
}
</script>

<template>
  <component :is="grid" v-bind="attrs">
    <!-- 透传除 toolbar-tools / toolbar-actions 外的所有插槽 -->
    <template
      v-for="name in Object.keys(filteredSlots)"
      :key="name"
      #[name]="slotProps"
    >
      <slot :name="name" v-bind="slotProps ?? {}"></slot>
    </template>

    <!-- 左侧工具栏：刷新 + 创建 -->
    <template #toolbar-actions>
      <div class="flex items-center gap-2">
        <Tooltip v-if="props.onRefresh" :title="$t('common.refresh')">
          <Button shape="circle" @click="handleRefresh">
            <template #icon>
              <IconifyIcon
                icon="lucide:refresh-cw"
                class="size-4"
                :style="{ transform: `rotate(${refreshAngle}deg)`, transition: 'transform 0.5s ease' }"
              />
            </template>
          </Button>
        </Tooltip>
        <Button
          v-if="props.onCreate && props.createPermission"
          v-access:code="[props.createPermission]"
          type="primary"
          @click="props.onCreate"
        >
          <template #icon>
            <Plus class="size-4" />
          </template>
          {{ props.createLabel }}
        </Button>
        <Button
          v-else-if="props.onCreate && !props.createPermission"
          type="primary"
          @click="props.onCreate"
        >
          <template #icon>
            <Plus class="size-4" />
          </template>
          {{ props.createLabel }}
        </Button>
        <slot
          v-if="hasToolbarActionsSlot"
          name="toolbar-actions"
        ></slot>
      </div>
    </template>

    <!-- 右侧工具栏：页面自定义 + 回收站 + 导出 -->
    <template #toolbar-tools="slotProps">
      <slot
        v-if="hasToolbarToolsSlot"
        name="toolbar-tools"
        v-bind="slotProps || {}"
      ></slot>
      <Tooltip v-if="showRecycleBin" :title="$t('common.recycleBin.title')">
        <Badge :count="props.recycleBinCount" :offset="[-4, 4]" size="small">
          <Button
            shape="circle"
            class="ml-2"
            @click="props.onRecycleBin"
          >
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
          </Button>
        </Badge>
      </Tooltip>
      <Tooltip v-if="showExport" :title="$t('common.export')">
        <Button
          type="primary"
          shape="circle"
          class="ml-2"
          @click="props.onExport"
        >
          <template #icon>
            <Download class="size-4" />
          </template>
        </Button>
      </Tooltip>
    </template>
  </component>
</template>
