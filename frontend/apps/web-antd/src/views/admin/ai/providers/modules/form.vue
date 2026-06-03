<script lang="ts" setup>
/**
 * AI 供应商新建/编辑表单抽屉
 */
import type {
  AIProviderConfig,
  AIProviderInfo,
} from '#/api/admin/ai-providers';

import { computed, ref } from 'vue';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getAIProviderDetailApi } from '#/api/admin/ai-providers';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import {
  buildProviderConfigWithPrimaryWireApi,
  getDefaultProviderType,
  getFormDefaults,
  hasForbiddenProviderEndpointSuffix,
  hasLikelyMissingProviderApiVersion,
  loadAdapterTypes,
  normalizeProviderBaseUrlInput,
  resolveProviderPrimaryWireApi,
  useFormSchema,
} from '../data';

defineOptions({ name: 'AIProviderForm' });

const emits = defineEmits<{ success: [] }>();
const configSnapshot = ref<AIProviderConfig | null>(null);
const providerTypeSnapshot = ref(getDefaultProviderType());

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIProviderInfo>({
  formApi,
  schema: (edit) => useFormSchema(edit),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const effectiveProviderType =
      typeof values.type === 'string' && values.type.trim()
        ? values.type
        : providerTypeSnapshot.value;
    const normalizedBaseUrl = normalizeProviderBaseUrlInput(
      typeof values.base_url === 'string' ? values.base_url : null,
    );
    if (
      hasForbiddenProviderEndpointSuffix(
        normalizedBaseUrl,
        effectiveProviderType,
      )
    ) {
      message.error(
        $t('admin.ai.provider.validation.baseUrlEndpointNotAllowed'),
      );
      throw new Error('Provider base_url must not include endpoint path');
    }
    if (
      hasLikelyMissingProviderApiVersion(
        normalizedBaseUrl,
        effectiveProviderType,
      )
    ) {
      message.warning(
        $t('admin.ai.provider.validation.baseUrlLikelyMissingVersion'),
      );
    }

    const nextConfig = buildProviderConfigWithPrimaryWireApi(
      edit ? configSnapshot.value : null,
      effectiveProviderType,
      typeof values.primary_wire_api === 'string'
        ? values.primary_wire_api
        : null,
    );

    const result: Record<string, unknown> = {
      name: values.name,
      type: effectiveProviderType,
      base_url: normalizedBaseUrl,
      description: values.description || null,
      icon: values.icon || null,
      sort_order: values.sort_order ?? 0,
      is_active: values.is_active ?? true,
      config: nextConfig,
    };
    if (!edit) {
      result.code = values.code;
    }
    return result;
  },
  onOpen: async () => {
    await loadAdapterTypes();
    providerTypeSnapshot.value = getDefaultProviderType();
  },
  toFormValues: (data) => {
    configSnapshot.value =
      data.config && typeof data.config === 'object'
        ? { ...data.config }
        : null;
    providerTypeSnapshot.value = data.type || getDefaultProviderType();
    const effectiveWireApi = resolveProviderPrimaryWireApi(
      data.type,
      data.config,
    );
    return {
      name: data.name,
      code: data.code,
      type: data.type,
      base_url: data.base_url,
      primary_wire_api: effectiveWireApi,
      description: data.description,
      icon: data.icon,
      sort_order: data.sort_order,
      is_active: data.is_active,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIProviderDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.provider.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
