<script lang="ts" setup>
/**
 * OnlineIndicator — 在线状态圆点指示器
 *
 * 显示绿色（在线）或灰色（离线）圆点，支持脉冲动画和 Tooltip。
 */
defineOptions({ name: 'OnlineIndicator' });

import { computed } from 'vue';

import { Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    /** 是否在线 */
    online: boolean;
    /** 圆点大小 */
    size?: 'lg' | 'md' | 'sm';
    /** 是否显示文字标签 */
    showLabel?: boolean;
    /** 在线时是否有脉冲动画 */
    pulse?: boolean;
  }>(),
  {
    size: 'sm',
    showLabel: false,
    pulse: true,
  },
);

const sizeClass = computed(() => {
  switch (props.size) {
    case 'lg': {
      return 'size-2.5';
    }
    case 'md': {
      return 'size-2';
    }
    default: {
      return 'size-1.5';
    }
  }
});

const label = computed(() =>
  props.online
    ? $t('common.presence.online')
    : $t('common.presence.offline'),
);
</script>

<template>
  <Tooltip :title="label" placement="top">
    <span class="inline-flex items-center gap-1">
      <span class="relative inline-flex">
        <!-- 脉冲动画层 -->
        <span
          v-if="online && pulse"
          class="absolute inline-flex size-full animate-ping rounded-full bg-green-500 opacity-50"
        />
        <!-- 实心圆点 -->
        <span
          class="relative inline-block rounded-full"
          :class="[
            sizeClass,
            online ? 'bg-green-500' : 'bg-muted-foreground/30',
          ]"
        />
      </span>
      <span
        v-if="showLabel"
        class="text-xs"
        :class="online ? 'text-green-600' : 'text-muted-foreground'"
      >
        {{ label }}
      </span>
    </span>
  </Tooltip>
</template>
