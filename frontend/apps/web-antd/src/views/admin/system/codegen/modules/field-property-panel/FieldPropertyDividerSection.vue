<script lang="ts" setup>
import { Input } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyDividerSection' });

const { selectedField, strVal, updateField } = useFieldPropertyPanelContext();
</script>

<template>
  <div class="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
    <div
      class="rounded-[16px] border border-dashed border-border/70 bg-muted/15 p-3"
    >
      <div
        class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
      >
        {{ $t('admin.system.codegen.palette.divider') }}
      </div>
      <label class="mb-1 mt-3 block text-xs font-medium text-foreground">
        {{ $t('admin.system.codegen.property.displayNameZh') }}
      </label>
      <Input
        :value="strVal(selectedField?.divider_title || selectedField?.title)"
        :placeholder="
          $t('admin.system.codegen.palette.dividerTitlePlaceholder')
        "
        @update:value="updateField({ divider_title: $event, title: $event })"
      />
    </div>
  </div>
</template>
