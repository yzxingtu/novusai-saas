<script setup lang="ts">
import type { FormInstance } from 'ant-design-vue';
import type { Rule } from 'ant-design-vue/es/form';

import type {
  ConfigItemMeta,
  ConfigSubmitPayload,
  ValidationRuleMeta,
} from '#/types/config';

import { computed, reactive, ref, watch } from 'vue';

import { Form, Input, InputNumber, Select, Switch } from 'ant-design-vue';

import { $t as t } from '#/locales';

import ImageUpload from '../image-upload/image-upload.vue';

interface Props {
  configs: ConfigItemMeta[];
  disabled?: boolean;
}

const props = defineProps<Props>();
const formRef = ref<FormInstance>();
const formModel = reactive<Record<string, any>>({});
// 保存初始值用于比较是否有修改
let initialSnapshot = '';

// 初始化表单值
watch(
  () => props.configs,
  (list) => {
    const data: Record<string, any> = {};
    (list || []).forEach((cfg) => {
      const raw = cfg.value ?? cfg.default_value;
      data[cfg.key] =
        cfg.value_type === 'password' && cfg.is_encrypted ? '******' : raw;
    });
    // 清空旧数据再赋新值
    Object.keys(formModel).forEach((key) => delete formModel[key]);
    Object.assign(formModel, data);
    // 保存初始快照
    initialSnapshot = JSON.stringify(data);
  },
  { immediate: true },
);

