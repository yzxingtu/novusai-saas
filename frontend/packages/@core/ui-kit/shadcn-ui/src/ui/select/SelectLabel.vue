<script setup lang="ts">
import type { SelectLabelProps } from 'reka-ui';

import { cn } from '@vben-core/shared/utils';

import { SelectLabel as RekaSelectLabel } from 'reka-ui';

const props = defineProps<SelectLabelProps & { class?: any }>();
</script>

<template>
  <RekaSelectLabel
    :class="cn('px-2 py-1.5 text-sm font-semibold', props.class)"
  >
    <slot></slot>
  </RekaSelectLabel>
</template>
