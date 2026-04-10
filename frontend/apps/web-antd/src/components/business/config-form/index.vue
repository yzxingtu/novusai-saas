<script setup lang="ts">
import type { FormInstance } from 'ant-design-vue';
import type { Rule } from 'ant-design-vue/es/form';

import type {
  ConfigItemMeta,
  DisplayRuleMeta,
  ValidationRuleMeta,
} from '#/types/config';

import { computed, ref } from 'vue';

import { Form } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { useConfigFormModel } from './composables/use-config-form-model';
import ConfigFormFieldSection from './sections/ConfigFormFieldSection.vue';

interface Props {
  configs: ConfigItemMeta[];
  disabled?: boolean;
}

const props = defineProps<Props>();
const formRef = ref<FormInstance>();

const {
  fieldApi,
  formModel,
  formatJsonValue,
  getValues,
  isConfigScalar,
  isDirty,
  prepareSubmitData,
  updateJsonValue,
} = useConfigFormModel({
  configs: () => props.configs || [],
});

const orderedConfigs = computed(() => {
  return (props.configs || []).toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
});

function checkDisplayRule(
  rule: DisplayRuleMeta,
  formValues: Record<string, unknown>,
): boolean {
  const fieldValue = formValues[rule.field];
  switch (rule.operator) {
    case 'equals': {
      if (!isConfigScalar(fieldValue) || Array.isArray(rule.value)) {
        return false;
      }
      return fieldValue === rule.value;
    }
    case 'in': {
      if (Array.isArray(rule.value)) {
        return isConfigScalar(fieldValue) && rule.value.includes(fieldValue);
      }
      return false;
    }
    default: {
      return true;
    }
  }
}

function shouldShowConfig(cfg: ConfigItemMeta): boolean {
  if (!cfg.display_rules || cfg.display_rules.length === 0) {
    return true;
  }
  return cfg.display_rules.every((rule) => checkDisplayRule(rule, formModel));
}

function getOrderedChildren(cfg: ConfigItemMeta): ConfigItemMeta[] {
  if (!cfg.children || cfg.children.length === 0) {
    return [];
  }
  return [...cfg.children].toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
}

function getConfigLabel(cfg: ConfigItemMeta): string {
  if (cfg.name) return cfg.name;
  if (cfg.name_key) {
    const translated = t(cfg.name_key);
    if (translated !== cfg.name_key) return translated;
  }
  const platformKey = `shared.config.platform.${cfg.key}`;
  const platformTranslated = t(platformKey);
  if (platformTranslated !== platformKey) return platformTranslated;

  const tenantKey = `shared.config.tenant.${cfg.key}`;
  const tenantTranslated = t(tenantKey);
  if (tenantTranslated !== tenantKey) return tenantTranslated;
  return cfg.key;
}

function getConfigDesc(cfg: ConfigItemMeta): string | undefined {
  if (cfg.description) return cfg.description;
  if (cfg.description_key) {
    const translated = t(cfg.description_key);
    if (translated !== cfg.description_key) return translated;
  }
  const platformDescKey = `shared.config.platform_desc.${cfg.key}`;
  const platformDescTranslated = t(platformDescKey);
  if (platformDescTranslated !== platformDescKey) return platformDescTranslated;

  const tenantDescKey = `shared.config.tenant_desc.${cfg.key}`;
  const tenantDescTranslated = t(tenantDescKey);
  if (tenantDescTranslated !== tenantDescKey) return tenantDescTranslated;
  return undefined;
}

function getSelectOptions(cfg: ConfigItemMeta) {
  return (cfg.options || []).map((option) => {
    if (option.label) return { value: option.value, label: option.label };
    if (option.label_key) {
      const translated = t(option.label_key);
      if (translated !== option.label_key) {
        return { value: option.value, label: translated };
      }
    }

    const platformOptKey = `shared.config.platform_options.${cfg.key}.${option.value}`;
    const platformOptTranslated = t(platformOptKey);
    if (platformOptTranslated !== platformOptKey) {
      return { value: option.value, label: platformOptTranslated };
    }

    const tenantOptKey = `shared.config.tenant_options.${cfg.key}.${option.value}`;
    const tenantOptTranslated = t(tenantOptKey);
    if (tenantOptTranslated !== tenantOptKey) {
      return { value: option.value, label: tenantOptTranslated };
    }

    return { value: option.value, label: option.value };
  });
}

function getConfigItemId(key: string): string {
  return `config-item-${key}`;
}

