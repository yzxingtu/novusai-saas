<script setup lang="ts">
import type { FormInstance } from 'ant-design-vue';
import type { Rule } from 'ant-design-vue/es/form';

import type {
  ConfigItemMeta,
  ConfigSubmitPayload,
  DisplayRuleMeta,
  ValidationRuleMeta,
} from '#/types/config';

import { computed, reactive, ref, watch } from 'vue';

import { Form, Input, InputNumber, Select, Switch } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { ConfigImagePicker } from '../config-image-picker';

interface Props {
  configs: ConfigItemMeta[];
  disabled?: boolean;
}

const props = defineProps<Props>();
const formRef = ref<FormInstance>();
const formModel = reactive<Record<string, any>>({});
// 保存初始值用于比较是否有修改
let initialSnapshot = '';

/**
 * 从嵌套对象中根据路径获取值
 * @param obj 对象
 * @param path 路径，支持 . 分隔
 */
function getValueByPath(obj: any, path: string): any {
  if (!obj || !path) return undefined;
  const keys = path.split('.');
  let result = obj;
  for (const key of keys) {
    if (result === null || result === undefined) return undefined;
    result = result[key];
  }
  return result;
}

/**
 * 在嵌套对象中根据路径设置值
 * @param obj 对象
 * @param path 路径，支持 . 分隔
 * @param value 要设置的值
 */
function setValueByPath(obj: any, path: string, value: any): void {
  if (!obj || !path) return;
  const keys = path.split('.');
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]!;
    if (current[key] === undefined || current[key] === null) {
      current[key] = {};
    }
    current = current[key];
  }
  current[keys[keys.length - 1]!] = value;
}

/**
 * 递归初始化配置项值到 formModel
 * 处理普通字段和子字段的值映射
 */
function initConfigValue(
  cfg: ConfigItemMeta,
  data: Record<string, any>,
  parentJsonValue?: any,
) {
  const raw = cfg.value ?? cfg.default_value;

  // 如果有 value_path，说明这是子字段，从父 JSON 中读取值
  if (cfg.value_path && parentJsonValue !== undefined) {
    const val = getValueByPath(parentJsonValue, cfg.value_path);
    const resolvedVal = val ?? cfg.default_value;
    // 只有当后端明确返回 '******' 时才显示占位符，否则直接使用 resolvedVal (可能是 null/undefined，即空值)
    data[cfg.key] = resolvedVal;
  } else {
    // 允许后端返回真实值，只有在值为空且加密时才显示占位符
    // 只有当后端明确返回 '******' 时才显示占位符，否则直接使用 raw (可能是 null/undefined，即空值)
    data[cfg.key] = raw;
  }

  // 如果有 children，递归初始化子字段
  if (cfg.children && cfg.children.length > 0) {
    // 父字段的 JSON 值
    const jsonValue =
      typeof data[cfg.key] === 'object' ? data[cfg.key] : tryParseJson(raw);
    for (const child of cfg.children) {
      initConfigValue(child, data, jsonValue);
    }
  }
}

/**
 * 尝试解析 JSON 字符串
 */
function tryParseJson(val: any): any {
  if (typeof val === 'string') {
    try {
      return JSON.parse(val);
    } catch {
      return {};
    }
  }
  return val ?? {};
}

/**
 * 格式化 JSON 值为字符串（用于 TextArea 显示）
 */
function formatJsonValue(val: any): string {
  if (val === null || val === undefined) return '';
  if (typeof val === 'string') return val;
  try {
    return JSON.stringify(val, null, 2);
  } catch {
    return '';
  }
}

/**
 * 更新 JSON 字段值（从 TextArea 输入）
 */
function updateJsonValue(key: string, val: string) {
  try {
    // 尝试解析为 JSON
    formModel[key] = JSON.parse(val);
  } catch {
    // 解析失败时保存原始字符串
    formModel[key] = val;
  }
}

