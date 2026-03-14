<script lang="ts" setup>
/**
 * CrudGrid - Declarative table wrapper component
 * CrudGrid - 声明式表格包装组件
 *
 * - toolbar-actions (left): refresh + create buttons / 左侧：刷新按钮 + 创建按钮
 * - toolbar-tools (right): recycle bin + export + custom tools / 右侧：回收站 + 导出 + 页面自定义工具
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
  createLabel: '',
  createPermission: '',
  onCreate: undefined,
  onExport: undefined,
  onRecycleBin: undefined,
  onRefresh: undefined,
  recycleBinCount: 0,
  recycleBinPermission: '',
  showExport: true,
  showRecycleBin: false,
});

interface Props {
  /** Original Grid component / 原始 Grid 组件 */
  grid: any;
  /** Whether to show export button / 是否显示导出按钮 */
  showExport?: boolean;
  /** Export button click callback / 导出按钮点击回调 */
  onExport?: () => void;
  /** Whether to show recycle bin button / 是否显示回收站按钮 */
  showRecycleBin?: boolean;
  /** Recycle bin record count / 回收站记录数量 */
  recycleBinCount?: number;
  /** Recycle bin button click callback / 回收站按钮点击回调 */
  onRecycleBin?: () => void;
  /** Recycle bin permission code (e.g. 'ai_provider:recycle_bin') / 回收站权限码 */
  recycleBinPermission?: string;
  /** Refresh callback / 刷新回调 */
  onRefresh?: () => void;
  /** Create callback (shows create button when provided) / 创建回调（提供时显示创建按钮） */
  onCreate?: () => void;
  /** Create button permission code / 创建按钮权限码 */
  createPermission?: string;
  /** Create button label / 创建按钮文案 */
  createLabel?: string;
}

const attrs = useAttrs();

const slots = useSlots();

// Filter out toolbar-tools / toolbar-actions slots, handle separately / 过滤掉 toolbar-tools / toolbar-actions 插槽，单独处理
const filteredSlots = computed(() => {
  const result: Record<string, any> = {};
  for (const name of Object.keys(slots)) {
    if (name !== 'toolbar-tools' && name !== 'toolbar-actions') {
      result[name] = slots[name];
    }
  }
  return result;
});

// Check for toolbar-tools slot / 检查是否有 toolbar-tools 插槽
const hasToolbarToolsSlot = computed(() => 'toolbar-tools' in slots);
// Check for toolbar-actions slot / 检查是否有 toolbar-actions 插槽
const hasToolbarActionsSlot = computed(() => 'toolbar-actions' in slots);

// Refresh button rotation animation / 刷新按钮旋转动画
const refreshAngle = ref(0);
function handleRefresh() {
  refreshAngle.value += 360;
  props.onRefresh?.();
}
</script>

<template>
  <component :is="grid" v-bind="attrs">
    <!-- Pass through all slots except toolbar-tools / toolbar-actions / 透传除 toolbar-tools / toolbar-actions 外的所有插槽 -->
    <template
      v-for="name in Object.keys(filteredSlots)"
      :key="name"
      #[name]="slotProps"
    >
      <slot :name="name" v-bind="slotProps ?? {}"></slot>
    </template>

    <!-- Left toolbar: refresh + create / 左侧工具栏：刷新 + 创建 -->
    <template #toolbar-actions>
      <div class="flex items-center gap-2">
        <Tooltip v-if="props.onRefresh" :title="$t('common.refresh')">
          <button
            class="flex size-8 items-center justify-center rounded-lg border border-border/60 bg-background text-muted-foreground transition-all hover:border-primary/30 hover:text-primary"
            @click="handleRefresh"
          >
            <IconifyIcon
              icon="lucide:refresh-cw"
              class="size-3.5"
              :style="{
                transform: `rotate(${refreshAngle}deg)`,
                transition: 'transform 0.5s ease',
              }"
            />
          </button>
        </Tooltip>
        <Button
          v-if="props.onCreate && props.createPermission"
          v-access:code="[props.createPermission]"
          type="primary"
          class="!rounded-lg !shadow-sm !shadow-primary/20"
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
          class="!rounded-lg !shadow-sm !shadow-primary/20"
          @click="props.onCreate"
        >
          <template #icon>
            <Plus class="size-4" />
          </template>
          {{ props.createLabel }}
        </Button>
        <slot v-if="hasToolbarActionsSlot" name="toolbar-actions"></slot>
      </div>
    </template>

    <!-- Right toolbar: custom + recycle bin + export / 右侧工具栏：页面自定义 + 回收站 + 导出 -->
    <template #toolbar-tools="slotProps">
      <slot
        v-if="hasToolbarToolsSlot"
        name="toolbar-tools"
        v-bind="slotProps || {}"
      ></slot>
      <span
        v-if="showRecycleBin"
        v-access:code="recycleBinPermission ? [recycleBinPermission] : undefined"
      >
        <Tooltip :title="$t('common.recycleBin.title')">
          <Badge :count="props.recycleBinCount" :offset="[-4, 4]" size="small">
            <button
              class="ml-2 flex size-8 items-center justify-center rounded-lg border border-border/60 bg-background text-muted-foreground transition-all hover:border-destructive/30 hover:text-destructive"
              @click="props.onRecycleBin"
            >
              <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
            </button>
          </Badge>
        </Tooltip>
      </span>
      <Tooltip v-if="showExport" :title="$t('common.export')">
        <button
          class="ml-2 flex size-8 items-center justify-center rounded-lg bg-primary text-white shadow-sm shadow-primary/20 transition-all hover:bg-primary/90"
          @click="props.onExport"
        >
          <Download class="size-3.5" />
        </button>
      </Tooltip>
    </template>
  </component>
</template>
