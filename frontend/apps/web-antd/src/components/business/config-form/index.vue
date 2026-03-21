<script setup lang="ts">
import type { FormInstance } from 'ant-design-vue';
import type { Rule } from 'ant-design-vue/es/form';

import type {
  ConfigItemMeta,
  ConfigObject,
  ConfigScalar,
  ConfigSubmitPayload,
  ConfigValue,
  DisplayRuleMeta,
  ValidationRuleMeta,
} from '#/types/config';

import { computed, reactive, ref, watch } from 'vue';

import { Form, Input, InputNumber, Select, Switch } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { ConfigHtmlEditor } from '../config-html-editor';
import { ConfigImagePicker } from '../config-image-picker';

interface Props {
  configs: ConfigItemMeta[];
  disabled?: boolean;
}

const props = defineProps<Props>();
const formRef = ref<FormInstance>();
type ConfigFormModel = Record<string, ConfigValue | undefined>;

const formModel = reactive<ConfigFormModel>({});
// Save initial values for comparison to detect modifications / 保存初始值用于比较是否有修改
let initialSnapshot = '';

function isConfigObject(value: unknown): value is ConfigObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isConfigScalar(value: unknown): value is ConfigScalar {
  return (
    value === null ||
    typeof value === 'boolean' ||
    typeof value === 'number' ||
    typeof value === 'string'
  );
}

/**
 * Get value from nested object by path
 * 从嵌套对象中根据路径获取值
 * @param obj Object / 对象
 * @param path Path, supports dot notation / 路径，支持 . 分隔
 */
function getValueByPath(
  obj: ConfigObject | undefined,
  path: string,
): ConfigValue | undefined {
  if (!obj || !path) return undefined;
  const keys = path.split('.');
  let result: ConfigValue | undefined = obj;
  for (const key of keys) {
    if (!isConfigObject(result)) return undefined;
    result = result[key];
  }
  return result;
}

/**
 * Set value in nested object by path
 * 在嵌套对象中根据路径设置值
 * @param obj Object / 对象
 * @param path Path, supports dot notation / 路径，支持 . 分隔
 * @param value Value to set / 要设置的值
 */
function setValueByPath(
  obj: ConfigObject,
  path: string,
  value: ConfigValue | undefined,
): void {
  if (!obj || !path) return;
  const keys = path.split('.');
  let current: ConfigObject = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]!;
    if (!isConfigObject(current[key])) {
      current[key] = {};
    }
    current = current[key] as ConfigObject;
  }
  current[keys[keys.length - 1]!] = value;
}

/**
 * Recursively initialize config item values into formModel
 * Handles value mapping for regular fields and child fields
 * 递归初始化配置项值到 formModel
 * 处理普通字段和子字段的值映射
 */
function initConfigValue(
  cfg: ConfigItemMeta,
  data: ConfigFormModel,
  parentJsonValue?: ConfigObject,
) {
  const raw = cfg.value ?? cfg.default_value;

  // If value_path exists, this is a child field, read value from parent JSON / 如果有 value_path，说明这是子字段，从父 JSON 中读取值
  if (cfg.value_path && parentJsonValue !== undefined) {
    const val = getValueByPath(parentJsonValue, cfg.value_path);
    const resolvedVal = val ?? cfg.default_value;
    // Only show placeholder when backend explicitly returns '******', otherwise use resolvedVal (may be null/undefined) / 只有当后端明确返回 '******' 时才显示占位符，否则直接使用 resolvedVal
    data[cfg.key] = resolvedVal;
  } else {
    // Allow backend to return real value, only show placeholder when value is empty and encrypted / 允许后端返回真实值，只有在值为空且加密时才显示占位符
    // Only show placeholder when backend explicitly returns '******', otherwise use raw (may be null/undefined) / 只有当后端明确返回 '******' 时才显示占位符
    if (cfg.value_type === 'html') {
      data[cfg.key] = raw == null || raw === undefined ? '' : String(raw);
    } else {
      data[cfg.key] = raw;
    }
  }

  // If there are children, recursively initialize child fields / 如果有 children，递归初始化子字段
  if (cfg.children && cfg.children.length > 0) {
    // Parent field's JSON value / 父字段的 JSON 值
    const currentValue = data[cfg.key];
    const jsonValue = isConfigObject(currentValue)
      ? currentValue
      : tryParseJson(raw);
    for (const child of cfg.children) {
      initConfigValue(child, data, jsonValue);
    }
  }
}

/**
 * Try to parse JSON string / 尝试解析 JSON 字符串
 */
