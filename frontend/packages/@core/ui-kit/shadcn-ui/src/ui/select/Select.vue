<script setup lang="ts">
import type { SelectRootEmits, SelectRootProps } from 'reka-ui';

import { SelectRoot as RekaSelectRoot, useForwardPropsEmits } from 'reka-ui';

const props = defineProps<SelectRootProps>();
const emits = defineEmits<SelectRootEmits>();

const forwarded = useForwardPropsEmits(props, emits);
</script>

<template>
  <RekaSelectRoot v-bind="forwarded">
    <slot></slot>
  </RekaSelectRoot>
</template>
