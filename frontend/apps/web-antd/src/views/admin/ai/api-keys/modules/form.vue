<script lang="ts" setup>
/**
 * AI API Key 新建/编辑表单抽屉
 */
import type { AIApiKeyInfo } from '#/api/admin/ai';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAIApiKeyDetailApi } from '#/api/admin/ai';
import {
  extractScopeFormValues,
  extractScopePayload,
} from '#/components/business/scope-select';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AIApiKeyForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(false),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIApiKeyInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => {
    const data: Record<string, unknown> = {
      name: values.name,
      is_active: values.is_active ?? true,
      usage_limit: values.usage_limit || null,
    };
    if (!isEdit.value) {
      data.provider_id = values.provider_id;
      data.api_key = values.api_key;
      Object.assign(data, extractScopePayload(values, 'scope', true));
    }
    return data;
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      provider_id: data.provider_id,
      is_active: data.is_active,
      usage_limit: data.usage_limit,
      ...extractScopeFormValues(data),
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIApiKeyDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.apiKey.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