const orderedConfigs = computed(() => {
  return [...(props.configs || [])].sort(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
});

// 获取配置项标签（优先使用 name，其次 name_key，最后 fallback）
function getConfigLabel(cfg: ConfigItemMeta): string {
  // 1. 直接使用 name 字段
  if (cfg.name) return cfg.name;
  // 2. 使用 name_key 翻译
  if (cfg.name_key) {
    const translated = t(cfg.name_key);
    if (translated !== cfg.name_key) return translated;
  }
  // 3. fallback: 尝试 shared.config.platform.{key} 或 shared.config.tenant.{key}
  const platformKey = `shared.config.platform.${cfg.key}`;
  const platformTranslated = t(platformKey);
  if (platformTranslated !== platformKey) return platformTranslated;

  const tenantKey = `shared.config.tenant.${cfg.key}`;
  const tenantTranslated = t(tenantKey);
  if (tenantTranslated !== tenantKey) return tenantTranslated;
  // 4. 最后 fallback 到 key 本身
  return cfg.key;
}

// 获取配置项描述（优先使用 description，其次 description_key，不做 fallback 避免警告）
function getConfigDesc(cfg: ConfigItemMeta): string | undefined {
  // 1. 直接使用 description 字段
  if (cfg.description) return cfg.description;
  // 2. 使用 description_key 翻译
  if (cfg.description_key) {
    const translated = t(cfg.description_key);
    if (translated !== cfg.description_key) return translated;
  }
  // 不做 fallback，避免 i18n 警告
  return undefined;
}

// 获取下拉选项
function getSelectOptions(cfg: ConfigItemMeta) {
  return (cfg.options || []).map((o) => {
    // 1. 直接使用 label 字段
    if (o.label) return { value: o.value, label: o.label };
    // 2. 使用 label_key 翻译
    if (o.label_key) {
      const translated = t(o.label_key);
      if (translated !== o.label_key)
        return { value: o.value, label: translated };
    }
    // 3. fallback 到 value
    return { value: o.value, label: o.value };
  });
}

const formRules = computed<Record<string, Rule[]>>(() => {
  const rules: Record<string, Rule[]> = {};
  (props.configs || []).forEach((cfg) => {
    rules[cfg.key] = convertRules(cfg);
  });
  return rules;
});

function convertRules(cfg: ConfigItemMeta): Rule[] {
  const rules: Rule[] = [];
  if (cfg.is_required) {
    const fieldName = cfg.name_key ? t(cfg.name_key) : cfg.key;
    rules.push({
      required: true,
      message: t('shared.config.validation.required', { field: fieldName }),
    });
  }
  (cfg.validation_rules || []).forEach((r: ValidationRuleMeta) => {
    switch (r.type) {
      case 'max_length': {
        rules.push({
          max: Number(r.value),
          message: r.message_key ? t(r.message_key, { max: r.value }) : '',
        });
        break;
      }
      case 'max_value': {
        rules.push({
          type: 'number',
          max: Number(r.value),
          message: r.message_key ? t(r.message_key, { max: r.value }) : '',
        });
        break;
      }
      case 'min_length': {
        rules.push({
          min: Number(r.value),
          message: r.message_key ? t(r.message_key, { min: r.value }) : '',
        });
        break;
      }
      case 'min_value': {
        rules.push({
          type: 'number',
          min: Number(r.value),
          message: r.message_key ? t(r.message_key, { min: r.value }) : '',
        });
        break;
      }
      case 'pattern': {
        rules.push({
          pattern: new RegExp(String(r.value)),
          message: r.message_key ? t(r.message_key) : '',
        });
        break;
      }
    }
  });
  return rules;
}

function getRuleNumber(
  cfg: ConfigItemMeta,
  type: 'max_value' | 'min_value',
): number | undefined {
  const rule = (cfg.validation_rules || []).find((r) => r.type === type);
  return rule ? Number(rule.value) : undefined;
}

async function validate() {
  await formRef.value?.validate();
}

function getValues(): Record<string, any> {
  return { ...formModel };
}

function prepareSubmitData(): ConfigSubmitPayload {
  const payload: ConfigSubmitPayload = {};
  (props.configs || []).forEach((cfg) => {
    const val = formModel[cfg.key];
    if (cfg.value_type === 'password' && cfg.is_encrypted) {
      if (val && val !== '******') {
        payload[cfg.key] = val;
      }
    } else {
      payload[cfg.key] = val;
    }
  });
  return payload;
}

function reset() {
  formRef.value?.resetFields();
}

// 检查表单是否有修改
function isDirty(): boolean {
  const currentSnapshot = JSON.stringify(formModel);
  return currentSnapshot !== initialSnapshot;
}

// 暴露方法给父组件
defineExpose({
  validate,
  getValues,
  prepareSubmitData,
  reset,
  isDirty,
  formRef,
});
</script>

<template>
  <Form
    layout="vertical"
    :model="formModel"
    :rules="formRules"
    ref="formRef"
    :disabled="disabled"
  >
    <Form.Item
      v-for="cfg in orderedConfigs"
      :key="cfg.key"
      :name="cfg.key"
      :label="getConfigLabel(cfg)"
      :extra="getConfigDesc(cfg)"
    >
      <!-- string -->
      <Input
        v-if="cfg.value_type === 'string'"
        v-model:value="formModel[cfg.key]"
      />

      <!-- number -->
      <InputNumber
        v-else-if="cfg.value_type === 'number'"
        v-model:value="formModel[cfg.key]"
        :style="{ width: '100%' }"
        :min="getRuleNumber(cfg, 'min_value')"
        :max="getRuleNumber(cfg, 'max_value')"
      />

      <!-- boolean -->
      <Switch
        v-else-if="cfg.value_type === 'boolean'"
        v-model:checked="formModel[cfg.key]"
      />

      <!-- select -->
      <Select
        v-else-if="cfg.value_type === 'select'"
        v-model:value="formModel[cfg.key]"
        :options="getSelectOptions(cfg)"
      />

      <!-- multi_select -->
      <Select
        v-else-if="cfg.value_type === 'multi_select'"
        v-model:value="formModel[cfg.key]"
        mode="multiple"
        :options="getSelectOptions(cfg)"
      />

      <!-- text -->
      <Input.TextArea
        v-else-if="cfg.value_type === 'text'"
        v-model:value="formModel[cfg.key]"
        :rows="4"
      />

      <!-- password -->
      <Input.Password
        v-else-if="cfg.value_type === 'password'"
        v-model:value="formModel[cfg.key]"
        autocomplete="new-password"
        :placeholder="t('shared.config.page.password_placeholder')"
      />

      <!-- color -->
      <div
        v-else-if="cfg.value_type === 'color'"
        class="flex items-center gap-2"
      >
        <input
          type="color"
          :value="formModel[cfg.key]"
          class="h-8 w-8 cursor-pointer rounded border border-border"
          @input="
            (e) => (formModel[cfg.key] = (e.target as HTMLInputElement).value)
          "
        />
        <Input v-model:value="formModel[cfg.key]" style="width: 120px" />
      </div>

      <!-- image -->
      <ImageUpload
        v-else-if="cfg.value_type === 'image'"
        v-model="formModel[cfg.key]"
      />

      <!-- json (fallback: textarea) -->
      <Input.TextArea v-else v-model:value="formModel[cfg.key]" :rows="6" />
    </Form.Item>
  </Form>
</template>

<style scoped></style>
