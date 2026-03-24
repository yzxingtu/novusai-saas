<script lang="ts" setup>
/**
 * Valves Config Form Component
 * Valves 配置表单组件
 *
 * Dynamically renders form fields based on valves_schema (JSON Schema).
 * 根据 valves_schema (JSON Schema) 动态渲染表单字段。
 * Supports string / number / integer / boolean types.
 * 支持 string / number / integer / boolean 类型。
 * Auto-uses password input when field name contains secret/password/key/token.
 * 字段名包含 secret/password/key/token 时自动使用密码输入框。
 */
import { computed, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Form,
  FormItem,
  Input,
  InputNumber,
  InputPassword,
  Switch,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'ValvesConfigForm' });

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    /** i18n prefix / 国际化前缀 */
    localePrefix?: string;
    /** JSON Schema from toolkit_meta.valves_schema / 来自 toolkit_meta.valves_schema 的 JSON Schema */
    schema?: null | Record<string, unknown>;
    /** Current valves config values / 当前阀门配置值 */
    value?: Record<string, unknown>;
  }>(),
  {
    schema: null,
    value: () => ({}),
    disabled: false,
    localePrefix: 'admin.ai.skill',
  },
);

const emit = defineEmits<{
  'update:value': [val: Record<string, unknown>];
}>();

// ── i18n helper / 国际化封装 ──
function t(key: string): string {
  return $t(`${props.localePrefix}.toolkitEditor.${key}`);
}

// ── Schema parsing / Schema 解析 ──
interface ValvesField {
  name: string;
  type: string;
  description: string;
  defaultValue: unknown;
  required: boolean;
  isSecret: boolean;
}

const SECRET_PATTERN = /secret|password|key|token|api_key|apikey/i;

const fields = computed<ValvesField[]>(() => {
  if (!props.schema) return [];
  const properties = (props.schema.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  const required = (props.schema.required ?? []) as string[];

  return Object.entries(properties).map(([name, prop]) => ({
    name,
    type: (prop.type as string) ?? 'string',
    description: (prop.description as string) ?? '',
    defaultValue: prop.default,
    required: required.includes(name),
    isSecret: SECRET_PATTERN.test(name),
  }));
});

const hasFields = computed(() => fields.value.length > 0);

// ── Form values / 表单值 ──
const formValues = computed(() => {
  const vals: Record<string, unknown> = {};
  for (const field of fields.value) {
    const current = props.value?.[field.name];
    vals[field.name] =
      current === undefined
        ? (field.defaultValue ?? getTypeDefault(field.type))
        : current;
  }
  return vals;
});

function getTypeDefault(type: string): unknown {
  switch (type) {
    case 'boolean': {
      return false;
    }
    case 'integer':
    case 'number': {
      return 0;
    }
    default: {
      return '';
    }
  }
}

function handleFieldChange(fieldName: string, val: unknown) {
  const newValues = { ...formValues.value, [fieldName]: val };
  emit('update:value', newValues);
}

// Emit defaults on mount if value is empty / 空值时挂载发出默认
watch(
  fields,
  (f) => {
    if (
      f.length > 0 &&
      (!props.value || Object.keys(props.value).length === 0)
    ) {
      const defaults: Record<string, unknown> = {};
      for (const field of f) {
        defaults[field.name] = field.defaultValue ?? getTypeDefault(field.type);
      }
      emit('update:value', defaults);
    }
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="hasFields" class="valves-config-form">
    <Form layout="vertical" :disabled="props.disabled">
      <FormItem
        v-for="field in fields"
        :key="field.name"
        :label="field.name"
        :required="field.required"
        :help="field.description || undefined"
      >
        <!-- Boolean -->
        <Switch
          v-if="field.type === 'boolean'"
          :checked="!!formValues[field.name]"
          @update:checked="handleFieldChange(field.name, $event)"
        />
        <!-- Number / Integer -->
        <InputNumber
          v-else-if="field.type === 'number' || field.type === 'integer'"
          :value="formValues[field.name] as number"
          :step="field.type === 'integer' ? 1 : 0.1"
          class="w-full"
          @update:value="handleFieldChange(field.name, $event)"
        />
        <!-- Secret string -->
        <InputPassword
          v-else-if="field.isSecret"
          :value="formValues[field.name] as string"
          :placeholder="field.description || field.name"
          @update:value="handleFieldChange(field.name, $event)"
        />
        <!-- Regular string -->
        <Input
          v-else
          :value="formValues[field.name] as string"
          :placeholder="field.description || field.name"
          @update:value="handleFieldChange(field.name, $event)"
        />
      </FormItem>
    </Form>
  </div>
  <div
    v-else
    class="flex items-center gap-1.5 py-2 text-xs text-muted-foreground"
  >
    <IconifyIcon icon="lucide:info" class="size-3.5" />
    {{ t('noValves') }}
  </div>
</template>
