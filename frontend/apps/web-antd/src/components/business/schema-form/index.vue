<script setup lang="ts">
/**
 * JSON Schema → Ant Design Vue 动态表单渲染器
 *
 * 支持字段类型：string, number, integer, boolean, array (enum)
 * 支持格式：password, textarea, uri, email
 * 支持校验：required, pattern, minLength, maxLength, minimum, maximum, enum
 * 支持描述：description → tooltip / extra
 */
import type { FormInstance } from 'ant-design-vue';
import type { Rule } from 'ant-design-vue/es/form';

import { computed, reactive, ref, watch } from 'vue';

import {
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

/** JSON Schema property definition */
interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  format?: string;
  pattern?: string;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  items?: { enum?: unknown[]; type?: string };
}

/** JSON Schema root */
interface JsonSchema {
  type?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
  title?: string;
  description?: string;
}

interface Props {
  schema: JsonSchema | null | undefined;
  modelValue?: Record<string, unknown>;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: () => ({}),
  disabled: false,
});

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>];
}>();

const formRef = ref<FormInstance>();
const formModel = reactive<Record<string, unknown>>({});

/** Sorted property keys */
const propertyKeys = computed<string[]>(() => {
  if (!props.schema?.properties) return [];
  return Object.keys(props.schema.properties);
});

/** Required fields set */
const requiredSet = computed<Set<string>>(() => {
  return new Set(props.schema?.required);
});

/** Initialize form model from schema defaults + modelValue */
function initModel() {
  const properties = props.schema?.properties ?? {};
  const values = props.modelValue ?? {};
  // Clear existing
  Object.keys(formModel).forEach((k) => delete formModel[k]);
  // Set values
  for (const [key, prop] of Object.entries(properties)) {
    if (values[key] !== undefined) {
      formModel[key] = values[key];
    } else if (prop.default === undefined) {
      switch (prop.type) {
        case 'array': {
          formModel[key] = [];

          break;
        }
        case 'boolean': {
          formModel[key] = false;

          break;
        }
        case 'integer':
        case 'number': {
          formModel[key] = undefined;

          break;
        }
        default: {
          formModel[key] = undefined;
        }
      }
    } else {
      formModel[key] = prop.default;
    }
  }
}

let _syncing = false;

watch(
  [() => props.schema, () => props.modelValue],
  () => {
    if (_syncing) return;
    initModel();
  },
  { immediate: true, deep: true },
);

// Sync changes back
watch(
  formModel,
  (val) => {
    _syncing = true;
    emit('update:modelValue', { ...val });
    // Reset flag after microtask to allow future external updates
    Promise.resolve().then(() => {
      _syncing = false;
    });
  },
  { deep: true },
);

/** Get property config */
function getProp(key: string): SchemaProperty {
  return props.schema?.properties?.[key] ?? {};
}

/** Get field label */
function getLabel(key: string): string {
  const prop = getProp(key);
  return prop.title ?? key;
}

/** Build validation rules for a field */
function buildRules(key: string): Rule[] {
  const prop = getProp(key);
  const rules: Rule[] = [];

  if (requiredSet.value.has(key)) {
    rules.push({
      required: true,
      message: $t('common.formRules.required', { field: getLabel(key) }),
    });
  }

  if (prop.pattern) {
    rules.push({
      pattern: new RegExp(prop.pattern),
      message: `${getLabel(key)}: pattern mismatch`,
    });
  }

  if (prop.minLength !== undefined) {
    rules.push({
      min: prop.minLength,
      message: `${getLabel(key)}: min ${prop.minLength} characters`,
    });
  }

  if (prop.maxLength !== undefined) {
    rules.push({
      max: prop.maxLength,
      message: `${getLabel(key)}: max ${prop.maxLength} characters`,
    });
  }

  return rules;
}

/** Computed form rules */
const formRules = computed<Record<string, Rule[]>>(() => {
  const rules: Record<string, Rule[]> = {};
  for (const key of propertyKeys.value) {
    rules[key] = buildRules(key);
  }
  return rules;
});

