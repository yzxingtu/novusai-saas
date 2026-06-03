import { computed, onMounted, ref, watch } from 'vue';

import { message } from 'ant-design-vue';

import {
  getCodegenComponentsApi,
  getCodegenDbColumnsApi,
  getCodegenDbTablesApi,
  getCodegenTypesApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { getComponent } from '../field-utils';
import {
  inferFieldConfig,
  inferFieldConfigForMerge,
  inferRelationTable,
} from '../infer';

export type BuilderField = Record<string, unknown>;
export type SelectOption = { label: string; value: string };
export type EnumValueItem = {
  label_en?: string;
  label_zh?: string;
  value: string;
};

type CodegenComponentLike = { label?: string; name: string };
type CodegenTypeLike = { type: string };

const FIELD_ICON_MAP: Record<string, string> = {
  ApiSelect: 'lucide:link',
  ApiTreeSelect: 'lucide:git-branch',
  Cascader: 'lucide:map-pin',
  CodeEditor: 'lucide:code-2',
  ColorPicker: 'lucide:palette',
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

export function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  return Boolean(value);
}

export function asNumberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : undefined;
}

export function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

export function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

export function filterOptionByValue(
  input: string,
  option?: { value?: unknown },
) {
  return asString(option?.value).toLowerCase().includes(input.toLowerCase());
}

export function buildTypeOptions(types: CodegenTypeLike[]): SelectOption[] {
  return types.map((item) => ({
    label: item.type,
    value: item.type,
  }));
}

export function buildComponentOptions(
  components: CodegenComponentLike[],
): SelectOption[] {
  return components.map((item) => ({
    label: item.label || item.name,
    value: item.name,
  }));
}

function hasRelationMetadata(field: BuilderField | null): boolean {
  if (!field) return false;
  return Boolean(
    asString(field.relation_table) ||
    asString(field.relation_display) ||
    asString(field.relation_display_field) ||
    asString(field.relation_value_field),
  );
}

