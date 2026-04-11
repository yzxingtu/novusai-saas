<script lang="ts" setup>
import { Checkbox, InputNumber } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyUploadSection' });

const { asBoolean, asNumberOrUndefined, selectedField, updateField } =
  useFieldPropertyPanelContext();
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.upload') }}
    </div>
    <div class="flex flex-col gap-3">
      <Checkbox
        :checked="asBoolean(selectedField?.multiple)"
        @update:checked="(value) => updateField({ multiple: asBoolean(value) })"
      >
        {{ $t('admin.system.codegen.property.multiple') }}
      </Checkbox>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.maxCount')
        }}</label>
        <InputNumber
          :value="asNumberOrUndefined(selectedField?.max_count) ?? 9"
          :min="1"
          class="w-full"
          @update:value="
            (value) => updateField({ max_count: asNumberOrUndefined(value) })
          "
        />
      </div>
    </div>
  </section>
</template>
