<script lang="ts" setup>
/**
 * AI 供应商管理列表页面
 */
import type { AIProviderInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIProviderList' });

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, message, Modal, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';

import QuickStartGuide from '#/components/business/quick-start-guide/QuickStartGuide.vue';
import {
  getAIProviderListApi,
  reorderAIProvidersApi,
  toggleAIProviderStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import { getFormDefaults, getProviderTypeText, loadAdapterTypes, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

loadAdapterTypes();

// ============================================================
// Status toggle
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
        // Error handled by request interceptor
      }
    },
  });
}

// ============================================================
// CRUD Grid
// ============================================================

const { Grid, FormDrawer, gridApi, onRefresh } =
  useCrudPage<AIProviderInfo>({
    api: {
      list: getAIProviderListApi,
      resource: '/admin/ai/providers',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.ai.provider',
    nameField: 'name',
    defaultSort: 'sort_order',
    recycleBin: true,
    createPermission: 'ai_provider:create',
  });

function onFormSuccess() {
  onRefresh();
}

// 拖拽排序
useAutoTableDragSort(() => gridApi.grid, {
  onBatchUpdate: (ids) => reorderAIProvidersApi(ids as number[]),
  keyField: 'id',
});
</script>

<template>
  <Page auto-content-height :description="$t('admin.ai.provider.pageDesc')" content-class="flex flex-col gap-4">
    <QuickStartGuide
      storage-key="admin-ai-guide-dismissed"
      i18n-prefix="admin.ai"
      :steps="[
        { key: 'step1', icon: 'lucide:plug', color: 'text-primary', bg: 'bg-primary/10', link: '/admin/ai/providers' },
        { key: 'step2', icon: 'lucide:key', color: 'text-amber-600', bg: 'bg-amber-500/10', link: '/admin/ai/api-keys' },
        { key: 'step3', icon: 'lucide:brain', color: 'text-purple-600', bg: 'bg-purple-500/10', link: '/admin/ai/models' },
        { key: 'step4', icon: 'lucide:activity', color: 'text-success', bg: 'bg-success/10', link: '/admin/ai/monitor/health' },
      ]"
    />
    <FormDrawer @success="onFormSuccess" />

    <!-- Data table -->
    <Grid>
        <!-- 名称列：图标 + 名称 + 代码 + base_url -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2.5">
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="row.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="row.icon || 'lucide:cpu'"
                class="size-4"
                :class="row.is_active ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-foreground">{{ row.name }}</span>
                <code class="shrink-0 rounded bg-accent px-1 py-0.5 text-[10px] text-muted-foreground">
                  {{ row.code }}
                </code>
              </div>
              <Tooltip v-if="row.base_url" :title="row.base_url">
                <div class="mt-0.5 flex items-center gap-1 truncate text-xs text-muted-foreground">
                  <IconifyIcon icon="lucide:link" class="size-3 shrink-0" />
                  <span class="truncate">{{ row.base_url }}</span>
                </div>
              </Tooltip>
              <div
                v-else-if="row.description"
                class="mt-0.5 truncate text-xs text-muted-foreground"
              >
                {{ row.description }}
              </div>
            </div>
          </div>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag color="blue">
            {{ getProviderTypeText(row.type) }}
          </Tag>
        </template>

        <!-- 模型数列 -->
        <template #modelCount_cell="{ row }">
          <Badge
            :count="row.model_count || 0"
            :number-style="{ backgroundColor: row.model_count > 0 ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))' }"
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
  </Page>
</template>
