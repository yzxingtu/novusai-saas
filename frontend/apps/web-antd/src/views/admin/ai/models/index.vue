<script lang="ts" setup>
/**
 * AI 模型管理列表页面
 */
import type { AIModelInfo } from '#/api/admin/ai';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Modal, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAIModelListApi,
  testAIGatewayApi,
  toggleAIModelStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';
import { getProcessedImageUrl } from '#/utils/image';

import {
  getFormDefaults,
  getModelTierText,
  getModelTypeText,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'AIModelList' });

/**
 * 格式化 Token 数量
 */
function formatTokens(num: null | number | undefined): string {
  if (!num) return '-';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(0)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return `${num}`;
}

/**
 * 格式化价格
 */
function formatPrice(price: null | number | undefined): string {
  if (price === null || price === undefined) return '-';
  return `$${price}`;
}

function onToggleModelActive(row: AIModelInfo) {
  Modal.confirm({
    title: row.is_active
      ? $t('admin.ai.model.messages.confirmDisable')
      : $t('admin.ai.model.messages.confirmEnable'),
    onOk: async () => {
      try {
        await toggleAIModelStatusApi(row.id);
        message.success($t('admin.ai.model.messages.toggleSuccess'));
        onRefresh();
      } catch {
        // handled by interceptor / 错误由请求拦截器处理
      }
    },
  });
}

/** 正在测试中的模型 ID 集合 */
const testingModelIds = ref<Set<number>>(new Set());

/**
 * 测试模型连通性
 */
async function onTestModel(row: AIModelInfo) {
  if (testingModelIds.value.has(row.id)) return;

  testingModelIds.value.add(row.id);
  const hideLoading = message.loading($t('admin.ai.model.testing'), 0);

  try {
    const result = await testAIGatewayApi({
      provider_id: row.provider_id,
      model_code: row.code,
    });

    if (result.connected) {
      message.success(
        $t('admin.ai.model.testSuccess', { latency: result.latency_ms }),
      );
    } else {
      message.error(
        $t('admin.ai.model.testFailed', {
          error: result.error || $t('common.requestFailed'),
        }),
      );
    }
  } catch {
    message.error(
      $t('admin.ai.model.testFailed', { error: $t('common.requestFailed') }),
    );
  } finally {
    hideLoading();
    testingModelIds.value.delete(row.id);
  }
}

const { Grid, FormDrawer, onRefresh, onCreate, gridApi, formAiOperations } = useCrudPage<AIModelInfo>({
  api: {
    list: getAIModelListApi,
    resource: '/admin/ai/models',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.ai.model',
  nameField: 'name',
  defaultSort: '-created_at',
  recycleBin: true,
  createPermission: 'ai_model:create',
  customActions: {
    test: onTestModel,
  },
  ai: { pageKey: 'admin.ai.models', formSchema: useFormSchema },
});

const cleanupPageContext = registerPageContext('admin/ai/models', () => ({
  page_key: 'admin.ai.models',
  page_title: $t('admin.ai.model.name'),
  page_data: {
    resource: '/admin/ai/models',
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.models', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the AI model list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Model list refreshed' };
    },
  },
  {
    name: 'create_record',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open the create model form',
    readonly: false,
    handler: async () => {
      onCreate();
      return { success: true, message: 'Create model form opened' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search models by keyword',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Search keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  ...formAiOperations,
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.model.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列：图标 + 名称 + 能力徽章 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg"
              :class="row.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="
                  row.type === 'embedding'
                    ? 'lucide:database'
                    : row.type === 'image'
                      ? 'lucide:image'
                      : 'lucide:brain'
                "
                class="size-4"
                :class="
                  row.is_active ? 'text-primary' : 'text-muted-foreground'
                "
              />
            </div>
            <div class="flex flex-col gap-0.5">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <div class="flex flex-wrap gap-1">
                <Tag
                  v-if="row.supports_function_calling"
                  class="!mr-0 rounded border-0 bg-blue-500/10 px-1 py-0 text-[10px] text-blue-600"
                >
                  {{ $t('admin.ai.model.functionCalling') }}
                </Tag>
                <Tag
                  v-if="row.supports_vision"
                  class="!mr-0 rounded border-0 bg-purple-500/10 px-1 py-0 text-[10px] text-purple-600"
                >
                  {{ $t('admin.ai.model.vision') }}
                </Tag>
                <Tag
                  v-if="row.supports_streaming"
                  class="!mr-0 rounded border-0 bg-green-500/10 px-1 py-0 text-[10px] text-green-600"
                >
                  {{ $t('admin.ai.model.streaming') }}
                </Tag>
              </div>
            </div>
          </div>
        </template>

        <!-- 代码列 -->
        <template #code_cell="{ row }">
          <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
            {{ row.code }}
          </code>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag
            :color="
              row.type === 'chat'
                ? 'blue'
                : row.type === 'embedding'
                  ? 'green'
                  : 'orange'
            "
          >
            {{ getModelTypeText(row.type) }}
          </Tag>
        </template>

        <!-- Provider column: icon + name / 供应商列：图标 + 名称 -->
        <template #providerName_cell="{ row }">
          <div
            v-if="row.provider_name"
            class="flex items-center justify-center gap-1.5"
          >
            <img
              v-if="row.provider_icon && Number(row.provider_icon) > 0"
              :src="getProcessedImageUrl(Number(row.provider_icon), { preset: 'small' })"
              class="size-4 shrink-0 rounded object-contain"
              alt=""
            />
            <IconifyIcon
              v-else
              icon="lucide:cpu"
              class="size-3.5 text-muted-foreground"
            />
            <span class="text-foreground">{{ row.provider_name }}</span>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 上下文窗口列 -->
        <template #contextWindow_cell="{ row }">
          <Tooltip
            v-if="row.context_window"
            :title="`${row.context_window.toLocaleString()} tokens`"
          >
            <span class="font-mono text-sm text-muted-foreground">
              {{ formatTokens(row.context_window) }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 合并价格列 -->
        <template #price_cell="{ row }">
          <div class="flex flex-col items-center gap-0.5 text-xs">
            <span class="text-muted-foreground">
              <span class="text-green-600">{{
                formatPrice(row.input_price_per_1k)
              }}</span>
              /
              <span class="text-orange-600">{{
                formatPrice(row.output_price_per_1k)
              }}</span>
            </span>
          </div>
        </template>

        <!-- 模型级别列：Tier Tag -->
        <template #tier_cell="{ row }">
          <span
            v-if="row.tier"
            class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
            :class="{
              'bg-success/10 text-success': row.tier === 'fast',
              'bg-primary/10 text-primary': row.tier === 'standard',
              'bg-warning/10 text-warning': row.tier === 'premium',
            }"
          >
            {{ getModelTierText(row.tier) }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 启用状态列：Switch -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_model:toggle_status']"
            :checked="row.is_active"
            size="small"
            @change="() => onToggleModelActive(row)"
          />
        </template>
      </Grid>
    </Card>
  </Page>
</template>
