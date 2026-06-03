<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Button, Tag } from 'ant-design-vue';

type ValidationErrorItem = {
  code: string;
  field: string;
  message: string;
  path: string;
};

defineProps<{
  validationErrors: ValidationErrorItem[];
}>();

const emit = defineEmits<{
  locate: [item: ValidationErrorItem];
}>();
</script>

<template>
  <div
    v-if="validationErrors.length > 0"
    class="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-1.5"
  >
    <div class="mb-1.5 flex items-start justify-between gap-3">
      <div>
        <div
          class="flex items-center gap-2 text-sm font-semibold text-amber-800"
        >
          <IconifyIcon icon="lucide:triangle-alert" class="size-4" />
          <span>{{
            $t('admin.system.codegen.generate.validationErrors')
          }}</span>
        </div>
        <div class="mt-1 text-xs leading-5 text-amber-700/90">
          {{ $t('admin.system.codegen.builder.validationListHint') }}
        </div>
      </div>
      <Tag color="warning" class="!mr-0">
        {{ validationErrors.length }}
      </Tag>
    </div>

    <div class="grid max-h-36 gap-1.5 overflow-y-auto pr-1">
      <div
        v-for="(item, index) in validationErrors"
        :key="`${item.path}-${item.field}-${index}`"
        class="flex flex-col gap-2 rounded-lg border border-amber-200/80 bg-background/85 px-3 py-2 md:flex-row md:items-center md:justify-between"
      >
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-foreground">
            {{ item.message }}
          </div>
          <div
            class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
          >
            <span v-if="item.path">{{ item.path }}</span>
            <span v-if="item.field">{{ item.field }}</span>
          </div>
        </div>
        <Button size="small" @click="emit('locate', item)">
          <IconifyIcon icon="lucide:locate-fixed" class="mr-1 size-4" />
          {{ $t('admin.system.codegen.builder.locateIssue') }}
        </Button>
      </div>
    </div>
  </div>
</template>
