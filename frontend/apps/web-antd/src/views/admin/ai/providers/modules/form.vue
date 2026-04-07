<script lang="ts" setup>
/**
 * AI 供应商新建/编辑表单抽屉
 */
import type { AIProviderInfo, ProviderWebSearchRuntime } from '#/api/admin/ai';

import { computed, ref } from 'vue';

import { message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getAIProviderDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import {
  buildProviderWebSearchConfigFromForm,
  getFormDefaults,
  getProviderWebSearchRuntimeSummary,
  hasForbiddenProviderEndpointSuffix,
  hasLikelyMissingProviderApiVersion,
  isResponsesToolHistoryCompatEnabled,
  normalizeProviderBaseUrlInput,
  resolveProviderWireApi,
  resolveProviderWebSearchConfig,
  shouldWarnProviderWebSearchAutoFallback,
  useFormSchema,
} from '../data';

defineOptions({ name: 'AIProviderForm' });

const emits = defineEmits<{ success: [] }>();
const configSnapshot = ref<null | Record<string, unknown>>(null);
const webSearchRuntime = ref<null | ProviderWebSearchRuntime>(null);
const webSearchRuntimeSummary = computed(() =>
  getProviderWebSearchRuntimeSummary(webSearchRuntime.value),
);
const shouldShowWebSearchRuntimeHint = computed(() =>
  shouldWarnProviderWebSearchAutoFallback(webSearchRuntime.value),
);

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
      message.warning(
        $t('admin.ai.provider.validation.baseUrlLikelyMissingVersion'),
      );
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

    const existingWebSearchConfig = edit
      ? resolveProviderWebSearchConfig(configSnapshot.value)
      : undefined;
    nextConfig.web_search = buildProviderWebSearchConfigFromForm(
      values as Record<string, unknown>,
      existingWebSearchConfig,
    );

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
    webSearchRuntime.value = data.web_search_runtime || null;
    const effectiveWireApi = resolveProviderWireApi(
      data.type,
      typeof data.config?.wire_api === 'string' ? data.config.wire_api : null,
    );
    const webSearchConfig = resolveProviderWebSearchConfig(data.config);
    return {
      name: data.name,
      code: data.code,
      type: data.type,
      base_url: data.base_url,
      wire_api: effectiveWireApi || 'chat_completions',
      responses_tool_history_compat: isResponsesToolHistoryCompatEnabled(
        data.config,
      ),
      web_search_enabled: webSearchConfig.enabled,
      web_search_strategy: webSearchConfig.strategy,
      web_search_max_results_cap: webSearchConfig.max_results_cap,
      web_search_native_timeout_seconds: webSearchConfig.native_timeout_seconds,
      web_search_public_timeout_seconds: webSearchConfig.public_timeout_seconds,
      web_search_public_providers: [...webSearchConfig.public_providers],
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
    <div
      v-if="isEdit"
      class="mt-3 rounded-md border border-border/80 bg-muted/40 p-3 text-xs leading-5 text-muted-foreground"
    >
      <div class="font-medium text-foreground">
        {{ $t('admin.ai.provider.webSearch.runtime.title') }}
      </div>
      <div class="mt-1">
        {{ webSearchRuntimeSummary }}
      </div>
      <div
        v-if="shouldShowWebSearchRuntimeHint"
        class="mt-1 text-amber-600 dark:text-amber-400"
      >
        {{ $t('admin.ai.provider.webSearch.runtime.autoFallbackHint') }}
      </div>
    </div>
  </Drawer>
</template>
