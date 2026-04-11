<script lang="ts" setup>
import { Input, Select } from 'ant-design-vue';

import { $t } from '#/locales';

import EnumValuesEditor from '../EnumValuesEditor.vue';
import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyEnumSection' });

const {
  asString,
  enumRenderOptions,
  getEnumValues,
  selectedField,
  selectedFieldForm,
  strVal,
  updateField,
} = useFieldPropertyPanelContext();
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.enum') }}
    </div>
    <div class="flex flex-col gap-3">
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.dictCode')
        }}</label>
        <Input
          :value="strVal(selectedField?.dict_code)"
          :placeholder="$t('admin.system.codegen.property.placeholderDictCode')"
          allow-clear
          @update:value="updateField({ dict_code: $event || undefined })"
        />
        <div class="mt-1 text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.property.dictCodeHelp') }}
        </div>
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.enumRender')
        }}</label>
        <Select
          :value="
            asString(selectedFieldForm.enumRender) ||
            asString(selectedField?.enum_render) ||
            'select'
          "
          class="w-full"
          :options="enumRenderOptions"
          @change="
            (value) =>
              updateField({
                form: {
                  ...selectedFieldForm,
                  enumRender: asString(value),
                },
                enum_render: asString(value),
              })
          "
        />
      </div>
      <EnumValuesEditor
        :model-value="getEnumValues(selectedField || {})"
        @update:model-value="updateField({ enum_values: $event })"
      />
    </div>
  </section>
</template>
