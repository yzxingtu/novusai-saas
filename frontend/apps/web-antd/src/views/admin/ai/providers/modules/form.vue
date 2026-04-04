<script lang="ts" setup>
/**
 * AI 供应商新建/编辑表单抽屉
 */
import type { AIProviderInfo } from '#/api/admin/ai';

import { computed, ref } from 'vue';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getAIProviderDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import {
  getFormDefaults,
  hasLikelyMissingProviderApiVersion,
  hasForbiddenProviderEndpointSuffix,
  isResponsesToolHistoryCompatEnabled,
  normalizeProviderBaseUrlInput,
  resolveProviderWireApi,
  useFormSchema,
} from '../data';

defineOptions({ name: 'AIProviderForm' });

const emits = defineEmits<{ success: [] }>();
const configSnapshot = ref<null | Record<string, unknown>>(null);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AIProviderInfo>({
  formApi,
  schema: (edit) => useFormSchema(edit),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const normalizedBaseUrl = normalizeProviderBaseUrlInput(
      typeof values.base_url === 'string' ? values.base_url : null,
    );
    if (
      hasForbiddenProviderEndpointSuffix(
        normalizedBaseUrl,
        typeof values.type === 'string' ? values.type : null,
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
        typeof values.type === 'string' ? values.type : null,
      )
    ) {
      message.warning($t('admin.ai.provider.validation.baseUrlLikelyMissingVersion'));
    }

    const effectiveWireApi = resolveProviderWireApi(
      typeof values.type === 'string' ? values.type : null,
      typeof values.wire_api === 'string' ? values.wire_api : null,
    );

    const nextConfig =
      edit && configSnapshot.value ? { ...configSnapshot.value } : {};
    if (values.type === 'openai_compatible') {
      nextConfig.wire_api = effectiveWireApi || 'chat_completions';
      if (
        effectiveWireApi === 'responses' &&
        values.responses_tool_history_compat === true
      ) {
        nextConfig.responses_tool_history_mode = 'text';
      } else {
        delete nextConfig.responses_tool_history_mode;
      }
    } else {
      delete nextConfig.wire_api;
      delete nextConfig.responses_tool_history_mode;
    }

    const result: Record<string, unknown> = {
      name: values.name,
      type: values.type,
      base_url: normalizedBaseUrl,
      description: values.description || null,
      icon: values.icon || null,
      sort_order: values.sort_order ?? 0,
      is_active: values.is_active ?? true,
      config: Object.keys(nextConfig).length > 0 ? nextConfig : null,
    };
    if (!edit) {
      result.code = values.code;
    }
    return result;
  },
  toFormValues: (data) => {
    configSnapshot.value =
      data.config && typeof data.config === 'object'
        ? { ...data.config }
        : null;
    const effectiveWireApi = resolveProviderWireApi(
      data.type,
      typeof data.config?.wire_api === 'string' ? data.config.wire_api : null,
    );
    return {
      name: data.name,
      code: data.code,
      type: data.type,
      base_url: data.base_url,
      wire_api: effectiveWireApi || 'chat_completions',
      responses_tool_history_compat: isResponsesToolHistoryCompatEnabled(
        data.config,
      ),
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
