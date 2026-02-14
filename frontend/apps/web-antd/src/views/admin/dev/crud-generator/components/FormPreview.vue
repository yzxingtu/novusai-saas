<script setup lang="ts">
/**
 * FormPreview — 根据 CrudConfig 实时渲染表单预览
 *
 * 支持: Input/Select/Switch/DatePicker/InputNumber/Textarea/Upload/
 *       RadioGroup/CheckboxGroup/ColorPicker/Rate/Slider/Cascader
 * 支持: 表单分组 (Divider), 条件字段显示/隐藏, 关联下拉 Mock
 */
import { computed, reactive, ref, watch } from 'vue';

import {
  Button,
  Checkbox,
  DatePicker,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Radio,
  Rate,
  Select,
  Slider,
  Switch,
  Upload,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type {
  CrudConfig,
  FieldConfig,
  FormGroup,
} from '../types';

import type { MockDataRow } from '../composables/use-mock-data';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
  row?: MockDataRow;
  mode?: 'create' | 'edit';
}>();

const drawerVisible = ref(false);

function open() {
  drawerVisible.value = true;
}

function close() {
  drawerVisible.value = false;
}

defineExpose({ open, close });

// ============================================================
// Form fields
// ============================================================

const formFields = computed(() =>
  props.config.fields.filter((f) => f.in_form),
);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const formData = reactive<Record<string, any>>({});

// Initialize form data from row (edit mode) or defaults
watch(
  () => [props.row, drawerVisible.value],
  () => {
    if (!drawerVisible.value) return;
    for (const field of formFields.value) {
      if (props.mode === 'edit' && props.row) {
        formData[field.name] = props.row[field.name] ?? field.default ?? undefined;
      } else {
        formData[field.name] = field.default ?? undefined;
      }
    }
  },
  { immediate: true },
);

// ============================================================
// Conditional fields
// ============================================================

function isFieldVisible(field: FieldConfig): boolean {
  if (!field.form_depends_on) return true;

  const dep = field.form_depends_on;
  const depValue = formData[dep.field];

  switch (dep.condition) {
    case 'eq': {
      return depValue === dep.value;
    }
    case 'neq': {
      return depValue !== dep.value;
    }
    case 'in': {
      return Array.isArray(dep.values) && dep.values.includes(depValue);
    }
    case 'not_empty': {
      return depValue !== undefined && depValue !== null && depValue !== '';
    }
    case 'truthy': {
      return !!depValue;
    }
    default: {
      return true;
    }
  }
}

// ============================================================
// Form groups
// ============================================================

const groups = computed(() => {
  const cfg = props.config.form_config.groups;
  if (!cfg || cfg.length === 0) return null;
  return cfg;
});

function getGroupFields(group: FormGroup): FieldConfig[] {
  return formFields.value.filter((f) => group.fields.includes(f.name));
}

const ungroupedFields = computed(() => {
  if (!groups.value) return formFields.value;
  const grouped = new Set(groups.value.flatMap((g) => g.fields));
  return formFields.value.filter((f) => !grouped.has(f.name));
});

// ============================================================
// Enum options for Select/Radio/Checkbox
// ============================================================

function getEnumOptions(field: FieldConfig) {
  if (!field.enum_ref) return [];
  const enumDef = props.config.enums.find((e) => e.name === field.enum_ref);
  if (!enumDef) return [];
  return enumDef.values.map((v) => ({
    label: v.label_zh,
    value: v.value,
  }));
}

// ============================================================
// Mock relation options
// ============================================================

function getRelationOptions(_field: FieldConfig) {
  return Array.from({ length: 10 }, (_, i) => ({
    label: `${$t(`${T}.formPreview.group`)} ${i + 1}`,
    value: i + 1,
  }));
}

// ============================================================
// Title
// ============================================================

const drawerTitle = computed(() => {
  const name = props.config.display_name || props.config.module || '';
  return props.mode === 'edit'
    ? $t(`${T}.formPreview.editTitle`, { name })
    : $t(`${T}.formPreview.createTitle`, { name });
});

const drawerWidth = computed(() => props.config.form_config.drawer_width || '600px');
const formColumns = computed(() => props.config.form_config.columns || 1);
const labelWidth = computed(() => props.config.form_config.label_width || 100);
const isDrawer = computed(() => props.config.form_config.form_type === 'drawer');
</script>

