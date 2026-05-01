<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Checkbox, Input, InputNumber, Select, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyFormSection' });

const {
  asBoolean,
  asNumberOrUndefined,
  asString,
  componentOptions,
  patternOptions,
  queryTypeOptionsComputed,
  selectedField,
  selectedFieldForm,
  selectedFieldType,
  selectedFormComponent,
  setFormComponent,
  strVal,
  updateField,
} = useFieldPropertyPanelContext();

const supportsValidation = computed(() =>
  ['Decimal', 'Float', 'Integer', 'String', 'Text'].includes(
    selectedFieldType.value,
  ),
);

const isTextType = computed(() =>
  ['String', 'Text'].includes(selectedFieldType.value),
);

const isNumericType = computed(() =>
  ['Decimal', 'Float', 'Integer'].includes(selectedFieldType.value),
);
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.formList') }}
    </div>
    <div class="flex flex-col gap-3">
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.component')
        }}</label>
        <Select
          :value="selectedFormComponent"
          class="w-full"
          :options="componentOptions"
          :placeholder="
            $t('admin.system.codegen.property.placeholderSelectComponent')
          "
          @change="setFormComponent"
        />
      </div>
      <div class="flex flex-wrap gap-4">
        <Checkbox
          :checked="selectedField?.insertable !== false"
          @update:checked="
            (value) => updateField({ insertable: asBoolean(value) })
          "
        >
          {{ $t('admin.system.codegen.property.insertable') }}
        </Checkbox>
        <Checkbox
          :checked="selectedField?.editable !== false"
          @update:checked="
            (value) => updateField({ editable: asBoolean(value) })
          "
        >
          {{ $t('admin.system.codegen.property.editable') }}
        </Checkbox>
        <Checkbox
          :checked="asBoolean(selectedField?.sortable)"
          @update:checked="
            (value) => updateField({ sortable: asBoolean(value) })
          "
        >
          {{ $t('admin.system.codegen.property.sortable') }}
        </Checkbox>
      </div>
      <div
        v-if="selectedField && asBoolean(selectedField.filterable)"
        class="flex items-center gap-2"
      >
        <label class="shrink-0 text-xs">{{
          $t('admin.system.codegen.property.queryType')
        }}</label>
        <Select
          :value="
            asString(selectedFieldForm.queryType) ||
            asString(selectedField.query_type)
          "
          class="flex-1"
          :options="queryTypeOptionsComputed"
          :placeholder="
            $t('admin.system.codegen.property.placeholderQueryTypeDefault')
          "
          @change="
            (value) =>
              updateField({
                form: { ...selectedFieldForm, queryType: asString(value) },
                query_type: asString(value),
              })
          "
        />
        <Tooltip :title="$t('admin.system.codegen.property.queryTypeHelp')">
          <IconifyIcon
            icon="lucide:info"
            class="size-4 text-muted-foreground"
          />
        </Tooltip>
      </div>
      <div
        v-if="supportsValidation"
        class="mt-2 text-xs font-medium text-muted-foreground"
      >
        {{ $t('admin.system.codegen.property.validation') }}
      </div>
      <div v-if="isTextType" class="grid grid-cols-2 gap-2">
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.minLength')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.min_length)"
            :min="0"
            class="w-full"
            :placeholder="
              $t('admin.system.codegen.property.placeholderOptional')
            "
            @update:value="
              (value) => updateField({ min_length: asNumberOrUndefined(value) })
            "
          />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.maxLength')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.max_length)"
            :min="1"
            class="w-full"
            :placeholder="
              $t('admin.system.codegen.property.placeholderOptional')
            "
            @update:value="
              (value) => updateField({ max_length: asNumberOrUndefined(value) })
            "
          />
        </div>
      </div>
      <div v-if="isNumericType" class="grid grid-cols-2 gap-2">
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.minValue')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.min_value)"
            class="w-full"
            :placeholder="
              $t('admin.system.codegen.property.placeholderOptional')
            "
            @update:value="
              (value) => updateField({ min_value: asNumberOrUndefined(value) })
            "
          />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.maxValue')
          }}</label>
          <InputNumber
            :value="asNumberOrUndefined(selectedField?.max_value)"
            class="w-full"
            :placeholder="
              $t('admin.system.codegen.property.placeholderOptional')
            "
            @update:value="
              (value) => updateField({ max_value: asNumberOrUndefined(value) })
            "
          />
        </div>
      </div>
      <div v-if="isTextType">
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.pattern')
        }}</label>
        <Select
          :value="asString(selectedField?.pattern)"
          class="mb-2 w-full"
          :options="patternOptions"
          allow-clear
          @change="
            (value) => updateField({ pattern: asString(value) || undefined })
          "
        />
        <div v-if="asString(selectedField?.pattern) === 'custom'" class="mt-1">
          <label class="mb-1 block text-xs">{{
            $t('admin.system.codegen.property.patternRegex')
          }}</label>
          <Input
            :value="
              strVal(
                selectedField?.pattern_regex || selectedField?.patternRegex,
              )
            "
            :placeholder="
              $t('admin.system.codegen.property.placeholderPatternRegex')
            "
            allow-clear
            @update:value="
              updateField({
                pattern_regex: $event || undefined,
                patternRegex: $event || undefined,
              })
            "
          />
        </div>
      </div>
    </div>
  </section>
</template>