// 初始化表单值
watch(
  () => props.configs,
  (list) => {
    const data: Record<string, any> = {};
    (list || []).forEach((cfg) => {
      initConfigValue(cfg, data);
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
  return (props.configs || []).toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
});

/**
 * 检查单个显示规则是否满足
 */
function checkDisplayRule(
  rule: DisplayRuleMeta,
  formValues: Record<string, any>,
): boolean {
  const fieldValue = formValues[rule.field];
  switch (rule.operator) {
    case 'equals': {
      return fieldValue === rule.value;
    }
    case 'in': {
      if (Array.isArray(rule.value)) {
        return rule.value.includes(fieldValue);
      }
      return false;
    }
    default: {
      return true;
    }
  }
}

/**
 * 判断配置项是否应该显示
 * 多个规则之间为 AND 关系，全部满足才显示
 */
function shouldShowConfig(cfg: ConfigItemMeta): boolean {
  if (!cfg.display_rules || cfg.display_rules.length === 0) {
    return true;
  }
  // 所有规则都满足才显示
  return cfg.display_rules.every((rule) => checkDisplayRule(rule, formModel));
}

/**
 * 获取排序后的子字段
 */
function getOrderedChildren(cfg: ConfigItemMeta): ConfigItemMeta[] {
  if (!cfg.children || cfg.children.length === 0) {
    return [];
  }
  return [...cfg.children].toSorted(
    (a, b) => (a.sort_order || 0) - (b.sort_order || 0),
  );
}

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

// 获取配置项描述（优先使用 description，其次 description_key，最后 fallback）
function getConfigDesc(cfg: ConfigItemMeta): string | undefined {
  // 1. 直接使用 description 字段
  if (cfg.description) return cfg.description;
  // 2. 使用 description_key 翻译
  if (cfg.description_key) {
    const translated = t(cfg.description_key);
    if (translated !== cfg.description_key) return translated;
  }
  // 3. fallback: 尝试 shared.config.platform_desc.{key} 或 shared.config.tenant_desc.{key}
  const platformDescKey = `shared.config.platform_desc.${cfg.key}`;
  const platformDescTranslated = t(platformDescKey);
  if (platformDescTranslated !== platformDescKey) return platformDescTranslated;

  const tenantDescKey = `shared.config.tenant_desc.${cfg.key}`;
  const tenantDescTranslated = t(tenantDescKey);
  if (tenantDescTranslated !== tenantDescKey) return tenantDescTranslated;
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
    // 3. fallback: 尝试 shared.config.platform_options.{key}.{value}
    const platformOptKey = `shared.config.platform_options.${cfg.key}.${o.value}`;
    const platformOptTranslated = t(platformOptKey);
    if (platformOptTranslated !== platformOptKey)
      return { value: o.value, label: platformOptTranslated };

    const tenantOptKey = `shared.config.tenant_options.${cfg.key}.${o.value}`;
    const tenantOptTranslated = t(tenantOptKey);
    if (tenantOptTranslated !== tenantOptKey)
      return { value: o.value, label: tenantOptTranslated };
    // 4. fallback 到 value
    return { value: o.value, label: o.value };
  });
}

/**
 * 递归收集所有配置项的校验规则
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

function getValues(): Record<string, any> {
  return { ...formModel };
}

/**
 * 递归处理子字段，将子字段值合并到父字段 JSON 中
 */
function mergeChildrenToParent(
  cfg: ConfigItemMeta,
  payload: ConfigSubmitPayload,
) {
  if (!cfg.children || cfg.children.length === 0) {
    return;
  }

  // 获取父字段当前的 JSON 值
  let parentValue = payload[cfg.key];
  if (typeof parentValue === 'string') {
    try {
      parentValue = JSON.parse(parentValue);
    } catch {
      parentValue = {};
    }
  }
  if (!parentValue || typeof parentValue !== 'object') {
    parentValue = {};
  }

  // 将子字段的值合并到父字段 JSON 中
  for (const child of cfg.children) {
    if (child.value_path) {
      const childVal = formModel[child.key];
      // 密码字段特殊处理
      if (child.value_type === 'password' && child.is_encrypted) {
        if (childVal && childVal !== '******') {
          setValueByPath(parentValue, child.value_path, childVal);
        }
        // 如果是占位符，不更新
      } else {
        setValueByPath(parentValue, child.value_path, childVal);
      }
      // 从 payload 中删除子字段的独立条目（它已经合并到父字段了）
      delete payload[child.key];
    }

    // 递归处理嵌套的子字段
    if (child.children && child.children.length > 0) {
      mergeChildrenToParent(child, payload);
    }
  }

  // 更新父字段的值
  payload[cfg.key] = parentValue;
}