<template>
  <Drawer
    v-if="isDrawer"
    :closable="true"
    :open="drawerVisible"
    :title="drawerTitle"
    :width="drawerWidth"
    @close="close"
  >
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="close">{{ $t(`${T}.formPreview.cancel`) }}</Button>
        <Button type="primary" @click="close">{{ $t(`${T}.formPreview.submit`) }}</Button>
      </div>
    </template>

    <div v-if="formFields.length === 0" class="py-12">
      <Empty :description="$t(`${T}.formPreview.noFields`)" />
    </div>

    <Form
      v-else
      :label-col="{ style: { width: `${labelWidth}px` } }"
      layout="horizontal"
    >
      <!-- Ungrouped fields -->
      <template v-if="!groups">
        <div
          :style="{ gridTemplateColumns: `repeat(${formColumns}, 1fr)` }"
          class="grid gap-x-4"
        >
          <template v-for="field in formFields" :key="field.name">
            <Form.Item
              v-if="isFieldVisible(field)"
              :label="field.label_zh || field.name"
              :required="field.required"
            >
              <!-- Input -->
              <Input
                v-if="field.form_component === 'Input'"
                v-model:value="formData[field.name]"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.placeholder`, { label: field.label_zh })"
                allow-clear
              />

              <!-- Textarea -->
              <Input.TextArea
                v-else-if="field.form_component === 'Textarea'"
                v-model:value="formData[field.name]"
                :auto-size="{ minRows: 3, maxRows: 6 }"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.placeholder`, { label: field.label_zh })"
              />

              <!-- InputNumber -->
              <InputNumber
                v-else-if="field.form_component === 'InputNumber'"
                v-model:value="formData[field.name]"
                :placeholder="field.form_placeholder ?? undefined"
                class="w-full"
              />

              <!-- Select (enum) -->
              <Select
                v-else-if="field.form_component === 'Select'"
                v-model:value="formData[field.name]"
                :options="getEnumOptions(field)"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.selectPlaceholder`, { label: field.label_zh })"
                allow-clear
              />

              <!-- ApiSelect (relation) -->
              <Select
                v-else-if="field.form_component === 'ApiSelect'"
                v-model:value="formData[field.name]"
                :options="getRelationOptions(field)"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.selectPlaceholder`, { label: field.label_zh })"
                allow-clear
                show-search
              />

              <!-- ApiTreeSelect -->
              <Select
                v-else-if="field.form_component === 'ApiTreeSelect'"
                v-model:value="formData[field.name]"
                :options="getRelationOptions(field)"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.selectPlaceholder`, { label: field.label_zh })"
                allow-clear
              />

              <!-- Switch -->
              <Switch
                v-else-if="field.form_component === 'Switch'"
                v-model:checked="formData[field.name]"
              />

              <!-- DatePicker -->
              <DatePicker
                v-else-if="field.form_component === 'DatePicker'"
                v-model:value="formData[field.name]"
                :placeholder="field.form_placeholder ?? undefined"
                class="w-full"
              />

              <!-- RangePicker -->
              <DatePicker.RangePicker
                v-else-if="field.form_component === 'RangePicker'"
                v-model:value="formData[field.name]"
                class="w-full"
              />

              <!-- RadioGroup -->
              <Radio.Group
                v-else-if="field.form_component === 'RadioGroup'"
                v-model:value="formData[field.name]"
                :options="getEnumOptions(field)"
              />

              <!-- CheckboxGroup -->
              <Checkbox.Group
                v-else-if="field.form_component === 'CheckboxGroup'"
                v-model:value="formData[field.name]"
                :options="getEnumOptions(field)"
              />

              <!-- Upload -->
              <Upload
                v-else-if="field.form_component === 'Upload'"
                :max-count="field.upload?.max_count || 1"
                list-type="picture-card"
              >
                <div class="flex flex-col items-center">
                  <span class="icon-[lucide--upload] size-5 opacity-40" />
                  <span class="text-xs opacity-40">Upload</span>
                </div>
              </Upload>

              <!-- Rate -->
              <Rate
                v-else-if="field.form_component === 'Rate'"
                v-model:value="formData[field.name]"
              />

              <!-- Slider -->
              <Slider
                v-else-if="field.form_component === 'Slider'"
                v-model:value="formData[field.name]"
              />

              <!-- ColorPicker (fallback to Input) -->
              <Input
                v-else-if="field.form_component === 'ColorPicker'"
                v-model:value="formData[field.name]"
                placeholder="#000000"
                type="color"
              />

              <!-- JsonEditor fallback -->
              <Input.TextArea
                v-else-if="field.form_component === 'JsonEditor'"
                v-model:value="formData[field.name]"
                :auto-size="{ minRows: 4, maxRows: 10 }"
                class="font-mono"
                placeholder="{ }"
              />

              <!-- RichText fallback -->
              <Input.TextArea
                v-else-if="field.form_component === 'RichText'"
                v-model:value="formData[field.name]"
                :auto-size="{ minRows: 5, maxRows: 12 }"
                placeholder="Rich text editor placeholder"
              />

              <!-- Cascader fallback -->
              <Select
                v-else-if="field.form_component === 'Cascader'"
                v-model:value="formData[field.name]"
                :options="[]"
                :placeholder="field.form_placeholder ?? $t(`${T}.formPreview.selectPlaceholder`, { label: field.label_zh })"
              />

              <!-- Default fallback -->
              <Input
                v-else
                v-model:value="formData[field.name]"
                :placeholder="field.form_placeholder || field.label_zh"
              />

              <!-- Help text -->
              <template v-if="field.form_help" #help>
                {{ field.form_help }}
              </template>
            </Form.Item>
          </template>
        </div>
      </template>

      <!-- Grouped fields -->
      <template v-else>
        <!-- Ungrouped first -->
        <template v-if="ungroupedFields.length > 0">
          <div
            :style="{ gridTemplateColumns: `repeat(${formColumns}, 1fr)` }"
            class="grid gap-x-4"
          >
            <template v-for="field in ungroupedFields" :key="field.name">
              <Form.Item
                v-if="isFieldVisible(field)"
                :label="field.label_zh || field.name"
                :required="field.required"
              >
                <Input
                  v-model:value="formData[field.name]"
                  :placeholder="field.form_placeholder || field.label_zh"
                />
              </Form.Item>
            </template>
          </div>
        </template>

        <!-- Groups -->
        <template v-for="group in groups" :key="group.title_zh">
          <Divider orientation="left" class="!mt-2 !mb-3">
            {{ group.title_zh }}
          </Divider>
          <div
            :style="{ gridTemplateColumns: `repeat(${formColumns}, 1fr)` }"
            class="grid gap-x-4"
          >
            <template v-for="field in getGroupFields(group)" :key="field.name">
              <Form.Item
                v-if="isFieldVisible(field)"
                :label="field.label_zh || field.name"
                :required="field.required"
              >
                <Input
                  v-model:value="formData[field.name]"
                  :placeholder="field.form_placeholder || field.label_zh"
                />
              </Form.Item>
            </template>
          </div>
        </template>
      </template>
    </Form>
  </Drawer>
</template>
