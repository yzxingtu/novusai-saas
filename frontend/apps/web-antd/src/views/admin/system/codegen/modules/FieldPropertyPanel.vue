<script lang="ts" setup>
/**
 * 字段属性面板 / Field Property Panel
 *
 * 右侧属性面板，选中字段时显示
 */
import { computed, onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Checkbox,
  Input,
  InputNumber,
  message,
  Select,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  getCodegenComponentsApi,
  getCodegenDbColumnsApi,
  getCodegenDbTablesApi,
  getCodegenTypesApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import EnumValuesEditor from './EnumValuesEditor.vue';
import { getComponent } from './field-utils';
import {
  inferFieldConfig,
  inferFieldConfigForMerge,
  inferRelationTable,
} from './infer';

defineOptions({ name: 'FieldPropertyPanel' });

const store = useCodegenBuilderStore();

type BuilderField = Record<string, unknown>;
type SelectOption = { label: string; value: string };
type EnumValueItem = { label_en?: string; label_zh?: string; value: string };

const FIELD_ICON_MAP: Record<string, string> = {
  ApiSelect: 'lucide:link',
  ApiTreeSelect: 'lucide:git-branch',
  Cascader: 'lucide:map-pin',
  CodeEditor: 'lucide:code-2',
  ColorPicker: 'lucide:palette',
  DictSelect: 'lucide:book-open',
  FilePicker: 'lucide:file',
  ImageUpload: 'lucide:image',
  Rate: 'lucide:star',
  RichText: 'lucide:file-text',
  Slider: 'lucide:sliders-horizontal',
  TimePicker: 'lucide:clock',
  input: 'lucide:type',
  number: 'lucide:hash',
  password: 'lucide:lock',
  select: 'lucide:list',
  switch: 'lucide:toggle-left',
  textarea: 'lucide:align-left',
};

function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  return Boolean(value);
}

function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : undefined;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function filterOptionByValue(input: string, option?: { value?: unknown }) {
  return asString(option?.value).toLowerCase().includes(input.toLowerCase());
}

const typeOptions = ref<SelectOption[]>([]);
const componentOptions = ref<SelectOption[]>([]);
const tableOptions = ref<SelectOption[]>([]);
const displayFieldOptions = ref<SelectOption[]>([]);
const displayFieldLoading = ref(false);

const selectedField = computed<BuilderField | null>(() => {
  const key = store.selectedFieldKey;
  if (!key) return null;
  const fields = (store.configJson.fields as BuilderField[]) || [];
  return fields.find((f) => f.__key === key || f.name === key) ?? null;
});

const selectedFieldForm = computed(() => asRecord(selectedField.value?.form));
const selectedFieldType = computed(() => asString(selectedField.value?.type));
const isDivider = computed(
  () =>
    selectedField.value?.type === '__divider__' || selectedField.value?.divider,
);
const selectedFormComponent = computed(() => getFormComponent());
const selectedFieldLabel = computed(
  () =>
    asString(selectedField.value?.display_name) ||
    asString(selectedField.value?.display_name_en) ||
    asString(selectedField.value?.name),
);
const selectedFieldIcon = computed(
  () => FIELD_ICON_MAP[selectedFormComponent.value] || 'lucide:circle-dot',
);
const summaryTags = computed(() =>
  [selectedFieldType.value, selectedFormComponent.value].filter(Boolean),
);

async function loadTypes() {
  try {
    const types = await getCodegenTypesApi();
    typeOptions.value = types.map((t) => ({ label: t.type, value: t.type }));
  } catch {
    typeOptions.value = [];
  }
}

async function loadComponents() {
  try {
    const comps = await getCodegenComponentsApi();
    componentOptions.value = comps.map((c) => ({
      label: c.label || c.name,
      value: c.name,
    }));
  } catch {
    componentOptions.value = [];
  }
}

