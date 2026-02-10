<script lang="ts" setup>
defineOptions({ name: 'AIToolForm' });
/**
 * 系统工具新建/编辑表单抽屉
 */
import type { AIToolInfo } from '#/api/admin/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAIToolDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIToolInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => {
    let inputSchema: Record<string, unknown> | null = null;
    let config: Record<string, unknown> | null = null;
    try {
      if (values.input_schema_json) {
        inputSchema = JSON.parse(values.input_schema_json as string);
      }
    } catch {
      // Invalid JSON ignored, validation should catch this
    }
    try {
      if (values.config_json) {
        config = JSON.parse(values.config_json as string);
      }
    } catch {
      // Invalid JSON ignored
    }
    return {
      name: values.name,
      description: values.description || null,
      type: values.type,
      timeout: values.timeout ?? 30,
      is_active: values.is_active ?? true,
      input_schema: inputSchema,
      config,
    };
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      description: data.description,
      type: data.type,
      timeout: data.timeout,
      is_active: data.is_active,
      input_schema_json: data.input_schema
        ? JSON.stringify(data.input_schema, null, 2)
        : '',
      config_json: data.config
        ? JSON.stringify(data.config, null, 2)
        : '',
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIToolDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.tool.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
