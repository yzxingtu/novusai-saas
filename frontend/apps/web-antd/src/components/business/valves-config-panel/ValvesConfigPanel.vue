<script lang="ts" setup>
/**
 * Valves 配置面板（共享组件）
 *
 * 根据 valves_schema（JSON Schema）动态渲染环境变量配置表单，
 * 支持加载已保存的 valves_config 并提交更新。
 *
 * 通过 props 注入 API 函数和 i18n 前缀，适配 admin/tenant 两端。
 */
import { ref, computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Drawer,
  Form,
  FormItem,
  Input,
  InputNumber,
  message,
  Spin,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

interface ValvesProperty {
  type: string;
  description?: string;
  default?: unknown;
}

interface ValvesSchema {
  type: string;
  properties: Record<string, ValvesProperty>;
  required?: string[];
}

interface ValvesInfo {
  valves_schema: ValvesSchema | null;
  valves_config: Record<string, unknown> | null;
}

const props = defineProps<{
  packageId: number | null;
  packageName?: string;
  /** i18n 前缀，如 'admin.ai.skillPackage' 或 'tenant.ai.skillPackage' */
  i18nPrefix: string;
  /** 获取 Valves 配置的 API 函数 */
  getValvesApi: (packageId: number) => Promise<ValvesInfo>;
  /** 更新 Valves 配置的 API 函数 */
  updateValvesApi: (
    packageId: number,
    data: { valves_config: Record<string, unknown> },
  ) => Promise<unknown>;
}>();

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const visible = ref(false);
const loading = ref(false);
const saving = ref(false);
const schema = ref<ValvesSchema | null>(null);
const formValues = ref<Record<string, unknown>>({});

const sortedFields = computed(() => {
  if (!schema.value?.properties) return [];
  const required = new Set(schema.value.required || []);
  return Object.entries(schema.value.properties)
    .map(([key, prop]) => ({
      key,
      ...prop,
      isRequired: required.has(key),
    }))
    .sort((a, b) => {
      // required first, then alphabetical
      if (a.isRequired !== b.isRequired) return a.isRequired ? -1 : 1;
      return a.key.localeCompare(b.key);
    });
});

async function open() {
  if (!props.packageId) return;
  visible.value = true;
  loading.value = true;
  try {
    const res = await props.getValvesApi(props.packageId);
    schema.value = res.valves_schema || null;
    const saved = (res.valves_config || {}) as Record<string, unknown>;

    // Initialize form: merge defaults + saved values
    const initial: Record<string, unknown> = {};
    if (schema.value?.properties) {
      for (const [key, prop] of Object.entries(schema.value.properties)) {
        if (key in saved) {
          initial[key] = saved[key];
        } else if (prop.default !== undefined) {
          initial[key] = prop.default;
        } else {
          initial[key] = '';
        }
      }
    }
    formValues.value = initial;
  } catch {
    schema.value = null;
  } finally {
    loading.value = false;
  }
}

function onResetDefaults() {
  if (!schema.value?.properties) return;
  const defaults: Record<string, unknown> = {};
  for (const [key, prop] of Object.entries(schema.value.properties)) {
    defaults[key] = prop.default !== undefined ? prop.default : '';
  }
  formValues.value = defaults;
}

async function onSave() {
  if (!props.packageId) return;
  saving.value = true;
  try {
    await props.updateValvesApi(props.packageId, {
      valves_config: formValues.value,
    });
    message.success($t(`${props.i18nPrefix}.valves.saveSuccess`));
    emit('success');
    visible.value = false;
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false;
  }
}

function getInputType(type: string) {
  switch (type) {
    case 'integer':
    case 'number': {
      return 'number';
    }
    case 'boolean': {
      return 'switch';
    }
    case 'array':
    case 'object': {
      return 'json';
    }
    default: {
      return 'string';
    }
  }
}

function isSecret(key: string): boolean {
  return /\b(api_?key|secret|password|access_?token|auth_?token|apikey|private_?key)\b/i.test(key);
}

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="$t(`${i18nPrefix}.valves.title`)"
    width="520"
    :destroy-on-close="false"
    :footer-style="{ textAlign: 'right' }"
  >
    <template #extra>
      <span v-if="packageName" class="text-sm text-muted-foreground">
        {{ packageName }}
      </span>
    </template>

    <Spin :spinning="loading">
      <template v-if="schema && sortedFields.length > 0">
        <Alert
          :message="$t(`${i18nPrefix}.valves.description`)"
          type="info"
          show-icon
          class="mb-4"
        />

        <Form layout="vertical">
          <FormItem
            v-for="field in sortedFields"
            :key="field.key"
            :required="field.isRequired"
          >
            <template #label>
              <div class="flex items-center gap-1.5">
                <code class="rounded bg-accent px-1.5 py-0.5 text-xs font-mono">
                  {{ field.key }}
                </code>
                <Tag
                  v-if="field.isRequired"
                  color="red"
                  style="font-size: 10px; line-height: 14px; padding: 0 3px; margin: 0;"
                >
                  {{ $t(`${i18nPrefix}.valves.required`) }}
                </Tag>
                <Tooltip v-if="isSecret(field.key)">
                  <template #title>
                    {{ $t(`${i18nPrefix}.valves.sensitiveHint`) }}
                  </template>
                  <IconifyIcon icon="lucide:shield" class="size-3 text-warning" />
                </Tooltip>
              </div>
            </template>

            <template #help>
              <span v-if="field.description" class="text-xs">
                {{ field.description }}
              </span>
            </template>

            <!-- Boolean → Switch -->
            <Switch
              v-if="getInputType(field.type) === 'switch'"
              :checked="!!formValues[field.key]"
              @update:checked="(val: unknown) => (formValues[field.key] = !!val)"
            />

            <!-- Number → InputNumber -->
            <InputNumber
              v-else-if="getInputType(field.type) === 'number'"
              v-model:value="(formValues[field.key] as number)"
              class="w-full"
              :placeholder="field.default !== undefined ? String(field.default) : ''"
            />

            <!-- Array/Object → JSON Textarea -->
            <Input.TextArea
              v-else-if="getInputType(field.type) === 'json'"
              :value="typeof formValues[field.key] === 'string' ? (formValues[field.key] as string) : JSON.stringify(formValues[field.key], null, 2)"
              :rows="4"
              :placeholder="field.default !== undefined ? JSON.stringify(field.default) : '[]'"
              class="font-mono text-xs"
              @update:value="(val: string) => { try { formValues[field.key] = JSON.parse(val); } catch { formValues[field.key] = val; } }"
            />

            <!-- String → Input / Password (secret) -->
            <div v-else-if="isSecret(field.key)" class="flex items-center gap-2">
              <Input.Password
                v-model:value="(formValues[field.key] as string)"
                :placeholder="field.default !== undefined ? String(field.default) : ''"
                class="flex-1"
              />
              <Tag
                v-if="formValues[field.key] === '******'"
                color="green"
                style="font-size: 10px; line-height: 14px; padding: 0 4px; margin: 0; cursor: pointer;"
                @click="formValues[field.key] = ''"
              >
                {{ $t(`${i18nPrefix}.valves.secretConfigured`) }}
              </Tag>
            </div>
            <Input
              v-else
              v-model:value="(formValues[field.key] as string)"
              :placeholder="field.default !== undefined ? String(field.default) : ''"
            />
          </FormItem>
        </Form>
      </template>

      <div v-else-if="!loading" class="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <IconifyIcon icon="lucide:settings-2" class="mb-2 size-10 opacity-40" />
        <span>{{ $t(`${i18nPrefix}.valves.noSchema`) }}</span>
      </div>
    </Spin>

    <template #footer>
      <div class="flex items-center justify-between">
        <Button
          v-if="schema"
          size="small"
          @click="onResetDefaults"
        >
          <IconifyIcon icon="lucide:rotate-ccw" class="mr-1 size-3.5" />
          {{ $t(`${i18nPrefix}.valves.resetDefaults`) }}
        </Button>
        <span v-else />
        <div>
          <Button class="mr-2" @click="visible = false">
            {{ $t('common.cancel') }}
          </Button>
          <Button
            type="primary"
            :loading="saving"
            :disabled="!schema || loading"
            @click="onSave"
          >
            {{ $t('common.save') }}
          </Button>
        </div>
      </div>
    </template>
  </Drawer>
</template>
