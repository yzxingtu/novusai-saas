<script setup lang="ts">
/**
 * StepFormConfig — Step 4: 表单配置
 *
 * 左侧: 表单字段设置 (组件选择、必填、占比) + 分组管理 + 表单选项 + 条件字段
 * 右侧: FormPreview 实时预览
 */
import { computed, ref } from 'vue';

import {
  Button,
  Card,
  Checkbox,
  Input,
  InputNumber,
  Select,
  Table,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type {
  CrudConfig,
  FieldConfig,
  FormGroup,
} from '../types';

import { FORM_COMPONENT_OPTIONS } from '../constants';

import type { MockDataRow } from '../composables/use-mock-data';

import FormPreview from './FormPreview.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  mockData: MockDataRow[];
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
}>();

const formPreviewRef = ref<InstanceType<typeof FormPreview>>();

// ============================================================
// Field config helpers
// ============================================================

function updateField(name: string, key: keyof FieldConfig, value: unknown) {
  const fields = props.config.fields.map((f) => {
    if (f.name === name) {
      return { ...f, [key]: value };
    }
    return f;
  });
  emit('update:config', { ...props.config, fields });
}

function updateFormConfig(key: string, value: unknown) {
  emit('update:config', {
    ...props.config,
    form_config: { ...props.config.form_config, [key]: value },
  });
}

// ============================================================
// Form component options
// ============================================================

const FORM_COMPONENTS = FORM_COMPONENT_OPTIONS;

const FORM_TYPE_OPTIONS = [
  { label: $t(`${T}.formConfig.formTypeDrawer`), value: 'drawer' },
  { label: $t(`${T}.formConfig.formTypeModal`), value: 'modal' },
];

const CONDITION_TYPE_OPTIONS = [
  { label: $t(`${T}.formConfig.conditionEq`), value: 'eq' },
  { label: $t(`${T}.formConfig.conditionNeq`), value: 'neq' },
  { label: $t(`${T}.formConfig.conditionIn`), value: 'in' },
  { label: $t(`${T}.formConfig.conditionTruthy`), value: 'truthy' },
  { label: $t(`${T}.formConfig.conditionNotEmpty`), value: 'not_empty' },
];

// ============================================================
// Field config table columns
// ============================================================

const fieldConfigCols = computed(() => [
  { title: $t(`${T}.formConfig.fieldName`), dataIndex: 'name', width: 100 },
  { title: $t(`${T}.formConfig.fieldLabel`), dataIndex: 'label_zh', width: 100 },
  { title: $t(`${T}.formConfig.fieldVisible`), dataIndex: 'in_form', width: 60, align: 'center' as const },
  { title: $t(`${T}.formConfig.fieldComponent`), dataIndex: 'form_component', width: 140 },
  { title: $t(`${T}.formConfig.fieldRequired`), dataIndex: 'required', width: 60, align: 'center' as const },
  { title: $t(`${T}.formConfig.fieldColSpan`), dataIndex: 'form_col_span', width: 80 },
]);

// ============================================================
// Groups management
// ============================================================

const groups = computed(() => props.config.form_config.groups ?? []);

function addGroup() {
  const newGroup: FormGroup = {
    title_zh: `${$t(`${T}.formConfig.groupTitle`)} ${groups.value.length + 1}`,
    title_en: `Group ${groups.value.length + 1}`,
    fields: [],
    collapsible: false,
    default_collapsed: false,
  };
  updateFormConfig('groups', [...groups.value, newGroup]);
}

function removeGroup(index: number) {
  const updated = [...groups.value];
  updated.splice(index, 1);
  updateFormConfig('groups', updated.length > 0 ? updated : null);
}

function updateGroup(index: number, key: keyof FormGroup, value: unknown) {
  const updated = groups.value.map((g, i) => {
    if (i === index) {
      return { ...g, [key]: value };
    }
    return g;
  });
  updateFormConfig('groups', updated);
}

// Available fields for group assignment
const formFieldNames = computed(() =>
  props.config.fields
    .filter((f) => f.in_form)
    .map((f) => ({ label: `${f.label_zh || f.name} (${f.name})`, value: f.name })),
);

// ============================================================
// Condition field helpers
// ============================================================

const dependableFields = computed(() =>
  props.config.fields
    .filter((f) => f.in_form)
    .map((f) => ({ label: `${f.label_zh || f.name}`, value: f.name })),
);

