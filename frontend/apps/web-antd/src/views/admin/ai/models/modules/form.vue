<script lang="ts" setup>
/**
 * AI model create/edit form drawer
 * AI 模型新建/编辑表单抽屉
 *
 * After selecting provider, auto-fetches remote model list; selection auto-fills name and code
 * 选择供应商后自动拉取远程模型列表，选择后自动填充 name 和 code
 */
import type { VbenFormSchema } from '#/adapter/form';
import type {
  AIModelConfig,
  AIModelInfo,
  RemoteModelInfo,
} from '#/api/admin/ai';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Select, Spin, Tag } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import {
  fetchRemoteModelsApi,
  getAIModelDetailApi,
  getAIProviderDetailApi,
} from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import {
  buildModelFormValues,
  buildModelPayload,
  buildRemoteModelFormValues,
  getFormDefaults,
  useFormSchema,
} from '../data';

defineOptions({ name: 'AIModelForm' });

const emits = defineEmits<{ success: [] }>();
const configSnapshot = ref<AIModelConfig | null>(null);

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
      onProviderChange,
    ),
  defaults: getFormDefaults,
  transform: (values) => buildModelPayload(values, configSnapshot.value),
  toFormValues: (data) => {
    configSnapshot.value =
      data.config && typeof data.config === 'object'
        ? { ...data.config }
        : null;
    currentProviderId.value = data.provider_id;
    currentProviderType.value = data.provider_type || null;
    if (!data.provider_type && data.provider_id) {
      void syncProviderType(data.provider_id);
    }
    return buildModelFormValues(data);
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
const currentProviderType = ref<null | string>(null);

const remoteModelOptions = computed(() =>
  remoteModels.value.map((m) => ({
    label: m.owned_by ? `${m.id} (${m.owned_by})` : m.id,
    value: m.id,
    caps: m.capabilities ?? null,
  })),
);

async function syncProviderType(providerId: number) {
  try {
    const provider = await getAIProviderDetailApi(providerId);
    currentProviderType.value = provider.type;
    formApi.setValues({ provider_type: provider.type });
  } catch {
    currentProviderType.value = null;
    formApi.setValues({ provider_type: null });
  }
}

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
    void syncProviderType(newId);
    fetchRemoteByProvider(newId);
  }
});

watch(isEdit, (editing) => {
  if (!editing) {
    configSnapshot.value = null;
  }
});

/** Auto-fill after selecting remote model / 选择远程模型后自动填充 */
function onRemoteModelSelect(modelId: unknown) {
  if (!modelId || typeof modelId !== 'string') return;

  const model = remoteModels.value.find((m) => m.id === modelId);
  configSnapshot.value = null;
  formApi.setValues(
    buildRemoteModelFormValues(
      modelId,
      currentProviderId.value,
      currentProviderType.value,
      model?.capabilities,
    ),
  );
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
              >
                Vision
              </Tag>
              <Tag
                v-if="caps.supports_function_calling"
                color="green"
                class="mr-0 leading-tight"
              >
                Tools
              </Tag>
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
