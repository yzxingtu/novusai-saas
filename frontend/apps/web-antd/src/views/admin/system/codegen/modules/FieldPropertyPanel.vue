<script lang="ts" setup>
/**
 * 字段属性面板 / Field Property Panel
 *
 * 右侧属性面板，选中字段时显示
 */
import type { Recordable } from '@vben/types';

import { computed, onMounted, ref, watch } from 'vue';
import { Alert, Checkbox, Divider, Input, InputNumber, Select, Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '#/locales';
import {
  getCodegenComponentsApi,
  getCodegenDbColumnsApi,
  getCodegenDbTablesApi,
  getCodegenTypesApi,
} from '#/api/admin/codegen';
import { useCodegenBuilderStore } from '#/store';

import { message } from 'ant-design-vue';

import { inferFieldConfig, inferFieldConfigForMerge, inferRelationTable } from './infer';
import EnumValuesEditor from './EnumValuesEditor.vue';

defineOptions({ name: 'FieldPropertyPanel' });

const store = useCodegenBuilderStore();

const typeOptions = ref<Array<{ label: string; value: string }>>([]);
const componentOptions = ref<Array<{ label: string; value: string }>>([]);
const tableOptions = ref<Array<{ label: string; value: string }>>([]);
const displayFieldOptions = ref<Array<{ label: string; value: string }>>([]);
const displayFieldLoading = ref(false);

const selectedField = computed<Recordable | null>(() => {
  const key = store.selectedFieldKey;
  if (!key) return null;
  const fields = (store.configJson.fields as Recordable[]) || [];
  return fields.find((f) => f.__key === key || f.name === key) ?? null;
});

const isDivider = computed(() => selectedField.value?.type === '__divider__' || selectedField.value?.divider);

async function loadTypes() {
  try {
    const types = (await getCodegenTypesApi()) as Array<{ type: string }>;
    typeOptions.value = types.map((t) => ({ label: t.type, value: t.type }));
  } catch {
    typeOptions.value = [];
  }
}

async function loadComponents() {
  try {
    const comps = (await getCodegenComponentsApi()) as Array<{ name: string; label: string }>;
    componentOptions.value = comps.map((c) => ({ label: c.label || c.name, value: c.name }));
  } catch {
    componentOptions.value = [];
  }
}

async function loadTables() {
  try {
    const tables = (await getCodegenDbTablesApi()) as Array<{ name: string }>;
    tableOptions.value = tables.map((t) => ({ label: t.name, value: t.name }));
  } catch {
    tableOptions.value = [];
  }
}

onMounted(() => {
  loadTypes();
  loadComponents();
  loadTables();
});

watch(
  () => selectedField.value?.relation_table,
  async (table) => {
    if (!table) {
      displayFieldOptions.value = [];
      return;
    }
    displayFieldLoading.value = true;
    try {
      const cols = await getCodegenDbColumnsApi(String(table));
      displayFieldOptions.value = cols.map((c: { name: string; type?: string }) => ({
        label: `${c.name}${c.type ? ` (${c.type})` : ''}`,
        value: c.name,
      }));
    } catch {
      displayFieldOptions.value = [];
    } finally {
      displayFieldLoading.value = false;
    }
  },
  { immediate: true },
);

const queryTypeOptionsComputed = computed(() => [
  { labelKey: 'admin.system.codegen.query.eq', value: 'eq' },
  { labelKey: 'admin.system.codegen.query.ne', value: 'ne' },
  { labelKey: 'admin.system.codegen.query.gt', value: 'gt' },
  { labelKey: 'admin.system.codegen.query.gte', value: 'gte' },
  { labelKey: 'admin.system.codegen.query.lt', value: 'lt' },
  { labelKey: 'admin.system.codegen.query.lte', value: 'lte' },
  { labelKey: 'admin.system.codegen.query.like', value: 'like' },
  { labelKey: 'admin.system.codegen.query.ilike', value: 'ilike' },
  { labelKey: 'admin.system.codegen.query.between', value: 'between' },
  { labelKey: 'admin.system.codegen.query.in', value: 'in' },
].map((o) => ({ label: $t(o.labelKey), value: o.value })));

const enumRenderOptions = computed(() => [
  { label: $t('admin.system.codegen.property.enumRenderSelect'), value: 'select' },
  { label: $t('admin.system.codegen.property.enumRenderRadio'), value: 'radio' },
  { label: $t('admin.system.codegen.property.enumRenderCheckbox'), value: 'checkbox' },
]);

const patternOptions = computed(() => [
  { label: '—', value: '' },
  { label: $t('admin.system.codegen.property.patternEmail'), value: 'email' },
  { label: $t('admin.system.codegen.property.patternPhone'), value: 'phone' },
  { label: $t('admin.system.codegen.property.patternUrl'), value: 'url' },
  { label: $t('admin.system.codegen.property.patternIdCard'), value: 'idCard' },
  { label: $t('admin.system.codegen.property.patternCustom'), value: 'custom' },
]);

const relationModeOptions = computed(() => [
  { label: $t('admin.system.codegen.property.modeSelect'), value: 'select' },
  { label: $t('admin.system.codegen.property.modeTreeSelect'), value: 'treeSelect' },
  { label: $t('admin.system.codegen.property.modeModal'), value: 'modal' },
]);

const inferredComponent = computed(() => {
  const name = (selectedField.value?.name as string) || '';
  if (!name) return null;
  const c = inferFieldConfig(name);
  return c?.component || null;
});

const showInferHint = computed(() => !!selectedField.value?._auto_detected);
const showRecommend = computed(() => {
  const f = selectedField.value;
  if (!f || !inferredComponent.value) return false;
  const cur = (f.form as Record<string, unknown>)?.component || f.form_component || 'input';
  return cur !== inferredComponent.value;
});
const recommendMessage = computed(() => {
  const comp = inferredComponent.value;
  if (!comp || typeof comp !== 'string') return '';
  return $t('admin.system.codegen.property.recommend', { component: comp });
});

function updateField(patch: Record<string, unknown>) {
  if (!selectedField.value) return;
  const key = (selectedField.value.__key as string) || (selectedField.value.name as string);
  const fields = [...((store.configJson.fields as Recordable[]) || [])];
  const idx = fields.findIndex((f) => (f.__key as string) === key || (f.name as string) === key);
  if (idx < 0) return;
  if (patch.form && typeof patch.form === 'object') {
    patch.form = { ...(fields[idx].form as Record<string, unknown>) || {}, ...patch.form };
  }
  if (patch.required === true) patch.nullable = false;
  if (patch.nullable === true) patch.required = false;
  fields[idx] = { ...fields[idx], ...patch };
  store.updateConfig({ fields });
}

function onNameChange(name: string) {
  const trimmed = (name || '').trim();
  const field = selectedField.value;
  if (!field) return;
  if (trimmed) {
    const allFields = (store.configJson.fields as Recordable[]) || [];
    const otherWithSameName = allFields.find(
      (f) => f.__key !== field.__key && (f.name as string)?.toLowerCase() === trimmed.toLowerCase(),
    );
    if (otherWithSameName) {
      message.warning($t('admin.system.codegen.property.duplicateFieldName'));
      return;
    }
  }
  updateField({ name: trimmed });
  if (!trimmed) return;
  const shouldInfer = field._auto_detected || !field._user_modified;
  if (!shouldInfer) return;
  const inferred = inferFieldConfigForMerge(trimmed);
  const patch: Record<string, unknown> = { ...inferred };
  if (inferred.type === 'ForeignKey') {
    patch.relation_table = inferRelationTable(trimmed) || '';
    patch.relation_display = 'name';
  }
  const form = (field.form as Record<string, unknown>) || {};
  if (inferred.form && typeof inferred.form === 'object') {
    patch.form = { ...form, ...(inferred.form as Record<string, unknown>) };
  }
  updateField(patch);
}

function getFormComponent(): string {
  const f = selectedField.value;
  const form = (f?.form as Record<string, unknown>) || {};
  return (form.component as string) || f?.form_component || 'input';
}

function setFormComponent(v: string) {
  const form = (selectedField.value?.form as Record<string, unknown>) || {};
  updateField({ form: { ...form, component: v || undefined } });
}

function onTypeChange(v: string) {
  const patch: Record<string, unknown> = { type: v };
  const curType = selectedField.value?.type as string;
  if (v !== 'Enum' && ['Enum'].includes(curType)) {
    patch.enum_values = undefined;
    patch.dict_code = undefined;
    patch.enum_render = undefined;
  }
  if (!['ForeignKey', 'TreeSelect', 'UserSelect', 'DeptSelect'].includes(v) && ['ForeignKey', 'TreeSelect', 'UserSelect', 'DeptSelect'].includes(curType)) {
    patch.relation_table = undefined;
    patch.relation_display = undefined;
    patch.relation_display_field = undefined;
    patch.relation_value_field = undefined;
    patch.relation_mode = undefined;
    patch.multiple = undefined;
  }
  if (v !== 'Cascader' && curType === 'Cascader') {
    patch.cascader_options = undefined;
  }
  const uploadTypes = ['ImageUpload', 'Image', 'Images', 'FilePicker', 'File', 'Files'];
  if (!uploadTypes.includes(v) && uploadTypes.includes(curType)) {
    patch.multiple = undefined;
    patch.max_count = undefined;
  }
  if (v === 'UserSelect' && !selectedField.value?.relation_table) {
    patch.relation_table = 'users';
    patch.relation_display = 'name';
  }
  if (v === 'DeptSelect' && !selectedField.value?.relation_table) {
    patch.relation_table = 'departments';
    patch.relation_display = 'name';
  }
  updateField(patch);
}

function onCascaderOptionsChange(v: string) {
  try {
    const parsed = v?.trim() ? JSON.parse(v) : [];
    updateField({ cascader_options: parsed });
  } catch {
    message.warning($t('admin.system.codegen.property.invalidCascaderJson'));
  }
}

/** 确保 Input value 为 string，避免 boolean 等导致 Vue 警告 / Ensure Input value is string, avoid Vue warning from boolean etc */
function strVal(v: unknown): string {
  return typeof v === 'string' ? v : '';
}
</script>

<template>
  <div v-if="!selectedField" class="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-muted-foreground">
    <span class="text-sm">{{ $t('admin.system.codegen.property.title') }}</span>
    <span class="text-xs">{{ $t('admin.system.codegen.palette.dropHint') }}</span>
  </div>
  <div v-else-if="isDivider" class="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
    <div class="flex flex-col gap-2">
      <label class="text-xs font-medium">{{ $t('admin.system.codegen.property.displayNameZh') }}</label>
      <Input
        :value="strVal(selectedField.divider_title || selectedField.title)"
        :placeholder="$t('admin.system.codegen.palette.dividerTitlePlaceholder')"
        @update:value="updateField({ divider_title: $event, title: $event })"
      />
    </div>
  </div>
  <div v-else class="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
    <Alert v-if="showInferHint" type="success" show-icon class="!py-1.5 text-xs" :message="$t('admin.system.codegen.property.inferHint')" />
    <Alert v-else-if="showRecommend && typeof recommendMessage === 'string' && recommendMessage.trim()" type="info" show-icon class="!py-1.5 text-xs" :message="recommendMessage" />

    <div>
      <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.basic') }}</div>
      <div class="flex flex-col gap-3">
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.fieldName') }}</label>
          <Input :value="strVal(selectedField.name)" :placeholder="$t('admin.system.codegen.property.placeholderSnakeCase')" @update:value="onNameChange" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.displayNameZh') }}</label>
          <Input :value="strVal(selectedField.display_name)" :placeholder="$t('admin.system.codegen.property.placeholderZh')" @update:value="updateField({ display_name: $event })" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.displayNameEn') }}</label>
          <Input :value="strVal(selectedField.display_name_en)" :placeholder="$t('admin.system.codegen.property.placeholderEn')" @update:value="updateField({ display_name_en: $event })" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.comment') }}</label>
          <Input :value="strVal(selectedField.comment)" :placeholder="$t('admin.system.codegen.property.placeholderDbComment')" @update:value="updateField({ comment: $event })" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.placeholder') }}</label>
          <Input :value="strVal(selectedField.placeholder)" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ placeholder: $event })" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.helpText') }}</label>
          <Input :value="strVal(selectedField.help_text)" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ help_text: $event })" />
        </div>
      </div>
    </div>

    <Divider class="!my-2" />

    <div>
      <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.database') }}</div>
      <div class="flex flex-col gap-3">
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.type') }}</label>
          <Select :value="selectedField.type" class="w-full" :options="typeOptions" :placeholder="$t('admin.system.codegen.property.placeholderSelectType')" @change="onTypeChange" />
        </div>
        <div v-if="selectedField.type === 'String'">
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.length') }}</label>
          <InputNumber :value="selectedField.max_length" :min="1" class="w-full" :placeholder="$t('admin.system.codegen.property.placeholderExampleLength')" @update:value="updateField({ max_length: $event })" />
        </div>
        <template v-if="selectedField.type === 'Decimal'">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.precision') }}</label>
            <InputNumber :value="selectedField.precision ?? 10" :min="1" :max="65" class="w-full" @update:value="updateField({ precision: $event })" />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.scale') }}</label>
            <InputNumber :value="selectedField.scale ?? 2" :min="0" :max="30" class="w-full" @update:value="updateField({ scale: $event })" />
          </div>
        </template>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.defaultValue') }}</label>
          <Input :value="strVal(selectedField.default)" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ default: $event })" />
        </div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.dbDefault') }}</label>
          <Input :value="strVal(selectedField.db_default)" :placeholder="$t('admin.system.codegen.property.placeholderDbDefault')" @update:value="updateField({ db_default: $event })" />
        </div>
        <div class="flex flex-wrap gap-4">
          <Checkbox :checked="selectedField.required" @update:checked="updateField({ required: $event })">
            {{ $t('admin.system.codegen.property.required') }}
          </Checkbox>
          <Checkbox :checked="selectedField.nullable" @update:checked="updateField({ nullable: $event })">
            {{ $t('admin.system.codegen.property.nullable') }}
          </Checkbox>
          <Checkbox :checked="selectedField.unique" @update:checked="updateField({ unique: $event })">
            {{ $t('admin.system.codegen.property.unique') }}
          </Checkbox>
          <Checkbox :checked="selectedField.index" @update:checked="updateField({ index: $event })">
            {{ $t('admin.system.codegen.property.index') }}
          </Checkbox>
        </div>
      </div>
    </div>

    <Divider class="!my-2" />

    <div>
      <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.formList') }}</div>
      <div class="flex flex-col gap-3">
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.component') }}</label>
          <Select :value="getFormComponent()" class="w-full" :options="componentOptions" :placeholder="$t('admin.system.codegen.property.placeholderSelectComponent')" @change="setFormComponent" />
        </div>
        <div v-if="getFormComponent() === 'RichText'" class="flex flex-wrap gap-4">
          <Checkbox
            :checked="(selectedField.form as Record<string, unknown>)?.ai !== false"
            @update:checked="(v: boolean) => updateField({ form: { ...(selectedField.form || {}), ai: v } })"
          >
            {{ $t('admin.system.codegen.property.richTextAi') }}
          </Checkbox>
        </div>
        <div class="flex flex-wrap gap-4">
          <Checkbox :checked="selectedField.insertable !== false" @update:checked="updateField({ insertable: $event })">
            {{ $t('admin.system.codegen.property.insertable') }}
          </Checkbox>
          <Checkbox :checked="selectedField.editable !== false" @update:checked="updateField({ editable: $event })">
            {{ $t('admin.system.codegen.property.editable') }}
          </Checkbox>
          <Checkbox :checked="selectedField.list_visible !== false" @update:checked="updateField({ list_visible: $event })">
            {{ $t('admin.system.codegen.property.listVisible') }}
          </Checkbox>
          <Checkbox :checked="selectedField.filterable" @update:checked="updateField({ filterable: $event })">
            {{ $t('admin.system.codegen.property.filterable') }}
          </Checkbox>
          <Checkbox :checked="selectedField.sortable" @update:checked="updateField({ sortable: $event })">
            {{ $t('admin.system.codegen.property.sortable') }}
          </Checkbox>
        </div>
        <div v-if="selectedField.filterable" class="flex items-center gap-2">
          <label class="shrink-0 text-xs">{{ $t('admin.system.codegen.property.queryType') }}</label>
          <Select
            :value="(selectedField.form?.queryType as string) || (selectedField.query_type as string)"
            class="flex-1"
            :options="queryTypeOptionsComputed"
            :placeholder="$t('admin.system.codegen.property.placeholderQueryTypeDefault')"
            @change="(v: string) => updateField({ form: { ...(selectedField.form || {}), queryType: v }, query_type: v })"
          />
          <Tooltip :title="$t('admin.system.codegen.property.queryTypeHelp')">
            <IconifyIcon icon="lucide:info" class="size-4 text-muted-foreground" />
          </Tooltip>
        </div>
        <div v-if="['String', 'Text', 'Integer', 'Float', 'Decimal'].includes(selectedField.type)" class="text-muted-foreground mt-2 text-xs font-medium">{{ $t('admin.system.codegen.property.validation') }}</div>
        <div v-if="['String', 'Text'].includes(selectedField.type)" class="grid grid-cols-2 gap-2">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.minLength') }}</label>
            <InputNumber :value="selectedField.min_length" :min="0" class="w-full" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ min_length: $event })" />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.maxLength') }}</label>
            <InputNumber :value="selectedField.max_length" :min="1" class="w-full" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ max_length: $event })" />
          </div>
        </div>
        <div v-if="['Integer', 'Float', 'Decimal'].includes(selectedField.type)" class="grid grid-cols-2 gap-2">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.minValue') }}</label>
            <InputNumber :value="selectedField.min_value" class="w-full" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ min_value: $event })" />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.maxValue') }}</label>
            <InputNumber :value="selectedField.max_value" class="w-full" :placeholder="$t('admin.system.codegen.property.placeholderOptional')" @update:value="updateField({ max_value: $event })" />
          </div>
        </div>
        <div v-if="['String', 'Text'].includes(selectedField.type)">
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.pattern') }}</label>
          <Select :value="selectedField.pattern || ''" class="w-full mb-2" :options="patternOptions" allow-clear @change="(v: string) => updateField({ pattern: v || undefined })" />
          <div v-if="(selectedField.pattern || '') === 'custom'" class="mt-1">
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.patternRegex') }}</label>
            <Input
              :value="strVal(selectedField.pattern_regex || selectedField.patternRegex)"
              :placeholder="$t('admin.system.codegen.property.placeholderPatternRegex')"
              allow-clear
              @update:value="updateField({ pattern_regex: $event || undefined, patternRegex: $event || undefined })"
            />
          </div>
        </div>
      </div>
    </div>

    <template v-if="selectedField.type === 'Enum'">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.enum') }}</div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.dictCode') }}</label>
            <Input
              :value="strVal(selectedField.dict_code)"
              :placeholder="$t('admin.system.codegen.property.placeholderDictCode')"
              allow-clear
              @update:value="updateField({ dict_code: $event || undefined })"
            />
            <div class="text-muted-foreground mt-1 text-xs">{{ $t('admin.system.codegen.property.dictCodeHelp') }}</div>
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.enumRender') }}</label>
            <Select
              :value="(selectedField.form?.enumRender as string) || selectedField.enum_render || 'select'"
              class="w-full"
              :options="enumRenderOptions"
              @change="(v: string) => updateField({ form: { ...(selectedField.form || {}), enumRender: v }, enum_render: v })"
            />
          </div>
          <EnumValuesEditor :model-value="selectedField.enum_values || []" @update:model-value="updateField({ enum_values: $event })" />
        </div>
      </div>
    </template>

    <template v-if="selectedField.type === 'TreeSelect'">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.relation') }}</div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.relationTable') }}</label>
            <Select
              :value="selectedField.relation_table"
              class="w-full"
              :options="tableOptions"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationTable')"
              @change="(v: string) => updateField({ relation_table: v })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.displayField') }}</label>
            <Select
              :value="selectedField.relation_display || selectedField.relation_display_field || 'name'"
              class="w-full"
              :options="displayFieldOptions"
              :loading="displayFieldLoading"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationDisplay')"
              allow-clear
              @change="(val: string) => updateField({ relation_display: val || undefined, relation_display_field: val || undefined })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.valueField') }}</label>
            <Input :value="strVal(selectedField.relation_value_field || 'id')" :placeholder="$t('admin.system.codegen.property.placeholderRelationValueField')" @update:value="updateField({ relation_value_field: $event })" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="selectedField.type === 'ForeignKey'">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.relation') }}</div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.relationTable') }}</label>
            <Select
              :value="selectedField.relation_table"
              class="w-full"
              :options="tableOptions"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationTable')"
              @change="(v: string) => updateField({ relation_table: v })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.displayField') }}</label>
            <Select
              :value="selectedField.relation_display || selectedField.relation_display_field || 'name'"
              class="w-full"
              :options="displayFieldOptions"
              :loading="displayFieldLoading"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationDisplay')"
              allow-clear
              @change="(val: string) => updateField({ relation_display: val || undefined, relation_display_field: val || undefined })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.valueField') }}</label>
            <Input :value="strVal(selectedField.relation_value_field || 'id')" :placeholder="$t('admin.system.codegen.property.placeholderRelationValueField')" @update:value="updateField({ relation_value_field: $event })" />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.relationMode') }}</label>
            <Select
              :value="selectedField.relation_mode || 'select'"
              class="w-full"
              :options="relationModeOptions"
              @change="(v: string) => updateField({ relation_mode: v })"
            />
          </div>
          <Checkbox :checked="selectedField.multiple" @update:checked="updateField({ multiple: $event })">
            {{ $t('admin.system.codegen.property.multiple') }}
          </Checkbox>
        </div>
      </div>
    </template>

    <template v-if="['UserSelect', 'DeptSelect'].includes(selectedField.type)">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.relation') }}</div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.relationTable') }}</label>
            <Select
              :value="selectedField.relation_table"
              class="w-full"
              :options="tableOptions"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationTable')"
              @change="(v: string) => updateField({ relation_table: v })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.displayField') }}</label>
            <Select
              :value="selectedField.relation_display || selectedField.relation_display_field || 'name'"
              class="w-full"
              :options="displayFieldOptions"
              :loading="displayFieldLoading"
              show-search
              :filter-option="(input: string, opt: { value: string }) => opt.value?.toLowerCase().includes(input?.toLowerCase())"
              :placeholder="$t('admin.system.codegen.property.placeholderRelationDisplay')"
              allow-clear
              @change="(val: string) => updateField({ relation_display: val || undefined, relation_display_field: val || undefined })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.valueField') }}</label>
            <Input :value="strVal(selectedField.relation_value_field || 'id')" :placeholder="$t('admin.system.codegen.property.placeholderRelationValueField')" @update:value="updateField({ relation_value_field: $event })" />
          </div>
        </div>
      </div>
    </template>

    <template v-if="selectedField.type === 'Cascader'">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.cascaderOptions') }}</div>
        <div>
          <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.placeholderCascaderOptions') }}</label>
          <Input.TextArea
            :value="typeof selectedField.cascader_options === 'string' ? selectedField.cascader_options : JSON.stringify(selectedField.cascader_options || [], null, 2)"
            :placeholder="$t('admin.system.codegen.property.placeholderCascaderOptions')"
            :rows="4"
            @update:value="onCascaderOptionsChange"
          />
        </div>
      </div>
    </template>

    <template v-if="['Image', 'ImageUpload', 'File', 'FilePicker', 'Images', 'Files'].includes(selectedField.type) || getFormComponent() === 'ImageUpload' || getFormComponent() === 'FilePicker'">
      <Divider class="!my-2" />
      <div>
        <div class="text-muted-foreground mb-2 text-xs font-medium">{{ $t('admin.system.codegen.property.upload') }}</div>
        <div class="flex flex-col gap-3">
          <Checkbox :checked="selectedField.multiple" @update:checked="updateField({ multiple: $event })">
            {{ $t('admin.system.codegen.property.multiple') }}
          </Checkbox>
          <div>
            <label class="mb-1 block text-xs">{{ $t('admin.system.codegen.property.maxCount') }}</label>
            <InputNumber :value="selectedField.max_count ?? 9" :min="1" class="w-full" @update:value="updateField({ max_count: $event })" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