function setCondition(fieldName: string, depField: string | null) {
  if (!depField) {
    updateField(fieldName, 'form_depends_on', null);
    return;
  }
  const existing = props.config.fields.find((f) => f.name === fieldName);
  updateField(fieldName, 'form_depends_on', {
    field: depField,
    condition: existing?.form_depends_on?.condition || 'eq',
    value: existing?.form_depends_on?.value ?? true,
  });
}

function updateConditionProp(fieldName: string, key: string, value: unknown) {
  const existing = props.config.fields.find((f) => f.name === fieldName);
  if (!existing?.form_depends_on) return;
  updateField(fieldName, 'form_depends_on', {
    ...existing.form_depends_on,
    [key]: value,
  });
}

// ============================================================
// Preview
// ============================================================

function openPreview() {
  formPreviewRef.value?.open();
}

const singleRow = computed(() => props.mockData[0] ?? { id: 1 });
</script>

<template>
  <div class="flex gap-4" style="min-height: 500px">
    <!-- Left: Config Panel -->
    <div class="w-[520px] flex-shrink-0 space-y-4 overflow-auto" style="max-height: 700px">
      <!-- Field Settings -->
      <Card :title="$t(`${T}.formConfig.fieldSettings`)" size="small">
        <Table
          :columns="fieldConfigCols"
          :data-source="config.fields"
          :pagination="false"
          :scroll="{ x: 540 }"
          bordered
          row-key="name"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'in_form'">
              <Checkbox
                :checked="(record as FieldConfig).in_form"
                @change="(e: { target: { checked: boolean } }) => updateField((record as FieldConfig).name, 'in_form', e.target.checked)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'form_component'">
              <Select
                :value="(record as FieldConfig).form_component"
                :options="FORM_COMPONENTS"
                size="small"
                style="width: 130px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'form_component', val)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'required'">
              <Checkbox
                :checked="(record as FieldConfig).required"
                @change="(e: { target: { checked: boolean } }) => updateField((record as FieldConfig).name, 'required', e.target.checked)"
              />
            </template>

            <template v-else-if="column.dataIndex === 'form_col_span'">
              <InputNumber
                :value="(record as FieldConfig).form_col_span ?? undefined"
                :max="24"
                :min="6"
                :step="6"
                placeholder="24"
                size="small"
                style="width: 70px"
                @change="(val: unknown) => updateField((record as FieldConfig).name, 'form_col_span', val)"
              />
            </template>
          </template>
        </Table>
      </Card>

      <!-- Form Options -->
      <Card :title="$t(`${T}.formConfig.formOptions`)" size="small">
        <div class="grid grid-cols-2 gap-3">
          <div class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">{{ $t(`${T}.formConfig.formType`) }}</span>
            <Select
              :value="config.form_config.form_type"
              :options="FORM_TYPE_OPTIONS"
              size="small"
              style="width: 100px"
              @change="(val: unknown) => updateFormConfig('form_type', val)"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">{{ $t(`${T}.formConfig.drawerWidth`) }}</span>
            <Input
              :value="config.form_config.drawer_width"
              size="small"
              style="width: 80px"
              @change="(e: Event) => updateFormConfig('drawer_width', (e.target as HTMLInputElement).value)"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">{{ $t(`${T}.formConfig.columns`) }}</span>
            <InputNumber
              :value="config.form_config.columns"
              :max="4"
              :min="1"
              size="small"
              style="width: 60px"
              @change="(val: unknown) => updateFormConfig('columns', val)"
            />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm whitespace-nowrap">{{ $t(`${T}.formConfig.labelWidth`) }}</span>
            <InputNumber
              :value="config.form_config.label_width"
              :max="200"
              :min="60"
              :step="10"
              size="small"
              style="width: 70px"
              @change="(val: unknown) => updateFormConfig('label_width', val)"
            />
          </div>
        </div>
      </Card>

      <!-- Group Settings -->
      <Card :title="$t(`${T}.formConfig.groupSettings`)" size="small">
        <div class="space-y-3">
          <div
            v-for="(group, idx) in groups"
            :key="idx"
            class="bg-accent/20 rounded-md p-3"
          >
            <div class="mb-2 flex items-center justify-between">
              <span class="text-sm font-medium">{{ group.title_zh }}</span>
              <span
                class="icon-[lucide--trash-2] text-muted-foreground size-4 cursor-pointer hover:text-red-500"
                @click="removeGroup(idx)"
              />
            </div>
            <div class="grid grid-cols-2 gap-2">
              <Input
                :value="group.title_zh"
                :placeholder="$t(`${T}.formConfig.groupTitle`)"
                size="small"
                @change="(e: Event) => updateGroup(idx, 'title_zh', (e.target as HTMLInputElement).value)"
              />
              <Input
                :value="group.title_en"
                :placeholder="$t(`${T}.formConfig.groupTitleEn`)"
                size="small"
                @change="(e: Event) => updateGroup(idx, 'title_en', (e.target as HTMLInputElement).value)"
              />
            </div>
            <div class="mt-2">
              <Select
                :value="group.fields"
                :options="formFieldNames"
                mode="multiple"
                :placeholder="$t(`${T}.formConfig.groupFields`)"
                size="small"
                style="width: 100%"
                @change="(val: unknown) => updateGroup(idx, 'fields', val)"
              />
            </div>
            <div class="mt-2 flex gap-4">
              <Checkbox
                :checked="group.collapsible"
                @change="(e: { target: { checked: boolean } }) => updateGroup(idx, 'collapsible', e.target.checked)"
              >
                {{ $t(`${T}.formConfig.groupCollapsible`) }}
              </Checkbox>
              <Checkbox
                :checked="group.default_collapsed"
                :disabled="!group.collapsible"
                @change="(e: { target: { checked: boolean } }) => updateGroup(idx, 'default_collapsed', e.target.checked)"
              >
                {{ $t(`${T}.formConfig.groupDefaultCollapsed`) }}
              </Checkbox>
            </div>
          </div>

          <Button size="small" @click="addGroup">
            <template #icon>
              <span class="icon-[lucide--plus] size-3.5" />
            </template>
            {{ $t(`${T}.formConfig.addGroup`) }}
          </Button>
        </div>
      </Card>

      <!-- Conditional Display -->
      <Card :title="$t(`${T}.formConfig.conditionConfig`)" size="small">
        <div class="space-y-2">
          <template v-for="field in config.fields.filter(f => f.in_form)" :key="field.name">
            <div class="flex items-center gap-2">
              <span class="w-24 truncate text-sm">{{ field.label_zh || field.name }}</span>
              <Select
                :value="field.form_depends_on?.field ?? undefined"
                :options="dependableFields.filter(d => d.value !== field.name)"
                :placeholder="$t(`${T}.formConfig.conditionField`)"
                allow-clear
                size="small"
                style="width: 120px"
                @change="(val: unknown) => setCondition(field.name, (val as string) || null)"
              />
              <template v-if="field.form_depends_on">
                <Select
                  :value="field.form_depends_on.condition"
                  :options="CONDITION_TYPE_OPTIONS"
                  size="small"
                  style="width: 90px"
                  @change="(val: unknown) => updateConditionProp(field.name, 'condition', val)"
                />
                <Input
                  v-if="field.form_depends_on.condition === 'eq' || field.form_depends_on.condition === 'neq'"
                  :value="String(field.form_depends_on.value ?? '')"
                  :placeholder="$t(`${T}.formConfig.conditionValue`)"
                  size="small"
                  style="width: 80px"
                  @change="(e: Event) => updateConditionProp(field.name, 'value', (e.target as HTMLInputElement).value)"
                />
              </template>
            </div>
          </template>
        </div>
      </Card>
    </div>

    <!-- Right: Preview -->
    <div class="flex-1 overflow-auto">
      <Card :title="$t(`${T}.formPreview.title`)" size="small">
        <div class="mb-3 flex gap-2">
          <Button size="small" type="primary" @click="openPreview">
            <template #icon>
              <span class="icon-[lucide--eye] size-3.5" />
            </template>
            {{ $t(`${T}.formPreview.createTitle`, { name: config.display_name || config.module }) }}
          </Button>
        </div>

        <div class="text-muted-foreground rounded-md border border-dashed p-8 text-center text-sm">
          <span class="icon-[lucide--form-input] mb-2 size-10 opacity-30" />
          <p>{{ $t(`${T}.formConfig.dragHint`) }}</p>
        </div>
      </Card>

      <FormPreview
        ref="formPreviewRef"
        :config="config"
        :row="singleRow"
        mode="create"
      />
    </div>
  </div>
</template>
