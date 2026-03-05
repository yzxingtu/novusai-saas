<script lang="ts" setup>
/**
 * 存储凭证表单
 *
 * 根据选中的存储驱动动态渲染对应的凭证字段。
 * 支持 4 种云存储驱动：s3、aliyun-oss、qiniu-kodo、tencent-cos。
 * 管理端和租户端存储配置页面共用。
 */
import { computed, nextTick, reactive, watch } from 'vue';

import { Form, FormItem, Input, InputPassword, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'StorageCredentialForm' });

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    driver: null | string;
    value?: CredentialValue;
  }>(),
  {
    disabled: false,
    value: () => ({ root_path: '', base_url: '', options: {} }),
  },
);

const emit = defineEmits<{
  'update:value': [value: CredentialValue];
}>();

interface CredentialValue {
  root_path: string;
  base_url: string;
  options: Record<string, unknown>;
}

const formState = reactive<Record<string, any>>({});
let isSyncingFromProps = false;

// 同步外部 props.value → 内部 formState
watch(
  () => props.value,
  (val) => {
    if (!val) return;
    isSyncingFromProps = true;
    // 先清理 formState 中不再属于新值的旧 key，防止脏状态残留
    const newKeys = new Set([
      'base_url',
      'root_path',
      ...Object.keys(val.options || {}),
    ]);
    Object.keys(formState).forEach((key) => {
      if (!newKeys.has(key)) {
        delete formState[key];
      }
    });
    formState.root_path = val.root_path || '';
    formState.base_url = val.base_url || '';
    const opts = val.options || {};
    Object.keys(opts).forEach((k) => {
      const v = opts[k];
      if (
        typeof v === 'string' ||
        typeof v === 'number' ||
        typeof v === 'boolean'
      ) {
        formState[k] = v;
      }
    });
    nextTick(() => {
      isSyncingFromProps = false;
    });
  },
  { immediate: true, deep: true },
);

// 用户编辑字段时自动向外 emit（由 v-model 驱动 formState 变化）
watch(
  formState,
  () => {
    if (isSyncingFromProps) return;
    const { root_path, base_url, ...rest } = formState;
    const options: Record<string, unknown> = {};
    Object.keys(rest).forEach((k) => {
      if (rest[k] !== undefined && rest[k] !== '') {
        options[k] = rest[k];
      }
    });
    emit('update:value', {
      root_path: (root_path as string) || '',
      base_url: (base_url as string) || '',
      options,
    });
  },
  { deep: true },
);

interface FieldDef {
  key: string;
  label: string;
  type: 'boolean' | 'password' | 'text';
  required?: boolean;
  placeholder?: string;
}

const fieldsByDriver = computed<FieldDef[]>(() => {
  const d = props.driver;
  if (!d || d === 'local') return [];

  const common: FieldDef[] = [
    {
      key: 'root_path',
      label: 'shared.storage.field.bucket',
      type: 'text',
      required: true,
      placeholder: 'my-bucket',
    },
    {
      key: 'base_url',
      label: 'shared.storage.field.baseUrl',
      type: 'text',
      placeholder: 'https://cdn.example.com',
    },
  ];

  if (d === 's3') {
    return [
      ...common,
      {
        key: 'access_key_id',
        label: 'shared.storage.field.accessKeyId',
        type: 'text',
        required: true,
      },
      {
        key: 'secret_access_key',
        label: 'shared.storage.field.secretAccessKey',
        type: 'password',
        required: true,
      },
      {
        key: 'region',
        label: 'shared.storage.field.region',
        type: 'text',
        placeholder: 'us-east-1',
      },
      {
        key: 'endpoint_url',
        label: 'shared.storage.field.endpointUrl',
        type: 'text',
        placeholder: 'https://s3.amazonaws.com',
      },
      {
        key: 'prefix',
        label: 'shared.storage.field.prefix',
        type: 'text',
      },
    ];
  }

  if (d === 'aliyun-oss') {
    return [
      ...common,
      {
        key: 'access_key_id',
        label: 'shared.storage.field.accessKeyId',
        type: 'text',
        required: true,
      },
      {
        key: 'access_key_secret',
        label: 'shared.storage.field.accessKeySecret',
        type: 'password',
        required: true,
      },
      {
        key: 'endpoint',
        label: 'shared.storage.field.endpoint',
        type: 'text',
        placeholder: 'oss-cn-hangzhou.aliyuncs.com',
      },
      {
        key: 'region',
        label: 'shared.storage.field.region',
        type: 'text',
        placeholder: 'cn-hangzhou',
      },
      {
        key: 'prefix',
        label: 'shared.storage.field.prefix',
        type: 'text',
      },
    ];
  }

  if (d === 'qiniu-kodo') {
    return [
      ...common,
      {
        key: 'access_key',
        label: 'shared.storage.field.accessKeyId',
        type: 'text',
        required: true,
      },
      {
        key: 'secret_key',
        label: 'shared.storage.field.secretKey',
        type: 'password',
        required: true,
      },
      {
        key: 'prefix',
        label: 'shared.storage.field.prefix',
        type: 'text',
      },
      {
        key: 'is_private',
        label: 'shared.storage.field.isPrivate',
        type: 'boolean',
      },
    ];
  }

  if (d === 'tencent-cos') {
    return [
      ...common,
      {
        key: 'secret_id',
        label: 'shared.storage.field.secretId',
        type: 'text',
        required: true,
      },
      {
        key: 'secret_key',
        label: 'shared.storage.field.secretKey',
        type: 'password',
        required: true,
      },
      {
        key: 'region',
        label: 'shared.storage.field.region',
        type: 'text',
        placeholder: 'ap-guangzhou',
      },
      {
        key: 'prefix',
        label: 'shared.storage.field.prefix',
        type: 'text',
      },
    ];
  }

  // 未知驱动兜底：只显示通用字段
  return common;
});

// 驱动切换时清理不属于当前驱动的旧字段
watch(
  () => props.driver,
  () => {
    isSyncingFromProps = true;
    const validKeys = new Set(fieldsByDriver.value.map((f) => f.key));
    Object.keys(formState).forEach((key) => {
      if (!validKeys.has(key)) {
        delete formState[key];
      }
    });
    nextTick(() => {
      isSyncingFromProps = false;
    });
  },
);
</script>

<template>
  <Form layout="vertical" :disabled="disabled" autocomplete="off">
    <template v-for="field in fieldsByDriver" :key="field.key">
      <FormItem :label="$t(field.label)" :required="field.required">
        <Switch
          v-if="field.type === 'boolean'"
          v-model:checked="formState[field.key]"
        />
        <InputPassword
          v-else-if="field.type === 'password'"
          v-model:value="formState[field.key]"
          :placeholder="field.placeholder || ''"
          autocomplete="new-password"
        />
        <Input
          v-else
          v-model:value="formState[field.key]"
          :placeholder="field.placeholder || ''"
          autocomplete="new-password"
        />
      </FormItem>
    </template>
    <div
      v-if="!driver || driver === 'local'"
      class="py-4 text-center text-muted-foreground"
    >
      {{ $t('shared.storage.selectDriverFirst') }}
    </div>
  </Form>
</template>