/** Determine field rendering type */
function getFieldType(
  key: string,
):
  | 'boolean'
  | 'enum'
  | 'multi_enum'
  | 'number'
  | 'password'
  | 'string'
  | 'textarea' {
  const prop = getProp(key);

  if (prop.type === 'boolean') return 'boolean';
  if (prop.type === 'number' || prop.type === 'integer') return 'number';

  if (prop.enum && prop.enum.length > 0) return 'enum';

  if (prop.type === 'array' && prop.items?.enum) return 'multi_enum';

  if (prop.format === 'password') return 'password';
  if (prop.format === 'textarea') return 'textarea';

  return 'string';
}

/** Get enum options */
function getEnumOptions(
  key: string,
): Array<{ label: string; value: number | string }> {
  const prop = getProp(key);
  const values = prop.enum ?? prop.items?.enum ?? [];
  return values.map((v) => ({ label: String(v), value: v as number | string }));
}

/** Generic handler for Select @change */
function onSelectChange(key: string, val: unknown) {
  formModel[key] = val;
}

function getMultiSelectValue(key: string): Array<number | string> {
  const value = formModel[key];
  return Array.isArray(value) ? (value as Array<number | string>) : [];
}

function getNumberValue(key: string): number | undefined {
  const value = formModel[key];
  return typeof value === 'number' ? value : undefined;
}

function getSelectValue(key: string): number | string | undefined {
  const value = formModel[key];
  if (typeof value === 'number' || typeof value === 'string') return value;
  return undefined;
}

function getStringValue(key: string): string {
  const value = formModel[key];
  return typeof value === 'string' ? value : '';
}

/** Public API */
async function validate(): Promise<void> {
  await formRef.value?.validate();
}

function getValues(): Record<string, unknown> {
  return { ...formModel };
}

function reset(): void {
  formRef.value?.resetFields();
}

defineExpose({ validate, getValues, reset, formRef });
</script>

<template>
  <Form
    ref="formRef"
    layout="vertical"
    :model="formModel"
    :rules="formRules"
    :disabled="disabled"
  >
    <template v-for="key in propertyKeys" :key="key">
      <Form.Item :name="key" :label="getLabel(key)">
        <template v-if="getProp(key).description" #extra>
          <Tooltip :title="getProp(key).description">
            <span class="text-xs text-muted-foreground">
              {{ getProp(key).description }}
            </span>
          </Tooltip>
        </template>

        <!-- boolean -->
        <Switch
          v-if="getFieldType(key) === 'boolean'"
          :checked="!!formModel[key]"
          @update:checked="
            (v: boolean | string | number) => (formModel[key] = !!v)
          "
        />

        <!-- number / integer -->
        <InputNumber
          v-else-if="getFieldType(key) === 'number'"
          :value="getNumberValue(key)"
          :style="{ width: '100%' }"
          :min="getProp(key).minimum"
          :max="getProp(key).maximum"
          @update:value="(v: string | number | null) => (formModel[key] = v)"
        />

        <!-- enum (single select) -->
        <Select
          v-else-if="getFieldType(key) === 'enum'"
          :value="getSelectValue(key)"
          :options="getEnumOptions(key)"
          @change="(v: unknown) => onSelectChange(key, v)"
        />

        <!-- array enum (multi select) -->
        <Select
          v-else-if="getFieldType(key) === 'multi_enum'"
          :value="getMultiSelectValue(key)"
          mode="multiple"
          :options="getEnumOptions(key)"
          @change="(v: unknown) => onSelectChange(key, v)"
        />

        <!-- password -->
        <Input.Password
          v-else-if="getFieldType(key) === 'password'"
          :value="getStringValue(key)"
          autocomplete="new-password"
          @update:value="(v: string) => (formModel[key] = v)"
        />

        <!-- textarea -->
        <Input.TextArea
          v-else-if="getFieldType(key) === 'textarea'"
          :value="getStringValue(key)"
          :rows="4"
          @update:value="(v: string) => (formModel[key] = v)"
        />

        <!-- string (default) -->
        <Input
          v-else
          :value="getStringValue(key)"
          @update:value="(v: string) => (formModel[key] = v)"
        />
      </Form.Item>
    </template>
  </Form>
</template>