export function useFieldPropertyPanel() {
  const store = useCodegenBuilderStore();

  const typeOptions = ref<SelectOption[]>([]);
  const componentOptions = ref<SelectOption[]>([]);
  const tableOptions = ref<SelectOption[]>([]);
  const displayFieldOptions = ref<SelectOption[]>([]);
  const displayFieldLoading = ref(false);

  const selectedField = computed<BuilderField | null>(() => {
    const key = store.selectedFieldKey;
    if (!key) return null;
    const fields = (store.configJson.fields as BuilderField[]) || [];
    return (
      fields.find((field) => field.__key === key || field.name === key) ?? null
    );
  });

  const selectedFieldForm = computed(() => asRecord(selectedField.value?.form));
  const selectedFieldType = computed(() => asString(selectedField.value?.type));
  const isDivider = computed(
    () =>
      selectedField.value?.type === '__divider__' ||
      selectedField.value?.divider,
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
    ].map((item) => ({ label: $t(item.labelKey), value: item.value })),
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
    { label: '-', value: '' },
    { label: $t('admin.system.codegen.property.patternEmail'), value: 'email' },
    { label: $t('admin.system.codegen.property.patternPhone'), value: 'phone' },
    { label: $t('admin.system.codegen.property.patternUrl'), value: 'url' },
    {
      label: $t('admin.system.codegen.property.patternIdCard'),
      value: 'idCard',
    },
    {
      label: $t('admin.system.codegen.property.patternCustom'),
      value: 'custom',
    },
  ]);

  const relationModeOptions = computed(() => [
    { label: $t('admin.system.codegen.property.modeSelect'), value: 'select' },
    {
      label: $t('admin.system.codegen.property.modeTreeSelect'),
      value: 'treeSelect',
    },
    { label: $t('admin.system.codegen.property.modeModal'), value: 'modal' },
  ]);

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
    const inferred = inferFieldConfig(name);
    return inferred?.component || null;
  });
  const showInferHint = computed(() => !!selectedField.value?._auto_detected);
  const showRecommend = computed(() => {
    const field = selectedField.value;
    if (!field || !inferredComponent.value) return false;
    const currentComponent =
      asString(asRecord(field.form).component) ||
      asString(field.form_component) ||
      'input';
    return currentComponent !== inferredComponent.value;
  });
  const recommendMessage = computed(() => {
    const component = inferredComponent.value;
    if (!component || typeof component !== 'string') return '';
    return $t('admin.system.codegen.property.recommend', { component });
  });

  async function loadTypes() {
    try {
      const types = await getCodegenTypesApi();
      typeOptions.value = buildTypeOptions(types);
    } catch {
      typeOptions.value = [];
    }
  }

  async function loadComponents() {
    try {
      const components = await getCodegenComponentsApi();
      componentOptions.value = buildComponentOptions(components);
    } catch {
      componentOptions.value = [];
    }
  }

  async function loadTables() {
    try {
      const tables = await getCodegenDbTablesApi();
      tableOptions.value = tables.map((item) => ({
        label: item.name,
        value: item.name,
      }));
    } catch {
      tableOptions.value = [];
    }
  }

  function updateField(patch: Partial<BuilderField>) {
    if (!selectedField.value) return;
    const key =
      asString(selectedField.value.__key) || asString(selectedField.value.name);
    const fields = [...((store.configJson.fields as BuilderField[]) || [])];
    const index = fields.findIndex(
      (field) => asString(field.__key) === key || asString(field.name) === key,
    );
    if (index === -1) return;
    const nextPatch: BuilderField = { ...patch };
    if (patch.form && typeof patch.form === 'object') {
      nextPatch.form = {
        ...asRecord(fields[index]?.form),
        ...asRecord(patch.form),
      };
    }
    if (patch.required === true) nextPatch.nullable = false;
    if (patch.nullable === true) nextPatch.required = false;
    fields[index] = { ...fields[index], ...nextPatch };
    store.updateConfig({ fields });
  }

  function onNameChange(name: string) {
    const trimmed = (name || '').trim();
    const field = selectedField.value;
    if (!field) return;
    if (trimmed) {
      const allFields = (store.configJson.fields as BuilderField[]) || [];
      const otherWithSameName = allFields.find(
        (item) =>
          item.__key !== field.__key &&
          asString(item.name).toLowerCase() === trimmed.toLowerCase(),
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
    const field = selectedField.value;
    const form = asRecord(field?.form);
    return (
      asString(form.component) ||
      asString(field?.form_component) ||
      getComponent(field || {})
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
    const currentType = selectedFieldType.value;
    if (nextType !== 'Enum' && currentType === 'Enum') {
      patch.enum_values = undefined;
      patch.dict_code = undefined;
      patch.enum_render = undefined;
    }
    if (
      !['DeptSelect', 'ForeignKey', 'TreeSelect', 'UserSelect'].includes(
        nextType,
      ) &&
      (['DeptSelect', 'ForeignKey', 'TreeSelect', 'UserSelect'].includes(
        currentType,
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
    if (nextType !== 'Cascader' && currentType === 'Cascader') {
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
    if (!uploadTypes.has(nextType) && uploadTypes.has(currentType)) {
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

  function onCascaderOptionsChange(value: string) {
    try {
      const parsed = value?.trim() ? JSON.parse(value) : [];
      updateField({ cascader_options: parsed });
    } catch {
      message.warning($t('admin.system.codegen.property.invalidCascaderJson'));
    }
  }

  function strVal(value: unknown): string {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean')
      return String(value);
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
        const columns = await getCodegenDbColumnsApi(tableName);
        displayFieldOptions.value = columns.map((item) => ({
          label: `${item.name}${item.type ? ` (${item.type})` : ''}`,
          value: item.name,
        }));
      } catch {
        displayFieldOptions.value = [];
      } finally {
        displayFieldLoading.value = false;
      }
    },
    { immediate: true },
  );

  return {
    applyRecommendedConfig,
    asBoolean,
    asNumberOrUndefined,
    asString,
    componentOptions,
    displayFieldLoading,
    displayFieldOptions,
    enumRenderOptions,
    filterOptionByValue,
    getEnumValues,
    isDivider,
    onCascaderOptionsChange,
    onNameChange,
    onTypeChange,
    patternOptions,
    queryTypeOptionsComputed,
    recommendMessage,
    relationModeOptions,
    selectedField,
    selectedFieldForm,
    selectedFieldIcon,
    selectedFieldLabel,
    selectedFieldType,
    selectedFormComponent,
    setFormComponent,
    showInferHint,
    showRecommend,
    showSelectRelationConfig,
    showTreeRelationConfig,
    showUserRelationConfig,
    strVal,
    summaryTags,
    tableOptions,
    typeOptions,
    updateField,
  };
}

export type UseFieldPropertyPanelReturn = ReturnType<
  typeof useFieldPropertyPanel
>;
