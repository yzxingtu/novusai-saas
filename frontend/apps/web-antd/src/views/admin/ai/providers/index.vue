<script lang="ts" setup>
/**
 * AI 供应商管理列表页面
 * AI provider management list page
 */
import type { AIProviderInfo } from '#/api/admin/ai';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, message, Modal, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';
import {
  getAIProviderListApi,
  reorderAIProvidersApi,
  toggleAIProviderStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';
import { toAttachmentImageUrl } from '#/utils/image';

import AIGatewayQuickStartHero from '../_shared/AIGatewayQuickStartHero.vue';
import {
  getFormDefaults,
  getProviderWebSearchRuntimeSummary,
  getProviderWebSearchStrategyText,
  getProviderTypeText,
  getProviderWireApiText,
  loadAdapterTypes,
  resolveProviderWireApi,
  resolveProviderWebSearchConfig,
  shouldWarnProviderWebSearchAutoFallback,
  useColumns,
  useGridFormSchema,
} from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'AIProviderList' });

loadAdapterTypes();

function getRowWireApi(row: AIProviderInfo) {
  const config =
    row.config && typeof row.config === 'object'
      ? (row.config as Record<string, unknown>)
      : null;
  return resolveProviderWireApi(
    row.type,
    typeof config?.wire_api === 'string' ? config.wire_api : null,
  );
}

function getRowWebSearchConfig(row: AIProviderInfo) {
  const config =
    row.config && typeof row.config === 'object'
      ? (row.config as Record<string, unknown>)
      : null;
  return resolveProviderWebSearchConfig(config);
}

// ============================================================
// Status toggle / 状态开关
// ============================================================

function onToggleActive(row: AIProviderInfo) {
  const isDisabling = row.is_active;
  Modal.confirm({
    title: isDisabling
      ? $t('admin.ai.provider.messages.confirmDisable')
      : $t('admin.ai.provider.messages.confirmEnable'),
    onOk: async () => {
      try {
        await toggleAIProviderStatusApi(row.id);
        message.success($t('admin.ai.provider.messages.toggleSuccess'));
        onRefresh();
      } catch {
        // Error handled by request interceptor / 错误由请求拦截器处理
      }
    },
  });
}

// ============================================================
// CRUD Grid / CRUD 表格
// ============================================================

const { Grid, FormDrawer, gridApi, onRefresh } = useCrudPage<AIProviderInfo>({
  api: {
    list: getAIProviderListApi,
    resource: '/admin/ai/providers',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[name][ilike]',
      fields: ['filter[name][ilike]'],
    },
  },
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.ai.provider',
  nameField: 'name',
  defaultSort: 'sort_order',
  rowHeight: 84,
  recycleBin: true,
  createPermission: 'ai_provider:create',
});

function onFormSuccess() {
  onRefresh();
}

// Drag sort / 拖拽排序
useAutoTableDragSort(() => gridApi.grid, {
  onBatchUpdate: (ids) => reorderAIProvidersApi(ids as number[]),
  keyField: 'id',
});
</script>

<template>
  <Page
    auto-content-height
    content-class="ai-providers-page flex flex-col gap-4 !p-4"
  >
    <AIGatewayQuickStartHero :current-title="$t('admin.ai.provider.title')" />

    <FormDrawer @success="onFormSuccess" />

    <section
      class="overflow-hidden rounded-[20px] border border-border/70 bg-card shadow-sm"
    >
      <!-- Data table -->
      <Grid>
        <!-- Name column: Logo + name + code + base_url / 名称列：Logo + 名称 + 代码 + base_url -->
        <template #name_cell="{ row }">
          <div class="flex items-start gap-3 py-0.5">
            <div
              class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 shadow-sm"
              :class="
                row.is_active
                  ? 'from-primary/12 bg-gradient-to-br to-primary/5'
                  : 'bg-muted/70'
              "
            >
              <img
                v-if="toAttachmentImageUrl(row.icon, { preset: 'small' })"
                :src="toAttachmentImageUrl(row.icon, { preset: 'small' })"
                class="size-full object-contain"
                alt=""
              />
              <IconifyIcon
                v-else
                icon="lucide:cpu"
                class="size-4"
                :class="
                  row.is_active ? 'text-primary' : 'text-muted-foreground'
                "
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <span class="font-medium text-foreground">{{ row.name }}</span>
                <code
                  class="shrink-0 rounded bg-accent px-1 py-0.5 text-[10px] text-muted-foreground"
                >
                  {{ row.code }}
                </code>
                <span
                  v-if="row.description"
                  class="min-w-0 truncate text-xs text-muted-foreground"
                >
                  {{ row.description }}
                </span>
              </div>
              <Tooltip v-if="row.base_url" :title="row.base_url">
                <div
                  class="mt-0.5 flex items-center gap-1 truncate text-xs text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:link" class="size-3 shrink-0" />
                  <span class="truncate">{{ row.base_url }}</span>
                </div>
              </Tooltip>
            </div>
          </div>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag color="blue">
            {{ getProviderTypeText(row.type) }}
          </Tag>
        </template>

        <!-- API 协议列 -->
        <template #wireApi_cell="{ row }">
          <Tag
            v-if="row.type === 'openai_compatible'"
            color="processing"
            class="m-0"
          >
            {{ getProviderWireApiText(getRowWireApi(row)) }}
          </Tag>
          <span v-else class="text-xs text-muted-foreground">-</span>
        </template>

        <template #webSearch_cell="{ row }">
          <div class="flex flex-col gap-1 py-1">
            <div class="flex flex-wrap items-center gap-1">
              <Tag :color="getRowWebSearchConfig(row).enabled ? 'success' : 'default'">
                {{
                  getRowWebSearchConfig(row).enabled
                    ? $t('admin.common.enabled')
                    : $t('admin.common.disabled')
                }}
              </Tag>
              <Tag color="processing">
                {{
                  getProviderWebSearchStrategyText(
                    getRowWebSearchConfig(row).strategy,
                  )
                }}
              </Tag>
            </div>
            <div class="text-xs text-muted-foreground">
              {{
                getProviderWebSearchRuntimeSummary(
                  row.web_search_runtime || null,
                )
              }}
            </div>
            <div
              v-if="shouldWarnProviderWebSearchAutoFallback(row.web_search_runtime)"
              class="text-xs text-amber-600 dark:text-amber-400"
            >
              {{ $t('admin.ai.provider.webSearch.runtime.autoFallbackHint') }}
            </div>
          </div>
        </template>

        <!-- 模型数列 -->
        <template #modelCount_cell="{ row }">
          <Badge
            :count="row.model_count || 0"
            :number-style="{
              backgroundColor:
                row.model_count > 0
                  ? 'hsl(var(--primary))'
                  : 'hsl(var(--muted-foreground))',
            }"
            :overflow-count="999"
            :show-zero="true"
          />
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_provider:toggle_status']"
            :checked="row.is_active"
            :checked-children="$t('admin.common.enabled')"
            :un-checked-children="$t('admin.common.disabled')"
            size="small"
            @change="() => onToggleActive(row)"
          />
        </template>
      </Grid>
    </section>
  </Page>
</template>

<style scoped>
.ai-providers-page :deep(.vxe-body--row .vxe-cell) {
  padding-top: 10px;
  padding-bottom: 10px;
}
</style>