function collectRules(
  configs: ConfigItemMeta[],
  rules: Record<string, Rule[]>,
) {
  for (const cfg of configs) {
    rules[cfg.key] = convertRules(cfg);
    if (cfg.children && cfg.children.length > 0) {
      collectRules(cfg.children, rules);
    }
  }
}

const formRules = computed<Record<string, Rule[]>>(() => {
  const rules: Record<string, Rule[]> = {};
  collectRules(props.configs || [], rules);
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
  (cfg.validation_rules || []).forEach((rule: ValidationRuleMeta) => {
    switch (rule.type) {
      case 'max_length': {
        rules.push({
          max: Number(rule.value),
          message: rule.message_key
            ? t(rule.message_key, { max: rule.value })
            : '',
        });
        break;
      }
      case 'max_value': {
        rules.push({
          type: 'number',
          max: Number(rule.value),
          message: rule.message_key
            ? t(rule.message_key, { max: rule.value })
            : '',
        });
        break;
      }
      case 'min_length': {
        rules.push({
          min: Number(rule.value),
          message: rule.message_key
            ? t(rule.message_key, { min: rule.value })
            : '',
        });
        break;
      }
      case 'min_value': {
        rules.push({
          type: 'number',
          min: Number(rule.value),
          message: rule.message_key
            ? t(rule.message_key, { min: rule.value })
            : '',
        });
        break;
      }
      case 'pattern': {
        rules.push({
          pattern: new RegExp(String(rule.value)),
          message: rule.message_key ? t(rule.message_key) : '',
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
  const rule = (cfg.validation_rules || []).find((item) => item.type === type);
  return rule ? Number(rule.value) : undefined;
}

async function validate() {
  await formRef.value?.validate();
}

function reset() {
  formRef.value?.resetFields();
}

defineExpose({
  formRef,
  getValues,
  isDirty,
  prepareSubmitData,
  reset,
  validate,
});
</script>

<template>
  <Form
    layout="vertical"
    :model="formModel"
    :rules="formRules"
    ref="formRef"
    :disabled="disabled"
    autocomplete="off"
  >
    <template v-for="cfg in orderedConfigs" :key="cfg.key">
      <Transition name="config-slide">
        <div
          v-if="shouldShowConfig(cfg)"
          :id="getConfigItemId(cfg.key)"
          class="scroll-mt-24 rounded-xl transition-colors"
        >
          <Form.Item
            :name="cfg.key"
            :label="getConfigLabel(cfg)"
            :extra="getConfigDesc(cfg)"
          >
            <ConfigFormFieldSection
              :config="cfg"
              :field-api="fieldApi"
              :form-model="formModel"
              :format-json-value="formatJsonValue"
              :get-rule-number="getRuleNumber"
              :get-select-options="getSelectOptions"
              :text-rows="4"
              :fallback-rows="6"
              :with-password-generator="true"
              @update-json="updateJsonValue"
            >
              <template #password-extra="{ setValue }">
                <slot
                  :name="`generate-${cfg.key}`"
                  :set-value="setValue"
                ></slot>
              </template>
            </ConfigFormFieldSection>
          </Form.Item>
        </div>
      </Transition>

      <template
        v-if="
          cfg.value_type === 'json' &&
          cfg.children &&
          cfg.children.length > 0 &&
          shouldShowConfig(cfg)
        "
      >
        <template v-for="child in getOrderedChildren(cfg)" :key="child.key">
          <Transition name="config-slide">
            <div
              v-if="shouldShowConfig(child)"
              :id="getConfigItemId(child.key)"
              class="ml-4 scroll-mt-24 rounded-xl border-l-2 border-primary/20 pl-4 transition-colors"
            >
              <Form.Item
                :name="child.key"
                :label="getConfigLabel(child)"
                :extra="getConfigDesc(child)"
              >
                <ConfigFormFieldSection
                  :config="child"
                  :field-api="fieldApi"
                  :form-model="formModel"
                  :format-json-value="formatJsonValue"
                  :get-rule-number="getRuleNumber"
                  :get-select-options="getSelectOptions"
                  :text-rows="4"
                  :fallback-rows="4"
                  @update-json="updateJsonValue"
                />
              </Form.Item>
            </div>
          </Transition>
        </template>
      </template>
    </template>
  </Form>
</template>

<style scoped>
.config-slide-enter-active,
.config-slide-leave-active {
  max-height: 500px; /* Large enough height / 足够大的高度 */
  overflow: hidden;
  transition: all 0.3s ease;
}

.config-slide-enter-from,
.config-slide-leave-to {
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-bottom: 0;
  opacity: 0;
  transform: translateY(-20px);
}
</style>
