<script setup lang="ts">
/**
 * PreviewToolbar — 预览工具栏
 *
 * 暗色/亮色模式切换 + PC/Tablet/Mobile 响应式断点切换
 */
import { ref } from 'vue';

import { Radio, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

const T = 'admin.dev.crudGenerator';

type Breakpoint = 'desktop' | 'mobile' | 'tablet';

const isDark = ref(false);
const breakpoint = ref<Breakpoint>('desktop');

const BREAKPOINTS: { value: Breakpoint; icon: string; width: string; labelKey: string }[] = [
  { value: 'desktop', icon: 'icon-[lucide--monitor]', width: '100%', labelKey: 'desktop' },
  { value: 'tablet', icon: 'icon-[lucide--tablet]', width: '768px', labelKey: 'tablet' },
  { value: 'mobile', icon: 'icon-[lucide--smartphone]', width: '375px', labelKey: 'mobile' },
];

defineExpose({ isDark, breakpoint });
</script>

<template>
  <div class="flex items-center gap-3">
    <!-- Dark/Light toggle -->
    <Tooltip :title="isDark ? $t(`${T}.previewToolbar.lightMode`) : $t(`${T}.previewToolbar.darkMode`)">
      <button
        class="text-muted-foreground hover:text-foreground flex size-7 items-center justify-center rounded-md transition-colors"
        @click="isDark = !isDark"
      >
        <span v-if="isDark" class="icon-[lucide--sun] size-4" />
        <span v-else class="icon-[lucide--moon] size-4" />
      </button>
    </Tooltip>

    <!-- Breakpoint switcher -->
    <Radio.Group v-model:value="breakpoint" size="small" button-style="solid">
      <Tooltip v-for="bp in BREAKPOINTS" :key="bp.value" :title="$t(`${T}.previewToolbar.${bp.labelKey}`)">
        <Radio.Button :value="bp.value">
          <span :class="bp.icon" class="size-3.5" />
        </Radio.Button>
      </Tooltip>
    </Radio.Group>
  </div>
</template>