function prepareSubmitData(): ConfigSubmitPayload {
  const payload: ConfigSubmitPayload = {};

  // 第一步：收集所有字段的值
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
      // 递归收集子字段
      if (cfg.children && cfg.children.length > 0) {
        collectValues(cfg.children);
      }
    }
  };
  collectValues(props.configs || []);

  // 第二步：将子字段值合并到父字段 JSON 中
  (props.configs || []).forEach((cfg) => {
    mergeChildrenToParent(cfg, payload);
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
    autocomplete="off"
  >
    <template v-for="cfg in orderedConfigs" :key="cfg.key">
      <Transition name="config-slide">
        <Form.Item
          v-if="shouldShowConfig(cfg)"
          :name="cfg.key"
          :label="getConfigLabel(cfg)"
          :extra="getConfigDesc(cfg)"
        >
          <!-- string -->
          <Input
            v-if="cfg.value_type === 'string'"
            v-model:value="formModel[cfg.key]"
            autocomplete="new-password"
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
          <div
            v-else-if="cfg.value_type === 'password'"
            class="flex items-center gap-2"
          >
            <Input.Password
              v-model:value="formModel[cfg.key]"
              autocomplete="new-password"
              :visibility-toggle="formModel[cfg.key] !== '******'"
              class="flex-1"
            />
            <slot
              :name="`generate-${cfg.key}`"
              :set-value="(v: string) => (formModel[cfg.key] = v)"
            ></slot>
          </div>

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
                (e) =>
                  (formModel[cfg.key] = (e.target as HTMLInputElement).value)
              "
            />
            <Input v-model:value="formModel[cfg.key]" style="width: 120px" />
          </div>

          <!-- image：使用附件管理器选择图片，存储附件 ID -->
          <ConfigImagePicker
            v-else-if="cfg.value_type === 'image'"
            v-model="formModel[cfg.key]"
          />

          <!-- json with children: render children as sub-fields -->
          <template
            v-else-if="
              cfg.value_type === 'json' &&
              cfg.children &&
              cfg.children.length > 0
            "
          >
            <!-- JSON 类型且有子字段时，不渲染父字段输入框，而是渲染子字段 -->
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
          <Input.TextArea v-else v-model:value="formModel[cfg.key]" :rows="6" />
        </Form.Item>
      </Transition>

      <!-- 渲染 JSON 字段的子字段 -->
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
            <Form.Item
              v-if="shouldShowConfig(child)"
              :name="child.key"
              :label="getConfigLabel(child)"
              :extra="getConfigDesc(child)"
              class="ml-4 border-l-2 border-primary/20 pl-4"
            >
              <!-- string -->
              <Input
                v-if="child.value_type === 'string'"
                v-model:value="formModel[child.key]"
              />

              <!-- number -->
              <InputNumber
                v-else-if="child.value_type === 'number'"
                v-model:value="formModel[child.key]"
                :style="{ width: '100%' }"
                :min="getRuleNumber(child, 'min_value')"
                :max="getRuleNumber(child, 'max_value')"
              />

              <!-- boolean -->
              <Switch
                v-else-if="child.value_type === 'boolean'"
                v-model:checked="formModel[child.key]"
              />

              <!-- select -->
              <Select
                v-else-if="child.value_type === 'select'"
                v-model:value="formModel[child.key]"
                :options="getSelectOptions(child)"
              />

              <!-- multi_select -->
              <Select
                v-else-if="child.value_type === 'multi_select'"
                v-model:value="formModel[child.key]"
                mode="multiple"
                :options="getSelectOptions(child)"
              />

              <!-- text -->
              <Input.TextArea
                v-else-if="child.value_type === 'text'"
                v-model:value="formModel[child.key]"
                :rows="4"
              />

              <!-- password -->
              <Input.Password
                v-else-if="child.value_type === 'password'"
                v-model:value="formModel[child.key]"
                autocomplete="new-password"
                :visibility-toggle="formModel[child.key] !== '******'"
              />

              <!-- color -->
              <div
                v-else-if="child.value_type === 'color'"
                class="flex items-center gap-2"
              >
                <input
                  type="color"
                  :value="formModel[child.key]"
                  class="h-8 w-8 cursor-pointer rounded border border-border"
                  @input="
                    (e) =>
                      (formModel[child.key] = (
                        e.target as HTMLInputElement
                      ).value)
                  "
                />
                <Input
                  v-model:value="formModel[child.key]"
                  style="width: 120px"
                />
              </div>

              <!-- image：使用附件管理器选择图片，存储附件 ID -->
              <ConfigImagePicker
                v-else-if="child.value_type === 'image'"
                v-model="formModel[child.key]"
              />

              <!-- fallback -->
              <Input.TextArea
                v-else
                v-model:value="formModel[child.key]"
                :rows="4"
              />
            </Form.Item>
          </Transition>
        </template>
      </template>
    </template>
  </Form>
</template>

<style scoped>
.config-slide-enter-active,
.config-slide-leave-active {
  max-height: 500px; /* 足够大的高度 */
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
