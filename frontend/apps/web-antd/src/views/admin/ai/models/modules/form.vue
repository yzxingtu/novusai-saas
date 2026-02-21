<script lang="ts" setup>
defineOptions({ name: 'AIModelForm' });
/**
 * AI 模型新建/编辑表单抽屉
 *
 * 选择供应商后自动拉取远程模型列表，选择后自动填充 name 和 code
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AIModelInfo, RemoteModelInfo } from '#/api/admin/ai';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Select, Spin } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { fetchRemoteModelsApi, getAIModelDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

/** 供应商变更回调 */
function onProviderChange(providerId: number) {
  currentProviderId.value = providerId;
}

const { Drawer, isEdit, recordId } = useCrudDrawer<AIModelInfo>({
  formApi,
  schema: (isEditMode: boolean): VbenFormSchema[] => useFormSchema(
    isEditMode,
    isEditMode ? (recordId.value as number) : undefined,
    isEditMode ? undefined : onProviderChange,
  ),
  defaults: getFormDefaults,
  transform: (values) => {
    return {
      name: values.name,
      code: values.code,
      type: values.type,
      provider_id: values.provider_id,
      context_window: values.context_window || null,
      max_output_tokens: values.max_output_tokens || null,
      input_price_per_1k: values.input_price_per_1k || null,
      output_price_per_1k: values.output_price_per_1k || null,
      supports_function_calling: values.supports_function_calling ?? false,
      supports_vision: values.supports_vision ?? false,
      supports_streaming: values.supports_streaming ?? true,
      max_image_count: values.supports_vision ? (values.max_image_count || 5) : null,
      max_image_size_mb: values.supports_vision ? (values.max_image_size_mb || 10) : null,
      is_active: values.is_active ?? true,
    };
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      code: data.code,
      type: data.type,
      provider_id: data.provider_id,
      context_window: data.context_window,
      max_output_tokens: data.max_output_tokens,
      input_price_per_1k: data.input_price_per_1k,
      output_price_per_1k: data.output_price_per_1k,
      supports_function_calling: data.supports_function_calling,
      supports_vision: data.supports_vision,
      supports_streaming: data.supports_streaming,
      max_image_count: data.max_image_count ?? 5,
      max_image_size_mb: data.max_image_size_mb ?? 10,
      is_active: data.is_active,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIModelDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.model.create'),
);

// ==================== 远程模型自动拉取 ====================

const remoteModels = ref<RemoteModelInfo[]>([]);
const remoteLoading = ref(false);
const selectedRemoteModel = ref<string | undefined>(undefined);
const currentProviderId = ref<number | undefined>(undefined);

const remoteModelOptions = computed(() =>
  remoteModels.value.map((m) => ({
    label: m.owned_by ? `${m.id} (${m.owned_by})` : m.id,
    value: m.id,
  })),
);

function filterRemoteOption(
  input: string,
  option?: { label?: string; value?: null | number | string },
): boolean {
  return String(option?.label ?? '').toLowerCase().includes(input.toLowerCase());
}

/** 供应商变更时自动拉取远程模型 */
async function fetchRemoteByProvider(providerId: number) {
  remoteLoading.value = true;
  selectedRemoteModel.value = undefined;
  remoteModels.value = [];

  try {
    const models = await fetchRemoteModelsApi(providerId);
    remoteModels.value = models;

    // 自动选中第一个远程模型并填充表单
    if (models.length > 0) {
      const first = models[0]!;
      selectedRemoteModel.value = first.id;
      onRemoteModelSelect(first.id);
    }
  } catch {
    // 拉取失败静默处理，用户仍可手动填写
  } finally {
    remoteLoading.value = false;
  }
}

// 监听 currentProviderId 变化
watch(currentProviderId, (newId) => {
  if (newId && !isEdit.value) {
    fetchRemoteByProvider(newId);
  }
});

/** 选择远程模型后自动填充 */
function onRemoteModelSelect(modelId: unknown) {
  if (!modelId || typeof modelId !== 'string') return;
  formApi.setValues({
    code: modelId,
    name: modelId,
  });
}
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <!-- 远程模型选择（仅新建模式，选择供应商后自动加载） -->
    <div
      v-if="!isEdit && remoteModelOptions.length > 0"
      class="mb-4 rounded-lg border border-border bg-accent/30 p-3"
    >
      <div class="mb-2 flex items-center gap-1.5 text-sm font-medium text-foreground">
        <IconifyIcon icon="lucide:cloud-download" class="size-4 text-primary" />
        {{ $t('admin.ai.model.selectRemoteModel') }}
      </div>
      <Select
        v-model:value="selectedRemoteModel"
        :filter-option="filterRemoteOption"
        :options="remoteModelOptions"
        :placeholder="$t('admin.ai.model.placeholder.selectRemoteModel')"
        allow-clear
        show-search
        class="w-full"
        @change="onRemoteModelSelect"
      />
      <div class="mt-1 text-xs text-muted-foreground">
        {{ $t('admin.ai.model.fetchRemoteSuccess', { count: remoteModelOptions.length }) }}
      </div>
    </div>
    <div
      v-else-if="!isEdit && remoteLoading"
      class="mb-4 flex items-center justify-center gap-2 rounded-lg border border-border bg-accent/30 p-4 text-sm text-muted-foreground"
    >
      <Spin size="small" />
      {{ $t('admin.ai.model.fetchRemoteLoading') }}
    </div>
    <Form />
  </Drawer>
</template>
