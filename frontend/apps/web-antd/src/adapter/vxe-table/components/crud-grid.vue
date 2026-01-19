<script lang="ts" setup>
/**
 * CrudGrid - 带导出按钮的 Grid 包装组件
 *
 * 在 toolbar-tools 插槽中自动添加导出按钮
 */
import { computed, useSlots } from 'vue';

import { Download } from '@vben/icons';

import { Button, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({
  name: 'CrudGrid',
});

interface Props {
  /** 原始 Grid 组件 */
  grid: any;
  /** 是否显示导出按钮 */
  showExport?: boolean;
  /** 导出按钮点击回调 */
  onExport?: () => void;
}

const props = withDefaults(defineProps<Props>(), {
  showExport: true,
});

const slots = useSlots();

// 过滤掉 toolbar-tools 插槽，单独处理
const filteredSlots = computed(() => {
  const result: Record<string, any> = {};
  for (const name of Object.keys(slots)) {
    if (name !== 'toolbar-tools') {
      result[name] = slots[name];
    }
  }
  return result;
});

// 检查是否有 toolbar-tools 插槽
const hasToolbarToolsSlot = computed(() => 'toolbar-tools' in slots);
</script>

<template>
  <component :is="grid">
    <!-- 透传除 toolbar-tools 外的所有插槽 -->
    <template
      v-for="name in Object.keys(filteredSlots)"
      :key="name"
      #[name]="slotProps"
    >
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>

    <!-- 工具栏插槽：添加导出按钮 -->
    <template #toolbar-tools="slotProps">
      <slot v-if="hasToolbarToolsSlot" name="toolbar-tools" v-bind="slotProps || {}" />
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
