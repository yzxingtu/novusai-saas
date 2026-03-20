<script lang="ts" setup>
/**
 * AI model create/edit form drawer
 * AI 模型新建/编辑表单抽屉
 *
 * After selecting provider, auto-fetches remote model list; selection auto-fills name and code
 * 选择供应商后自动拉取远程模型列表，选择后自动填充 name 和 code
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { AIModelInfo, RemoteModelInfo } from '#/api/admin/ai';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Select, Spin, Tag } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { fetchRemoteModelsApi, getAIModelDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AIModelForm' });

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

/** Provider change callback / 供应商变更回调 */
function onProviderChange(providerId: number) {
  currentProviderId.value = providerId;
}

const { Drawer, isEdit, recordId } = useCrudDrawer<AIModelInfo>({
  formApi,
  schema: (isEditMode: boolean): VbenFormSchema[] =>
    useFormSchema(
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
      rpm_limit: values.rpm_limit || null,
      tpm_limit: values.tpm_limit || null,
      supports_function_calling: values.supports_function_calling ?? false,
      supports_vision: values.supports_vision ?? false,
      supports_audio: values.supports_audio ?? false,
      supports_video: values.supports_video ?? false,
      supports_streaming: values.supports_streaming ?? true,
      max_image_count: values.supports_vision
        ? values.max_image_count || 5
        : null,
      max_image_size_mb: values.supports_vision
        ? values.max_image_size_mb || 10
        : null,
      is_active: values.is_active ?? true,
      fallback_model_id: values.fallback_model_id || null,
      tier: values.tier || null,
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
      rpm_limit: data.rpm_limit,
      tpm_limit: data.tpm_limit,
      supports_function_calling: data.supports_function_calling,
      supports_vision: data.supports_vision,
      supports_audio: data.supports_audio,
      supports_video: data.supports_video,
      supports_streaming: data.supports_streaming,
      max_image_count: data.max_image_count ?? 5,
      max_image_size_mb: data.max_image_size_mb ?? 10,
      is_active: data.is_active,
      fallback_model_id: data.fallback_model_id,
      tier: data.tier,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIModelDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.model.create'),
);

// ==================== Remote model auto-fetch / 远程模型自动拉取 ====================

const remoteModels = ref<RemoteModelInfo[]>([]);
const remoteLoading = ref(false);
const selectedRemoteModel = ref<string | undefined>(undefined);
const currentProviderId = ref<number | undefined>(undefined);

const remoteModelOptions = computed(() =>
  remoteModels.value.map((m) => ({
    label: m.owned_by ? `${m.id} (${m.owned_by})` : m.id,
    value: m.id,
    caps: m.capabilities ?? null,
  })),
);

function filterRemoteOption(
  input: string,
  option?: { label?: string; value?: null | number | string },
): boolean {
  return String(option?.label ?? '')
    .toLowerCase()
    .includes(input.toLowerCase());
}

/** 供应商变更时自动拉取远程模型 / Fetch remote models when provider changes */
async function fetchRemoteByProvider(providerId: number) {
  remoteLoading.value = true;
  selectedRemoteModel.value = undefined;
  remoteModels.value = [];

  try {
    const models = await fetchRemoteModelsApi(providerId);
    remoteModels.value = models;

    // Auto-select first remote model and fill form / 自动选中第一个远程模型并填充表单
    if (models.length > 0) {
      const first = models[0]!;
      selectedRemoteModel.value = first.id;
      onRemoteModelSelect(first.id);
    }
  } catch {
    // Silently handle fetch failure, user can still fill manually / 拉取失败静默处理，用户仍可手动填写
  } finally {
    remoteLoading.value = false;
  }
}

// Watch currentProviderId changes / 监听 currentProviderId 变化
watch(currentProviderId, (newId) => {
  if (newId && !isEdit.value) {
    fetchRemoteByProvider(newId);
  }
});

/** Auto-fill after selecting remote model / 选择远程模型后自动填充 */
function onRemoteModelSelect(modelId: unknown) {
  if (!modelId || typeof modelId !== 'string') return;

  const model = remoteModels.value.find((m) => m.id === modelId);
  const caps = model?.capabilities;

  const defaults = getFormDefaults();
  const providerId = currentProviderId.value;

  const values: Record<string, unknown> = {
    ...defaults,
    provider_id: providerId,
    code: modelId,
    name: modelId,
    context_window: null,
    max_output_tokens: null,
    input_price_per_1k: null,
    output_price_per_1k: null,
    rpm_limit: null,
    tpm_limit: null,
    fallback_model_id: null,
  };

  if (caps) {
    if (caps.model_type) values.type = caps.model_type;
    if (caps.supports_vision != null)
      values.supports_vision = caps.supports_vision;
    if (caps.supports_audio != null) values.supports_audio = caps.supports_audio;
    if (caps.supports_video != null) values.supports_video = caps.supports_video;
    if (caps.supports_function_calling != null)
      values.supports_function_calling = caps.supports_function_calling;
    if (caps.supports_streaming != null)
      values.supports_streaming = caps.supports_streaming;
    if (caps.context_window != null) values.context_window = caps.context_window;
    if (caps.max_output_tokens != null)
      values.max_output_tokens = caps.max_output_tokens;
    if (caps.input_price_per_1k != null)
      values.input_price_per_1k = caps.input_price_per_1k;
    if (caps.output_price_per_1k != null)
      values.output_price_per_1k = caps.output_price_per_1k;
    if (caps.rpm_limit != null) values.rpm_limit = caps.rpm_limit;
    if (caps.tpm_limit != null) values.tpm_limit = caps.tpm_limit;
  }

  formApi.setValues(values);
}
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <!-- 远程模型选择（仅新建模式，选择供应商后自动加载） -->
    <div
      v-if="!isEdit && remoteModelOptions.length > 0"
      class="mb-4 rounded-lg border border-border bg-accent/30 p-3"
    >
      <div
        class="mb-2 flex items-center gap-1.5 text-sm font-medium text-foreground"
      >
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
      >
        <template #option="{ label: optLabel, caps }">
          <div class="flex items-center gap-1.5">
            <span class="truncate">{{ optLabel }}</span>
            <template v-if="caps">
              <Tag
                v-if="caps.supports_vision"
                color="blue"
                class="mr-0 leading-tight"
                >Vision</Tag
              >
              <Tag
                v-if="caps.supports_function_calling"
                color="green"
                class="mr-0 leading-tight"
                >Tools</Tag
              >
            </template>
          </div>
        </template>
      </Select>
      <div class="mt-1 text-xs text-muted-foreground">
        {{
          $t('admin.ai.model.fetchRemoteSuccess', {
            count: remoteModelOptions.length,
          })
        }}
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
