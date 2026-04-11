<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

defineOptions({ name: 'FieldPropertyEmptyState' });
</script>

<template>
  <div
    class="flex flex-1 flex-col items-center justify-center gap-3 p-5 text-center text-muted-foreground"
  >
    <div
      class="flex size-12 items-center justify-center rounded-2xl bg-muted/25"
    >
      <IconifyIcon icon="lucide:sliders-horizontal" class="size-6" />
    </div>
    <span class="text-sm font-medium text-foreground">{{
      $t('admin.system.codegen.property.title')
    }}</span>
    <span class="max-w-xs text-xs leading-6">{{
      $t('admin.system.codegen.property.selectFieldHint')
    }}</span>
  </div>
</template>
