<script setup lang="ts">
import type { SelectGroupProps } from 'reka-ui';

import { computed } from 'vue';

import { cn } from '@vben-core/shared/utils';

import { SelectGroup as RekaSelectGroup } from 'reka-ui';

const props = defineProps<SelectGroupProps & { class?: any }>();

const delegatedProps = computed(() => {
  const { class: _, ...delegated } = props;

  return delegated;
});
</script>

<template>
  <RekaSelectGroup
    :class="cn('w-full p-1', props.class)"
    v-bind="delegatedProps"
  >
    <slot></slot>
  </RekaSelectGroup>
</template>
