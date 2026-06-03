<script lang="ts" setup>
import { $t } from '#/locales';

import { useWysiwygFormContext } from './wysiwyg-form-context';

defineOptions({ name: 'WysiwygFormHeader' });

const { formTitle, previewBadges } = useWysiwygFormContext();
</script>

<template>
  <div class="border-b border-border/50 px-5 py-4">
    <div
      class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between"
    >
      <div class="min-w-0">
        <div
          class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground"
        >
          {{ $t('admin.system.codegen.wysiwyg.formView') }}
        </div>
        <div class="mt-2 text-lg font-semibold text-foreground">
          {{ formTitle }}
        </div>
        <div class="mt-1 text-sm leading-6 text-muted-foreground">
          {{ $t('admin.system.codegen.builder.previewFormDesc') }}
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <span
          v-for="item in previewBadges"
          :key="item.key"
          class="rounded-full border border-border/70 bg-muted/15 px-3 py-1 text-xs text-muted-foreground"
        >
          {{ item.label }}
        </span>
      </div>
    </div>
  </div>
</template>
