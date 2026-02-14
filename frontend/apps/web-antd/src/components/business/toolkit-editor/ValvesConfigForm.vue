<script lang="ts" setup>
/**
 * Valves 配置表单组件
 *
 * 根据 valves_schema (JSON Schema) 动态渲染表单字段。
 * 支持 string / number / integer / boolean 类型。
 * 字段名包含 secret/password/key/token 时自动使用密码输入框。
 */
import { computed, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { Form, FormItem, Input, InputNumber, InputPassword, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'ValvesConfigForm' });

const props = withDefaults(
  defineProps<{
    /** JSON Schema from toolkit_meta.valves_schema */
    schema?: Record<string, unknown> | null;
    /** Current valves config values */
    value?: Record<string, unknown>;
    disabled?: boolean;
    /** i18n prefix */
    localePrefix?: string;
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

// ── i18n helper ──
function t(key: string): string {
  return $t(`${props.localePrefix}.toolkitEditor.${key}`);
}

// ── Schema parsing ──
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
  const properties = (props.schema.properties ?? {}) as Record<string, Record<string, unknown>>;
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

// ── Form values ──
const formValues = computed(() => {
  const vals: Record<string, unknown> = {};
  for (const field of fields.value) {
    const current = props.value?.[field.name];
    vals[field.name] = current !== undefined ? current : (field.defaultValue ?? getTypeDefault(field.type));
  }
  return vals;
});

function getTypeDefault(type: string): unknown {
  switch (type) {
    case 'boolean': return false;
    case 'number':
    case 'integer': return 0;
    default: return '';
  }
}

function handleFieldChange(fieldName: string, val: unknown) {
  const newValues = { ...formValues.value, [fieldName]: val };
  emit('update:value', newValues);
}

// Emit defaults on mount if value is empty
watch(
  fields,
  (f) => {
    if (f.length > 0 && (!props.value || Object.keys(props.value).length === 0)) {
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
          :value="(formValues[field.name] as number)"
          :step="field.type === 'integer' ? 1 : 0.1"
          class="w-full"
          @update:value="handleFieldChange(field.name, $event)"
        />
        <!-- Secret string -->
        <InputPassword
          v-else-if="field.isSecret"
          :value="(formValues[field.name] as string)"
          :placeholder="field.description || field.name"
          @update:value="handleFieldChange(field.name, $event)"
        />
        <!-- Regular string -->
        <Input
          v-else
          :value="(formValues[field.name] as string)"
          :placeholder="field.description || field.name"
          @update:value="handleFieldChange(field.name, $event)"
        />
      </FormItem>
    </Form>
  </div>
  <div v-else class="text-muted-foreground flex items-center gap-1.5 py-2 text-xs">
    <IconifyIcon icon="lucide:info" class="size-3.5" />
    {{ t('noValves') }}
  </div>
</template>
