<script lang="ts" setup>
import { computed } from 'vue';

import { Checkbox, Input, InputNumber, Select } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyDatabaseSection' });

const {
  asBoolean,
  asNumberOrUndefined,
  selectedField,
  selectedFieldType,
  strVal,
  typeOptions,
  updateField,
  onTypeChange,
} = useFieldPropertyPanelContext();

const showStringLength = computed(() => selectedFieldType.value === 'String');
const showDecimalOptions = computed(
  () => selectedFieldType.value === 'Decimal',
);
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.database') }}
    </div>
    <div class="flex flex-col gap-3">
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.type')
        }}</label>
        <Select
          :value="selectedFieldType"
          class="w-full"
          :options="typeOptions"
          :placeholder="
            $t('admin.system.codegen.property.placeholderSelectType')
          "
          @change="onTypeChange"
        />
      </div>
      <div v-if="showStringLength">
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.length')
        }}</label>
        <InputNumber
          :value="asNumberOrUndefined(selectedField?.max_length)"
          :min="1"
          class="w-full"
          :placeholder="
            $t('admin.system.codegen.property.placeholderExampleLength')
          "
          @update:value="
            (value) => updateField({ max_length: asNumberOrUndefined(value) })
          "
        />
      </div>
      <template v-if="showDecimalOptions">
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.precision')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.precision) ?? 10"
            :min="1"
            :max="65"
            class="w-full"
            @update:value="
              (value) => updateField({ precision: asNumberOrUndefined(value) })
            "
          />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.scale')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.scale) ?? 2"
            :min="0"
            :max="30"
            class="w-full"
            @update:value="
              (value) => updateField({ scale: asNumberOrUndefined(value) })
            "
          />
        </div>
      </template>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.defaultValue')
        }}</label>
        <Input
          :value="strVal(selectedField?.default)"
          :placeholder="$t('admin.system.codegen.property.placeholderOptional')"
          @update:value="updateField({ default: $event })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.dbDefault')
        }}</label>
        <Input
          :value="strVal(selectedField?.db_default)"
          :placeholder="
            $t('admin.system.codegen.property.placeholderDbDefault')
          "
          @update:value="updateField({ db_default: $event })"
        />
      </div>
      <div class="flex flex-wrap gap-4">
        <Checkbox
          :checked="asBoolean(selectedField?.unique)"
          @update:checked="(value) => updateField({ unique: asBoolean(value) })"
        >
          {{ $t('admin.system.codegen.property.unique') }}
        </Checkbox>
        <Checkbox
          :checked="asBoolean(selectedField?.index)"
          @update:checked="(value) => updateField({ index: asBoolean(value) })"
        >
          {{ $t('admin.system.codegen.property.index') }}
        </Checkbox>
      </div>
    </div>
  </section>
</template>
