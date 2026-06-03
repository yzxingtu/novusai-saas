<script lang="ts" setup>
import { computed } from 'vue';

import { Checkbox, Input, Select } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyRelationSection' });

const props = defineProps<{
  mode: 'select' | 'tree' | 'user';
}>();

const {
  asBoolean,
  asString,
  displayFieldLoading,
  displayFieldOptions,
  filterOptionByValue,
  relationModeOptions,
  selectedField,
  strVal,
  tableOptions,
  updateField,
} = useFieldPropertyPanelContext();

const showRelationMode = computed(() => props.mode === 'select');
const showMultiple = computed(() => props.mode === 'select');
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.relation') }}
    </div>
    <div class="flex flex-col gap-3">
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.relationTable')
        }}</label>
        <Select
          :value="asString(selectedField?.relation_table)"
          class="w-full"
          :options="tableOptions"
          show-search
          :filter-option="filterOptionByValue"
          :placeholder="
            $t('admin.system.codegen.property.placeholderRelationTable')
          "
          @change="(value) => updateField({ relation_table: asString(value) })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.displayField')
        }}</label>
        <Select
          :value="
            asString(selectedField?.relation_display) ||
            asString(selectedField?.relation_display_field) ||
            'name'
          "
          class="w-full"
          :options="displayFieldOptions"
          :loading="displayFieldLoading"
          show-search
          :filter-option="filterOptionByValue"
          :placeholder="
            $t('admin.system.codegen.property.placeholderRelationDisplay')
          "
          allow-clear
          @change="
            (value) =>
              updateField({
                relation_display: asString(value) || undefined,
                relation_display_field: asString(value) || undefined,
              })
          "
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.valueField')
        }}</label>
        <Input
          :value="strVal(selectedField?.relation_value_field || 'id')"
          :placeholder="
            $t('admin.system.codegen.property.placeholderRelationValueField')
          "
          @update:value="updateField({ relation_value_field: $event })"
        />
      </div>
      <div v-if="showRelationMode">
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.relationMode')
        }}</label>
        <Select
          :value="asString(selectedField?.relation_mode) || 'select'"
          class="w-full"
          :options="relationModeOptions"
          @change="(value) => updateField({ relation_mode: asString(value) })"
        />
      </div>
      <Checkbox
        v-if="showMultiple"
        :checked="asBoolean(selectedField?.multiple)"
        @update:checked="(value) => updateField({ multiple: asBoolean(value) })"
      >
        {{ $t('admin.system.codegen.property.multiple') }}
      </Checkbox>
    </div>
  </section>
</template>
