<script setup lang="ts">
/**
 * 插件配置表单
 *
 * 从 plugin.yaml config_schema (JSON Schema) 自动生成配置表单。
 * 支持 x-encrypted 字段脱敏显示、required 校验、枚举选择框。
 */
import { computed, ref, watch } from 'vue';

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  enum?: string[];
  default?: unknown;
  'x-encrypted'?: boolean;
  minimum?: number;
  maximum?: number;
}

interface ConfigSchema {
  type?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
}

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    modelValue: Record<string, unknown>;
    schema: ConfigSchema;
  }>(),
  {
    disabled: false,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', v: Record<string, unknown>): void;
}>();

const form = ref<Record<string, unknown>>({ ...props.modelValue });

watch(
  () => props.modelValue,
  (v) => {
    form.value = { ...v };
  },
  { deep: true },
);

function resolveFieldType(schema: SchemaProperty): string {
  if (schema.enum) return 'select';
  if (schema.type === 'boolean') return 'switch';
  if (schema.type === 'integer' || schema.type === 'number') return 'number';
  if (schema['x-encrypted']) return 'password';
  return 'text';
}

const fields = computed(() => {
  const props_map = props.schema?.properties ?? {};
  const required = new Set(props.schema?.required);
  return Object.entries(props_map).map(([key, schema]) => ({
    key,
    schema,
    required: required.has(key),
    isEncrypted: schema['x-encrypted'] === true,
    fieldType: resolveFieldType(schema),
  }));
});

function handleChange(key: string, value: unknown) {
  form.value[key] = value;
  emit('update:modelValue', { ...form.value });
}

/** 脱敏值：已加密的字段显示为 sk-***xxx 形式 */
function displayValue(key: string, schema: SchemaProperty): string {
  const v = form.value[key];
  if (!schema['x-encrypted'] || !v || typeof v !== 'string')
    return String(v ?? '');
  if (v.length > 6) return `${v.slice(0, 3)}***${v.slice(-3)}`;
  return '***';
}
</script>

<template>
  <a-form layout="vertical" :disabled="disabled">
    <a-form-item
      v-for="field in fields"
      :key="field.key"
      :label="field.schema.title ?? field.key"
      :required="field.required"
    >
      <a-tooltip
        v-if="field.schema.description"
        :title="field.schema.description"
        placement="topLeft"
      >
        <!-- Select -->
        <a-select
          v-if="field.fieldType === 'select'"
          :value="form[field.key]"
          :options="
            (field.schema.enum ?? []).map((v) => ({ label: v, value: v }))
          "
          @change="(v: unknown) => handleChange(field.key, v)"
        />
        <!-- Switch -->
        <a-switch
          v-else-if="field.fieldType === 'switch'"
          :checked="!!form[field.key]"
          @change="(v: boolean) => handleChange(field.key, v)"
        />
        <!-- Number -->
        <a-input-number
          v-else-if="field.fieldType === 'number'"
          :value="form[field.key] as number"
          :min="field.schema.minimum"
          :max="field.schema.maximum"
          class="w-full"
          @change="(v: number | null) => handleChange(field.key, v)"
        />
        <!-- Password / Encrypted -->
        <a-input-password
          v-else-if="field.fieldType === 'password'"
          :value="form[field.key] as string"
          :placeholder="
            field.isEncrypted ? displayValue(field.key, field.schema) : ''
          "
          @change="
            (e: Event) =>
              handleChange(field.key, (e.target as HTMLInputElement).value)
          "
        />
        <!-- Text (default) -->
        <a-input
          v-else
          :value="form[field.key] as string"
          @change="
            (e: Event) =>
              handleChange(field.key, (e.target as HTMLInputElement).value)
          "
        />
      </a-tooltip>
      <!-- No tooltip version -->
      <template v-if="!field.schema.description">
        <a-select
          v-if="field.fieldType === 'select'"
          :value="form[field.key]"
          :options="
            (field.schema.enum ?? []).map((v) => ({ label: v, value: v }))
          "
          @change="(v: unknown) => handleChange(field.key, v)"
        />
        <a-switch
          v-else-if="field.fieldType === 'switch'"
          :checked="!!form[field.key]"
          @change="(v: boolean) => handleChange(field.key, v)"
        />
        <a-input-number
          v-else-if="field.fieldType === 'number'"
          :value="form[field.key] as number"
          :min="field.schema.minimum"
          :max="field.schema.maximum"
          class="w-full"
          @change="(v: number | null) => handleChange(field.key, v)"
        />
        <a-input-password
          v-else-if="field.fieldType === 'password'"
          :value="form[field.key] as string"
          :placeholder="
            field.isEncrypted ? displayValue(field.key, field.schema) : ''
          "
          @change="
            (e: Event) =>
              handleChange(field.key, (e.target as HTMLInputElement).value)
          "
        />
        <a-input
          v-else
          :value="form[field.key] as string"
          @change="
            (e: Event) =>
              handleChange(field.key, (e.target as HTMLInputElement).value)
          "
        />
      </template>
    </a-form-item>
  </a-form>
</template>
