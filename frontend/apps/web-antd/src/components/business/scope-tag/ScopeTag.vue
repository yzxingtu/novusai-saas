<script setup lang="ts">
/**
 * ScopeTag — 统一作用域标签组件
 *
 * 根据 scope 值自动渲染对应颜色、图标和文字的 Ant Design Tag。
 * 替代各模块分散的 scope Tag 渲染逻辑。
 */
import { computed } from 'vue';
import { Tag } from 'ant-design-vue';

import { IconifyIcon } from '@vben/icons';

import { getScopeColor, getScopeIcon, getScopeText } from '#/utils/scope-helpers';

const props = withDefaults(
  defineProps<{
    scope: string;
    showIcon?: boolean;
    size?: 'default' | 'small';
  }>(),
  {
    showIcon: false,
    size: 'default',
  },
);

const color = computed(() => getScopeColor(props.scope));
const text = computed(() => getScopeText(props.scope));
const icon = computed(() => getScopeIcon(props.scope));
const isSmall = computed(() => props.size === 'small');
</script>

<template>
  <Tag
    :color="color"
    :class="[
      '!m-0 !rounded-md',
      isSmall ? '!text-[10px] !leading-[14px] !px-1' : '',
    ]"
  >
    <span v-if="showIcon" class="mr-0.5 inline-flex items-center">
      <IconifyIcon :icon="icon" class="size-3" />
    </span>
    {{ text }}
  </Tag>
</template>
