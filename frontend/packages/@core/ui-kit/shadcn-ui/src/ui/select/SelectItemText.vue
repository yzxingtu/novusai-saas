<script setup lang="ts">
import type { SelectItemTextProps } from 'reka-ui';

import { SelectItemText as RekaSelectItemText } from 'reka-ui';

const props = defineProps<SelectItemTextProps>();
</script>

<template>
  <RekaSelectItemText v-bind="props">
    <slot></slot>
  </RekaSelectItemText>
</template>
