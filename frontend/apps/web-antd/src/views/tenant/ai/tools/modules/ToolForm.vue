<script lang="ts" setup>
defineOptions({ name: 'TenantToolForm' });
/**
 * 租户端工具新建/编辑表单抽屉
 */
import type { ToolDefinitionInfo } from '#/api/tenant/tools';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

/**
 * 安全解析 JSON 字符串，失败返回空对象
 */
function safeJsonParse(str: string | undefined): Record<string, unknown> | null {
  if (!str || str.trim() === '' || str.trim() === '{}') return null;
  try {
    return JSON.parse(str) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * 对象转 JSON 字符串（美化格式）
 */
function toJsonString(obj: Record<string, unknown> | null | undefined): string {
  if (!obj || Object.keys(obj).length === 0) return '{}';
  return JSON.stringify(obj, null, 2);
}

const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<ToolDefinitionInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/tools',
  transform: (values) => {
    return {
      name: values.name,
      type: values.type,
      description: values.description || null,
      timeout: values.timeout ?? 30,
      input_schema: safeJsonParse(values.input_schema_str),
      config: safeJsonParse(values.config_str),
      is_active: values.is_active ?? true,
    };
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      type: data.type,
      description: data.description,
      timeout: data.timeout,
      input_schema_str: toJsonString(data.input_schema),
      config_str: toJsonString(data.config),
      is_active: data.is_active,
    };
  },
  onSuccess: () => {
    emits('success');
  },
});

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value
    ? $t('common.edit')
    : $t('tenant.ai.tool.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