async function loadTables() {
  try {
    const tables = await getCodegenDbTablesApi();
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
  [() => selectedField.value?.relation_table, () => tableOptions.value],
  async ([table, tables]) => {
    const tableName = asString(table);
    if (!tableName) {
      displayFieldOptions.value = [];
      return;
    }
    if (!tables.some((item) => item.value === tableName)) {
      displayFieldOptions.value = [];
      return;
    }
    displayFieldLoading.value = true;
    try {
      const cols = await getCodegenDbColumnsApi(tableName);
      displayFieldOptions.value = cols.map((c) => ({
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

const queryTypeOptionsComputed = computed(() =>
  [
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
  ].map((o) => ({ label: $t(o.labelKey), value: o.value })),
);

const enumRenderOptions = computed(() => [
  {
    label: $t('admin.system.codegen.property.enumRenderSelect'),
    value: 'select',
  },
  {
    label: $t('admin.system.codegen.property.enumRenderRadio'),
    value: 'radio',
  },
  {
    label: $t('admin.system.codegen.property.enumRenderCheckbox'),
    value: 'checkbox',
  },
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
  {
    label: $t('admin.system.codegen.property.modeTreeSelect'),
    value: 'treeSelect',
  },
  { label: $t('admin.system.codegen.property.modeModal'), value: 'modal' },
]);

function hasRelationMetadata(field: BuilderField | null): boolean {
  if (!field) return false;
  return Boolean(
    asString(field.relation_table) ||
    asString(field.relation_display) ||
    asString(field.relation_display_field) ||
    asString(field.relation_value_field),
  );
}

const showTreeRelationConfig = computed(() => {
  return (
    selectedFieldType.value === 'TreeSelect' ||
    selectedFormComponent.value === 'ApiTreeSelect'
  );
});

const showUserRelationConfig = computed(
  () => selectedFieldType.value === 'UserSelect',
);

const showSelectRelationConfig = computed(() => {
  if (showTreeRelationConfig.value || showUserRelationConfig.value)
    return false;
  return (
    selectedFieldType.value === 'ForeignKey' ||
    selectedFormComponent.value === 'ApiSelect' ||
    hasRelationMetadata(selectedField.value)
  );
});

const inferredComponent = computed(() => {
  const name = asString(selectedField.value?.name);
  if (!name) return null;
  const c = inferFieldConfig(name);
  return c?.component || null;
});

const showInferHint = computed(() => !!selectedField.value?._auto_detected);
const showRecommend = computed(() => {
  const f = selectedField.value;
  if (!f || !inferredComponent.value) return false;
  const cur =
    asString(asRecord(f.form).component) ||
    asString(f.form_component) ||
    'input';
  return cur !== inferredComponent.value;
});
const recommendMessage = computed(() => {
  const comp = inferredComponent.value;
  if (!comp || typeof comp !== 'string') return '';
  return $t('admin.system.codegen.property.recommend', { component: comp });
});

function updateField(patch: Partial<BuilderField>) {
  if (!selectedField.value) return;
  const key =
    asString(selectedField.value.__key) || asString(selectedField.value.name);
  const fields = [...((store.configJson.fields as BuilderField[]) || [])];
  const idx = fields.findIndex(
    (f) => asString(f.__key) === key || asString(f.name) === key,
  );
  if (idx === -1) return;
  const nextPatch: BuilderField = { ...patch };
  if (patch.form && typeof patch.form === 'object') {
    nextPatch.form = {
      ...asRecord(fields[idx]?.form),
      ...asRecord(patch.form),
    };
  }
  if (patch.required === true) nextPatch.nullable = false;
  if (patch.nullable === true) nextPatch.required = false;
  fields[idx] = { ...fields[idx], ...nextPatch };
  store.updateConfig({ fields });
}

function onNameChange(name: string) {
  const trimmed = (name || '').trim();
  const field = selectedField.value;
  if (!field) return;
  if (trimmed) {
    const allFields = (store.configJson.fields as BuilderField[]) || [];
    const otherWithSameName = allFields.find(
      (f) =>
        f.__key !== field.__key &&
        asString(f.name).toLowerCase() === trimmed.toLowerCase(),
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
  const patch: BuilderField = { ...inferred };
  if (inferred.type === 'ForeignKey') {
    patch.relation_table = inferRelationTable(trimmed) || '';
    patch.relation_display = 'name';
  }
  const form = asRecord(field.form);
  if (inferred.form && typeof inferred.form === 'object') {
    patch.form = { ...form, ...asRecord(inferred.form) };
  }
  updateField(patch);
}

function getFormComponent(): string {
  const f = selectedField.value;
  const form = asRecord(f?.form);
  return (
    asString(form.component) ||
    asString(f?.form_component) ||
    getComponent(f || {})
  );
}

function setFormComponent(value: unknown) {
  const form = asRecord(selectedField.value?.form);
  const component = asString(value) || undefined;
  updateField({ form: { ...form, component } });
}

function applyRecommendedConfig() {
  const field = selectedField.value;
  const name = asString(field?.name);
  if (!field || !name) return;

  const inferred = inferFieldConfigForMerge(name);
  const patch: BuilderField = { ...inferred };
  if (inferred.type === 'ForeignKey') {
    patch.relation_table =
      inferRelationTable(name) || asString(field.relation_table);
    patch.relation_display = asString(field.relation_display) || 'name';
  }
  if (inferred.form && typeof inferred.form === 'object') {
    patch.form = { ...asRecord(field.form), ...asRecord(inferred.form) };
  }
  updateField(patch);
}

function onTypeChange(value: unknown) {
  const nextType = asString(value);
  const patch: BuilderField = { type: nextType };
  const curType = selectedFieldType.value;
  if (nextType !== 'Enum' && curType === 'Enum') {
    patch.enum_values = undefined;
    patch.dict_code = undefined;
    patch.enum_render = undefined;
  }
  if (
    !['DeptSelect', 'ForeignKey', 'TreeSelect', 'UserSelect'].includes(
      nextType,
    ) &&
    (['DeptSelect', 'ForeignKey', 'TreeSelect', 'UserSelect'].includes(
      curType,
    ) ||
      ['ApiSelect', 'ApiTreeSelect'].includes(selectedFormComponent.value) ||
      hasRelationMetadata(selectedField.value))
  ) {
    patch.relation_table = undefined;
    patch.relation_display = undefined;
    patch.relation_display_field = undefined;
    patch.relation_value_field = undefined;
    patch.relation_mode = undefined;
    patch.multiple = undefined;
  }
  if (nextType !== 'Cascader' && curType === 'Cascader') {
    patch.cascader_options = undefined;
  }
  const uploadTypes = new Set([
    'File',
    'FilePicker',
    'Files',
    'Image',
    'Images',
    'ImageUpload',
  ]);
  if (!uploadTypes.has(nextType) && uploadTypes.has(curType)) {
    patch.multiple = undefined;
    patch.max_count = undefined;
  }
  if (nextType === 'UserSelect' && !selectedField.value?.relation_table) {
    patch.relation_table = 'users';
    patch.relation_display = 'name';
  }
  if (nextType === 'DeptSelect' && !selectedField.value?.relation_table) {
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
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  return '';
}

function getEnumValues(field: BuilderField): EnumValueItem[] {
  const values = field.enum_values;
  if (!Array.isArray(values)) return [];
  const normalized: EnumValueItem[] = [];
  for (const value of values) {
    if (typeof value !== 'object' || value === null) continue;
    const item = value as Record<string, unknown>;
    normalized.push({
      label_en: asString(item.label_en) || undefined,
      label_zh: asString(item.label_zh) || undefined,
      value: asString(item.value),
    });
  }
  return normalized;
}
</script>

<template>
  <div
    v-if="!selectedField"
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
  <div
    v-else-if="isDivider"
    class="flex flex-1 flex-col gap-3 overflow-y-auto p-3"
  >
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
        :value="strVal(selectedField.divider_title || selectedField.title)"
        :placeholder="
          $t('admin.system.codegen.palette.dividerTitlePlaceholder')
        "
        @update:value="updateField({ divider_title: $event, title: $event })"
      />
    </div>
  </div>
  <div v-else class="flex flex-1 flex-col overflow-hidden">
    <div class="border-b border-border/70 px-3 py-3">
      <div class="flex items-start justify-between gap-3">
        <div class="flex min-w-0 items-start gap-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted/20 ring-1 ring-border/70"
          >
            <IconifyIcon
              :icon="selectedFieldIcon"
              class="size-4.5 text-foreground"
            />
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-foreground">
              {{
                selectedFieldLabel ||
                $t('admin.system.codegen.property.unnamed')
              }}
            </div>
            <div class="mt-1 truncate font-mono text-xs text-muted-foreground">
              {{ selectedField.name || 'field' }}
            </div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <Tag
                v-for="tag in summaryTags"
                :key="tag"
                class="!mr-0 !rounded-full"
              >
                {{ tag }}
              </Tag>
              <Tag
                v-if="selectedField._auto_detected"
                color="success"
                class="!mr-0 !rounded-full"
              >
                {{ $t('admin.system.codegen.field.autoDetected') }}
              </Tag>
            </div>
          </div>
        </div>
        <Button
          v-if="showRecommend"
          size="small"
          type="primary"
          ghost
          @click="applyRecommendedConfig"
        >
          {{ $t('admin.system.codegen.property.applyRecommend') }}
        </Button>
      </div>

      <Alert
        v-if="showInferHint"
        type="success"
        show-icon
        class="mt-3 !py-1 text-xs"
        :message="$t('admin.system.codegen.property.inferHint')"
      />
      <Alert
        v-else-if="
          showRecommend &&
          typeof recommendMessage === 'string' &&
          recommendMessage.trim()
        "
        type="info"
        show-icon
        class="mt-3 !py-1 text-xs"
        :message="recommendMessage"
      />
    </div>

    <div class="border-b border-border/60 px-3 py-2.5">
      <div class="grid grid-cols-2 gap-1.5">
        <div
          class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
        >
          <span class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.property.required') }}
          </span>
          <Switch
            size="small"
            :checked="asBoolean(selectedField.required)"
            @update:checked="
              (value) => updateField({ required: asBoolean(value) })
            "
          />
        </div>
        <div
          class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
        >
          <span class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.property.nullable') }}
          </span>
          <Switch
            size="small"
            :checked="asBoolean(selectedField.nullable)"
            @update:checked="
              (value) => updateField({ nullable: asBoolean(value) })
            "
          />
        </div>
        <div
          class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
        >
          <span class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.property.listVisible') }}
          </span>
          <Switch
            size="small"
            :checked="selectedField.list_visible !== false"
            @update:checked="
              (value) => updateField({ list_visible: asBoolean(value) })
            "
          />
        </div>
        <div
          class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
        >
          <span class="text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.property.filterable') }}
          </span>
          <Switch
            size="small"
            :checked="asBoolean(selectedField.filterable)"
            @update:checked="
              (value) => updateField({ filterable: asBoolean(value) })
            "
          />
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-3">
      <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
        <div class="mb-2 text-xs font-medium text-muted-foreground">
          {{ $t('admin.system.codegen.property.basic') }}
        </div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.fieldName')
            }}</label>
            <Input
              :value="strVal(selectedField.name)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderSnakeCase')
              "
              @update:value="onNameChange"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.displayNameZh')
            }}</label>
            <Input
              :value="strVal(selectedField.display_name)"
              :placeholder="$t('admin.system.codegen.property.placeholderZh')"
              @update:value="updateField({ display_name: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.displayNameEn')
            }}</label>
            <Input
              :value="strVal(selectedField.display_name_en)"
              :placeholder="$t('admin.system.codegen.property.placeholderEn')"
              @update:value="updateField({ display_name_en: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.comment')
            }}</label>
            <Input
              :value="strVal(selectedField.comment)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderDbComment')
              "
              @update:value="updateField({ comment: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.placeholder')
            }}</label>
            <Input
              :value="strVal(selectedField.placeholder)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ placeholder: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.helpText')
            }}</label>
            <Input
              :value="strVal(selectedField.help_text)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ help_text: $event })"
            />
          </div>
        </div>
      </section>

      <div class="h-2"></div>

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
          <div v-if="selectedFieldType === 'String'">
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.length')
            }}</label>
            <InputNumber
              :value="asNumberOrUndefined(selectedField.max_length)"
              :min="1"
              class="w-full"
              :placeholder="
                $t('admin.system.codegen.property.placeholderExampleLength')
              "
              @update:value="
                (value) =>
                  updateField({ max_length: asNumberOrUndefined(value) })
              "
            />
          </div>
          <template v-if="selectedFieldType === 'Decimal'">
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.precision')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.precision) ?? 10"
                :min="1"
                :max="65"
                class="w-full"
                @update:value="
                  (value) =>
                    updateField({ precision: asNumberOrUndefined(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.scale')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.scale) ?? 2"
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
              :value="strVal(selectedField.default)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ default: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.dbDefault')
            }}</label>
            <Input
              :value="strVal(selectedField.db_default)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderDbDefault')
              "
              @update:value="updateField({ db_default: $event })"
            />
          </div>
          <div class="flex flex-wrap gap-4">
            <Checkbox
              :checked="asBoolean(selectedField.unique)"
              @update:checked="
                (value) => updateField({ unique: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.unique') }}
            </Checkbox>
            <Checkbox
              :checked="asBoolean(selectedField.index)"
              @update:checked="
                (value) => updateField({ index: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.index') }}
            </Checkbox>
          </div>
        </div>
      </section>

      <div class="h-2"></div>

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
          <div
            v-if="selectedFormComponent === 'RichText'"
            class="flex flex-wrap gap-4"
          >
            <Checkbox
              :checked="selectedFieldForm.ai !== false"
              @update:checked="
                (value) =>
                  updateField({
                    form: { ...selectedFieldForm, ai: asBoolean(value) },
                  })
              "
            >
              {{ $t('admin.system.codegen.property.richTextAi') }}
            </Checkbox>
          </div>
          <div class="flex flex-wrap gap-4">
            <Checkbox
              :checked="selectedField.insertable !== false"
              @update:checked="
                (value) => updateField({ insertable: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.insertable') }}
            </Checkbox>
            <Checkbox
              :checked="selectedField.editable !== false"
              @update:checked="
                (value) => updateField({ editable: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.editable') }}
            </Checkbox>
            <Checkbox
              :checked="asBoolean(selectedField.sortable)"
              @update:checked="
                (value) => updateField({ sortable: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.sortable') }}
            </Checkbox>
          </div>
          <div
            v-if="asBoolean(selectedField.filterable)"
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
            v-if="
              ['String', 'Text', 'Integer', 'Float', 'Decimal'].includes(
                selectedFieldType,
              )
            "
            class="mt-2 text-xs font-medium text-muted-foreground"
          >
            {{ $t('admin.system.codegen.property.validation') }}
          </div>
          <div
            v-if="['String', 'Text'].includes(selectedFieldType)"
            class="grid grid-cols-2 gap-2"
          >
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.minLength')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.min_length)"
                :min="0"
                class="w-full"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderOptional')
                "
                @update:value="
                  (value) =>
                    updateField({ min_length: asNumberOrUndefined(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.maxLength')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.max_length)"
                :min="1"
                class="w-full"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderOptional')
                "
                @update:value="
                  (value) =>
                    updateField({ max_length: asNumberOrUndefined(value) })
                "
              />
            </div>
          </div>
          <div
            v-if="['Integer', 'Float', 'Decimal'].includes(selectedFieldType)"
            class="grid grid-cols-2 gap-2"
          >
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.minValue')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.min_value)"
                class="w-full"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderOptional')
                "
                @update:value="
                  (value) =>
                    updateField({ min_value: asNumberOrUndefined(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.maxValue')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.max_value)"
                class="w-full"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderOptional')
                "
                @update:value="
                  (value) =>
                    updateField({ max_value: asNumberOrUndefined(value) })
                "
              />
            </div>
          </div>
          <div v-if="['String', 'Text'].includes(selectedFieldType)">
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.pattern')
            }}</label>
            <Select
              :value="asString(selectedField.pattern)"
              class="mb-2 w-full"
              :options="patternOptions"
              allow-clear
              @change="
                (value) =>
                  updateField({ pattern: asString(value) || undefined })
              "
            />
            <div
              v-if="asString(selectedField.pattern) === 'custom'"
              class="mt-1"
            >
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.patternRegex')
              }}</label>
              <Input
                :value="
                  strVal(
                    selectedField.pattern_regex || selectedField.patternRegex,
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

      <template v-if="selectedFieldType === 'Enum'">
        <div class="h-2"></div>
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
                :value="strVal(selectedField.dict_code)"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderDictCode')
                "
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
                  asString(selectedField.enum_render) ||
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
              :model-value="getEnumValues(selectedField)"
              @update:model-value="updateField({ enum_values: $event })"
            />
          </div>
        </section>
      </template>

      <template v-if="showTreeRelationConfig">
        <div class="h-2"></div>
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
                :value="asString(selectedField.relation_table)"
                class="w-full"
                :options="tableOptions"
                show-search
                :filter-option="filterOptionByValue"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderRelationTable')
                "
                @change="
                  (value) => updateField({ relation_table: asString(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.displayField')
              }}</label>
              <Select
                :value="
                  asString(selectedField.relation_display) ||
                  asString(selectedField.relation_display_field) ||
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
                :value="strVal(selectedField.relation_value_field || 'id')"
                :placeholder="
                  $t(
                    'admin.system.codegen.property.placeholderRelationValueField',
                  )
                "
                @update:value="updateField({ relation_value_field: $event })"
              />
            </div>
          </div>
        </section>
      </template>

      <template v-if="showSelectRelationConfig">
        <div class="h-2"></div>
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
                :value="asString(selectedField.relation_table)"
                class="w-full"
                :options="tableOptions"
                show-search
                :filter-option="filterOptionByValue"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderRelationTable')
                "
                @change="
                  (value) => updateField({ relation_table: asString(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.displayField')
              }}</label>
              <Select
                :value="
                  asString(selectedField.relation_display) ||
                  asString(selectedField.relation_display_field) ||
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
                :value="strVal(selectedField.relation_value_field || 'id')"
                :placeholder="
                  $t(
                    'admin.system.codegen.property.placeholderRelationValueField',
                  )
                "
                @update:value="updateField({ relation_value_field: $event })"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.relationMode')
              }}</label>
              <Select
                :value="asString(selectedField.relation_mode) || 'select'"
                class="w-full"
                :options="relationModeOptions"
                @change="
                  (value) => updateField({ relation_mode: asString(value) })
                "
              />
            </div>
            <Checkbox
              :checked="asBoolean(selectedField.multiple)"
              @update:checked="
                (value) => updateField({ multiple: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.multiple') }}
            </Checkbox>
          </div>
        </section>
      </template>

      <template v-if="showUserRelationConfig">
        <div class="h-2"></div>
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
                :value="asString(selectedField.relation_table)"
                class="w-full"
                :options="tableOptions"
                show-search
                :filter-option="filterOptionByValue"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderRelationTable')
                "
                @change="
                  (value) => updateField({ relation_table: asString(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.displayField')
              }}</label>
              <Select
                :value="
                  asString(selectedField.relation_display) ||
                  asString(selectedField.relation_display_field) ||
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
                :value="strVal(selectedField.relation_value_field || 'id')"
                :placeholder="
                  $t(
                    'admin.system.codegen.property.placeholderRelationValueField',
                  )
                "
                @update:value="updateField({ relation_value_field: $event })"
              />
            </div>
          </div>
        </section>
      </template>

      <template v-if="selectedFieldType === 'Cascader'">
        <div class="h-2"></div>
        <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('admin.system.codegen.property.cascaderOptions') }}
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.placeholderCascaderOptions')
            }}</label>
            <Input.TextArea
              :value="
                typeof selectedField.cascader_options === 'string'
                  ? selectedField.cascader_options
                  : JSON.stringify(
                      selectedField.cascader_options || [],
                      null,
                      2,
                    )
              "
              :placeholder="
                $t('admin.system.codegen.property.placeholderCascaderOptions')
              "
              :rows="4"
              @update:value="onCascaderOptionsChange"
            />
          </div>
        </section>
      </template>

      <template
        v-if="
          [
            'Image',
            'ImageUpload',
            'File',
            'FilePicker',
            'Images',
            'Files',
          ].includes(selectedFieldType) ||
          selectedFormComponent === 'ImageUpload' ||
          selectedFormComponent === 'FilePicker'
        "
      >
        <div class="h-2"></div>
        <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('admin.system.codegen.property.upload') }}
          </div>
          <div class="flex flex-col gap-3">
            <Checkbox
              :checked="asBoolean(selectedField.multiple)"
              @update:checked="
                (value) => updateField({ multiple: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.multiple') }}
            </Checkbox>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.maxCount')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.max_count) ?? 9"
                :min="1"
                class="w-full"
                @update:value="
                  (value) =>
                    updateField({ max_count: asNumberOrUndefined(value) })
                "
              />
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
