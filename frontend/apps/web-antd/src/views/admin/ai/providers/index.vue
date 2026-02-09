<script lang="ts" setup>
/**
 * AI 供应商管理列表页面
 */
import type { AIProviderInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIProviderList' });

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, message, Modal, Switch, Tag } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';
import {
  getAIProviderListApi,
  reorderAIProvidersApi,
  toggleAIProviderStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import { getFormDefaults, getProviderTypeText, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

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

const { Grid, FormDrawer, gridApi, onCreate, onRefresh } =
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
  });

// 拖拽排序
useAutoTableDragSort(() => gridApi.grid, {
  onBatchUpdate: (ids) => reorderAIProvidersApi(ids as number[]),
  keyField: 'id',
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg"
              :class="row.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="row.icon || 'lucide:cpu'"
                class="size-4"
                :class="row.is_active ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="flex flex-col">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <span
                v-if="row.description"
                class="line-clamp-1 text-xs text-muted-foreground"
              >
                {{ row.description }}
              </span>
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
          <Tag color="blue">
            {{ getProviderTypeText(row.type) }}
          </Tag>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_provider:toggle_status']"
            :checked="row.is_active"
            size="small"
            @change="() => onToggleActive(row)"
          />
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['ai_provider:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.ai.provider.create')
              }}</span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