function tryParseJson(val: unknown): ConfigObject {
  if (typeof val === 'string') {
    try {
      const parsed: unknown = JSON.parse(val);
      return isConfigObject(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return isConfigObject(val) ? val : {};
}

/**
 * Format JSON value to string (for TextArea display) / 格式化 JSON 值为字符串（用于 TextArea 显示）
 */
function formatJsonValue(val: ConfigValue | undefined): string {
  if (val === null || val === undefined) return '';
  if (typeof val === 'string') return val;
  try {
    return JSON.stringify(val, null, 2);
  } catch {
    return '';
  }
}

/**
 * Update JSON field value (from TextArea input) / 更新 JSON 字段值（从 TextArea 输入）
 */
function updateJsonValue(key: string, val: string) {
  try {
    // Try to parse as JSON / 尝试解析为 JSON
    formModel[key] = JSON.parse(val);
  } catch {
    // Save raw string on parse failure / 解析失败时保存原始字符串
    formModel[key] = val;
  }
}

// Initialize form values / 初始化表单值
watch(
  () => props.configs,
  (list) => {
    const data: ConfigFormModel = {};
    (list || []).forEach((cfg) => {
      initConfigValue(cfg, data);
    });
    // Clear old data and assign new values / 清空旧数据再赋新值
    Object.keys(formModel).forEach((key) => delete formModel[key]);
    Object.assign(formModel, data);
    // Save initial snapshot / 保存初始快照
    initialSnapshot = JSON.stringify(data);
  },
  { immediate: true },
);

const orderedConfigs = computed(() => {
  return (props.configs || []).toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
});

/**
 * Check if a single display rule is satisfied / 检查单个显示规则是否满足
 */
function checkDisplayRule(
  rule: DisplayRuleMeta,
  formValues: ConfigFormModel,
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

/**
 * Determine if config item should be visible
 * Multiple rules are AND-ed, all must be satisfied to show
 * 判断配置项是否应该显示
 * 多个规则之间为 AND 关系，全部满足才显示
 */
function shouldShowConfig(cfg: ConfigItemMeta): boolean {
  if (!cfg.display_rules || cfg.display_rules.length === 0) {
    return true;
  }
  // All rules must be satisfied to show / 所有规则都满足才显示
  return cfg.display_rules.every((rule) => checkDisplayRule(rule, formModel));
}

/**
 * Get sorted child fields / 获取排序后的子字段
 */
function getOrderedChildren(cfg: ConfigItemMeta): ConfigItemMeta[] {
  if (!cfg.children || cfg.children.length === 0) {
    return [];
  }
  return [...cfg.children].toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
}

// Get config item label (prefer name, then name_key, finally fallback) / 获取配置项标签（优先使用 name，其次 name_key，最后 fallback）
function getConfigLabel(cfg: ConfigItemMeta): string {
  // 1. Use name field directly / 直接使用 name 字段
  if (cfg.name) return cfg.name;
  // 2. Use name_key translation / 使用 name_key 翻译
  if (cfg.name_key) {
    const translated = t(cfg.name_key);
    if (translated !== cfg.name_key) return translated;
  }
  // 3. fallback: try shared.config.platform.{key} or shared.config.tenant.{key}
  const platformKey = `shared.config.platform.${cfg.key}`;
  const platformTranslated = t(platformKey);
  if (platformTranslated !== platformKey) return platformTranslated;

  const tenantKey = `shared.config.tenant.${cfg.key}`;
  const tenantTranslated = t(tenantKey);
  if (tenantTranslated !== tenantKey) return tenantTranslated;
  // 4. Final fallback to key itself / 最后 fallback 到 key 本身
  return cfg.key;
}

// Get config item description (prefer description, then description_key, finally fallback) / 获取配置项描述（优先使用 description，其次 description_key，最后 fallback）
function getConfigDesc(cfg: ConfigItemMeta): string | undefined {
  // 1. Use description field directly / 直接使用 description 字段
  if (cfg.description) return cfg.description;
  // 2. Use description_key translation / 使用 description_key 翻译
  if (cfg.description_key) {
    const translated = t(cfg.description_key);
    if (translated !== cfg.description_key) return translated;
  }
  // 3. fallback: try shared.config.platform_desc.{key} or shared.config.tenant_desc.{key}
  const platformDescKey = `shared.config.platform_desc.${cfg.key}`;
  const platformDescTranslated = t(platformDescKey);
  if (platformDescTranslated !== platformDescKey) return platformDescTranslated;

  const tenantDescKey = `shared.config.tenant_desc.${cfg.key}`;
  const tenantDescTranslated = t(tenantDescKey);
  if (tenantDescTranslated !== tenantDescKey) return tenantDescTranslated;
  return undefined;
}

// Get select options / 获取下拉选项
function getSelectOptions(cfg: ConfigItemMeta) {
  return (cfg.options || []).map((o) => {
    // 1. Use label field directly / 直接使用 label 字段
    if (o.label) return { value: o.value, label: o.label };
    // 2. Use label_key translation / 使用 label_key 翻译
    if (o.label_key) {
      const translated = t(o.label_key);
      if (translated !== o.label_key)
        return { value: o.value, label: translated };
    }
    // 3. fallback: try shared.config.platform_options.{key}.{value}
    const platformOptKey = `shared.config.platform_options.${cfg.key}.${o.value}`;
    const platformOptTranslated = t(platformOptKey);
    if (platformOptTranslated !== platformOptKey)
      return { value: o.value, label: platformOptTranslated };

    const tenantOptKey = `shared.config.tenant_options.${cfg.key}.${o.value}`;
    const tenantOptTranslated = t(tenantOptKey);
    if (tenantOptTranslated !== tenantOptKey)
      return { value: o.value, label: tenantOptTranslated };
    // 4. fallback to value
    return { value: o.value, label: o.value };
  });
}

function getConfigItemId(key: string): string {
  return `config-item-${key}`;
}

/**
 * Recursively collect validation rules for all config items / 递归收集所有配置项的校验规则
 */
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

function getStringValue(key: string): string | undefined {
  const value = formModel[key];
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return undefined;
}

function setStringValue(
  key: string,
  value: null | number | string | undefined,
): void {
  formModel[key] = value == null ? undefined : String(value);
}

function getNumberValue(key: string): number | undefined {
  const value = formModel[key];
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function setNumberValue(
  key: string,
  value: null | number | string | undefined,
): void {
  if (value == null || value === '') {
    formModel[key] = undefined;
    return;
  }
  const parsed = typeof value === 'number' ? value : Number(value);
  formModel[key] = Number.isFinite(parsed) ? parsed : undefined;
}

function getBooleanValue(key: string): boolean {
  return Boolean(formModel[key]);
}

function setBooleanValue(key: string, value: unknown): void {
  formModel[key] = Boolean(value);
}

function getSelectValue(key: string): number | string | undefined {
  const value = formModel[key];
  return typeof value === 'number' || typeof value === 'string'
    ? value
    : undefined;
}

function setSelectValue(
  key: string,
  value: unknown,
): void {
  formModel[key] =
    typeof value === 'number' || typeof value === 'string'
      ? value
      : undefined;
}

function getMultiSelectValue(key: string): Array<number | string> {
  const value = formModel[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is number | string =>
      typeof item === 'number' || typeof item === 'string',
  );
}

function setMultiSelectValue(key: string, value: unknown): void {
  if (!Array.isArray(value)) {
    formModel[key] = [];
    return;
  }
  formModel[key] = value.filter(
    (item): item is number | string =>
      typeof item === 'number' || typeof item === 'string',
  );
}

function getHtmlValue(key: string): string {
  return getStringValue(key) ?? '';
}

function setHtmlValue(key: string, value: string): void {
  formModel[key] = value;
}

function getImageValue(key: string): string {
  return getStringValue(key) ?? '';
}

function setImageValue(key: string, value: string): void {
  formModel[key] = value;
}

function getValues(): ConfigFormModel {
  return { ...formModel };
}

/**
 * Recursively process child fields, merge child values into parent JSON field
 * 递归处理子字段，将子字段值合并到父字段 JSON 中
 */
function mergeChildrenToParent(
  cfg: ConfigItemMeta,
  payload: ConfigSubmitPayload,
) {
  if (!cfg.children || cfg.children.length === 0) {
    return;
  }

  // Get parent field's current JSON value / 获取父字段当前的 JSON 值
  const parentValue = tryParseJson(payload[cfg.key]);

  // Merge child field values into parent JSON / 将子字段的值合并到父字段 JSON 中
  for (const child of cfg.children) {
    if (child.value_path) {
      const childVal = formModel[child.key];
      // Special handling for password fields / 密码字段特殊处理
      if (child.value_type === 'password' && child.is_encrypted) {
        if (childVal && childVal !== '******') {
          setValueByPath(parentValue, child.value_path, childVal);
        }
        // If placeholder, don't update / 如果是占位符，不更新
      } else {
        setValueByPath(parentValue, child.value_path, childVal);
      }
      // Remove child field's independent entry from payload (it's been merged into parent) / 从 payload 中删除子字段的独立条目（它已经合并到父字段了）
      delete payload[child.key];
    }

    // Recursively process nested child fields / 递归处理嵌套的子字段
    if (child.children && child.children.length > 0) {
      mergeChildrenToParent(child, payload);
    }
  }

  // Update parent field's value / 更新父字段的值
  payload[cfg.key] = parentValue;
}

function prepareSubmitData(): ConfigSubmitPayload {
  const payload: ConfigSubmitPayload = {};

  // Step 1: Collect all field values / 第一步：收集所有字段的值
  const collectValues = (configs: ConfigItemMeta[]) => {
    for (const cfg of configs) {
      const val = formModel[cfg.key];
      if (cfg.value_type === 'password' && cfg.is_encrypted) {
        if (val && val !== '******') {
          payload[cfg.key] = val;
        }
      } else {
        payload[cfg.key] = val;
      }
      // Recursively collect child fields / 递归收集子字段
      if (cfg.children && cfg.children.length > 0) {
        collectValues(cfg.children);
      }
    }
  };
  collectValues(props.configs || []);

  // Step 2: Merge child field values into parent JSON / 第二步：将子字段值合并到父字段 JSON 中
  (props.configs || []).forEach((cfg) => {
    mergeChildrenToParent(cfg, payload);
  });

  return payload;
}

function reset() {
  formRef.value?.resetFields();
}

// Check if form has been modified / 检查表单是否有修改
function isDirty(): boolean {
  const currentSnapshot = JSON.stringify(formModel);
  return currentSnapshot !== initialSnapshot;
}

// Expose methods to parent component / 暴露方法给父组件
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
            <!-- string -->
            <Input
              v-if="cfg.value_type === 'string'"
              :value="getStringValue(cfg.key)"
              autocomplete="new-password"
              @update:value="(val) => setStringValue(cfg.key, val)"
            />

            <!-- number -->
            <InputNumber
              v-else-if="cfg.value_type === 'number'"
              :value="getNumberValue(cfg.key)"
              :style="{ width: '100%' }"
              :min="getRuleNumber(cfg, 'min_value')"
              :max="getRuleNumber(cfg, 'max_value')"
              @update:value="(val) => setNumberValue(cfg.key, val)"
            />

            <!-- boolean -->
            <Switch
              v-else-if="cfg.value_type === 'boolean'"
              :checked="getBooleanValue(cfg.key)"
              @update:checked="(val) => setBooleanValue(cfg.key, val)"
            />

            <!-- select -->
            <Select
              v-else-if="cfg.value_type === 'select'"
              :value="getSelectValue(cfg.key)"
              :options="getSelectOptions(cfg)"
              @update:value="(val) => setSelectValue(cfg.key, val)"
            />

            <!-- multi_select -->
            <Select
              v-else-if="cfg.value_type === 'multi_select'"
              :value="getMultiSelectValue(cfg.key)"
              mode="multiple"
              :options="getSelectOptions(cfg)"
              @update:value="(val) => setMultiSelectValue(cfg.key, val)"
            />

            <!-- text -->
            <Input.TextArea
              v-else-if="cfg.value_type === 'text'"
              :value="getStringValue(cfg.key)"
              :rows="4"
              @update:value="(val) => setStringValue(cfg.key, val)"
            />

            <!-- html (sanitized on server) -->
            <ConfigHtmlEditor
              v-else-if="cfg.value_type === 'html'"
              :model-value="getHtmlValue(cfg.key)"
              @update:model-value="(val) => setHtmlValue(cfg.key, val)"
            />

            <!-- password -->
            <div
              v-else-if="cfg.value_type === 'password'"
              class="flex items-center gap-2"
            >
              <Input.Password
                :value="getStringValue(cfg.key)"
                autocomplete="new-password"
                :visibility-toggle="getStringValue(cfg.key) !== '******'"
                class="flex-1"
                @update:value="(val) => setStringValue(cfg.key, val)"
              />
              <slot
                :name="`generate-${cfg.key}`"
                :set-value="(v: string) => setStringValue(cfg.key, v)"
              ></slot>
            </div>

            <!-- color -->
            <div
              v-else-if="cfg.value_type === 'color'"
              class="flex items-center gap-2"
            >
              <input
                type="color"
                :value="getStringValue(cfg.key)"
                class="h-8 w-8 cursor-pointer rounded border border-border"
                @input="
                  (e) =>
                    setStringValue(
                      cfg.key,
                      (e.target as HTMLInputElement).value,
                    )
                "
              />
              <Input
                :value="getStringValue(cfg.key)"
                style="width: 120px"
                @update:value="(val) => setStringValue(cfg.key, val)"
              />
            </div>

            <!-- image：使用附件管理器选择图片，存储附件 ID / Use attachment manager to select image, store attachment ID -->
            <ConfigImagePicker
              v-else-if="cfg.value_type === 'image'"
              :model-value="getImageValue(cfg.key)"
              @update:model-value="(val) => setImageValue(cfg.key, val)"
            />

            <!-- json with children: render children as sub-fields / JSON 类型且有子字段时，渲染子字段 -->
            <template
              v-else-if="
                cfg.value_type === 'json' &&
                cfg.children &&
                cfg.children.length > 0
              "
            >
              <!-- When JSON type has child fields, don't render parent input, render child fields instead / JSON 类型且有子字段时，不渲染父字段输入框，而是渲染子字段 -->
            </template>

            <!-- json without children: textarea for raw JSON editing -->
            <Input.TextArea
              v-else-if="cfg.value_type === 'json'"
              :value="formatJsonValue(formModel[cfg.key])"
              @update:value="(val: string) => updateJsonValue(cfg.key, val)"
              :rows="6"
              :placeholder="t('shared.config.page.json_placeholder')"
            />

            <!-- fallback: textarea -->
            <Input.TextArea
              v-else
              :value="getStringValue(cfg.key)"
              :rows="6"
              @update:value="(val) => setStringValue(cfg.key, val)"
            />
          </Form.Item>
        </div>
      </Transition>

      <!-- Render JSON field's child fields / 渲染 JSON 字段的子字段 -->
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
                <!-- string -->
                <Input
                  v-if="child.value_type === 'string'"
                  :value="getStringValue(child.key)"
                  @update:value="(val) => setStringValue(child.key, val)"
                />

                <!-- number -->
                <InputNumber
                  v-else-if="child.value_type === 'number'"
                  :value="getNumberValue(child.key)"
                  :style="{ width: '100%' }"
                  :min="getRuleNumber(child, 'min_value')"
                  :max="getRuleNumber(child, 'max_value')"
                  @update:value="(val) => setNumberValue(child.key, val)"
                />

                <!-- boolean -->
                <Switch
                  v-else-if="child.value_type === 'boolean'"
                  :checked="getBooleanValue(child.key)"
                  @update:checked="(val) => setBooleanValue(child.key, val)"
                />

                <!-- select -->
                <Select
                  v-else-if="child.value_type === 'select'"
                  :value="getSelectValue(child.key)"
                  :options="getSelectOptions(child)"
                  @update:value="(val) => setSelectValue(child.key, val)"
                />

                <!-- multi_select -->
                <Select
                  v-else-if="child.value_type === 'multi_select'"
                  :value="getMultiSelectValue(child.key)"
                  mode="multiple"
                  :options="getSelectOptions(child)"
                  @update:value="(val) => setMultiSelectValue(child.key, val)"
                />

                <!-- text -->
                <Input.TextArea
                  v-else-if="child.value_type === 'text'"
                  :value="getStringValue(child.key)"
                  :rows="4"
                  @update:value="(val) => setStringValue(child.key, val)"
                />

                <!-- html -->
                <ConfigHtmlEditor
                  v-else-if="child.value_type === 'html'"
                  :model-value="getHtmlValue(child.key)"
                  @update:model-value="(val) => setHtmlValue(child.key, val)"
                />

                <!-- password -->
                <Input.Password
                  v-else-if="child.value_type === 'password'"
                  :value="getStringValue(child.key)"
                  autocomplete="new-password"
                  :visibility-toggle="getStringValue(child.key) !== '******'"
                  @update:value="(val) => setStringValue(child.key, val)"
                />

                <!-- color -->
                <div
                  v-else-if="child.value_type === 'color'"
                  class="flex items-center gap-2"
                >
                  <input
                    type="color"
                    :value="getStringValue(child.key)"
                    class="h-8 w-8 cursor-pointer rounded border border-border"
                    @input="
                      (e) =>
                        setStringValue(
                          child.key,
                          (e.target as HTMLInputElement).value,
                        )
                    "
                  />
                  <Input
                    :value="getStringValue(child.key)"
                    style="width: 120px"
                    @update:value="(val) => setStringValue(child.key, val)"
                  />
                </div>

                <!-- image: use attachment manager to select image, store attachment ID / 使用附件管理器选择图片，存储附件 ID -->
                <ConfigImagePicker
                  v-else-if="child.value_type === 'image'"
                  :model-value="getImageValue(child.key)"
                  @update:model-value="(val) => setImageValue(child.key, val)"
                />

                <!-- fallback -->
                <Input.TextArea
                  v-else
                  :value="getStringValue(child.key)"
                  :rows="4"
                  @update:value="(val) => setStringValue(child.key, val)"
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
