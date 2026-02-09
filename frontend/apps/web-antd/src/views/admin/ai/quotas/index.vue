<script lang="ts" setup>
/**
 * AI 配额管理列表页面
 */
import type { AIQuotaInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIQuotaList' });

import { Page } from '@vben/common-ui';
import { Plus } from '@vben/icons';

import { Card, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIQuotaListApi } from '#/api/admin/ai';
import { $t } from '#/locales';

import {
  getFormDefaults,
  getPeriodText,
  getQuotaTypeText,
  useColumns,
  useGridFormSchema,
} from './data';
import Form from './modules/form.vue';

/**
 * 格式化 Token 数量
 */
function formatTokens(num: null | number | undefined): string {
  if (!num) return '-';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return `${num}`;
}

const { Grid, FormDrawer, onCreate, onRefresh } =
  useCrudPage<AIQuotaInfo>({
    api: {
      list: getAIQuotaListApi,
      resource: '/admin/ai/quotas',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.ai.quota',
    nameField: 'id',
    defaultSort: '-created_at',
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 租户列 -->
        <template #tenantName_cell="{ row }">
          <span v-if="row.tenant_name" class="text-foreground">
            {{ row.tenant_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 模型列 -->
        <template #modelName_cell="{ row }">
          <span v-if="row.model_name" class="text-foreground">
            {{ row.model_name }}
          </span>
          <Tag v-else color="blue">
            {{ $t('admin.ai.quota.globalQuota') }}
          </Tag>
        </template>

        <!-- 周期列 -->
        <template #period_cell="{ row }">
          <Tag :color="row.period === 'daily' ? 'orange' : 'blue'">
            {{ getPeriodText(row.period) }}
          </Tag>
        </template>

        <!-- 配额限制列：人性化格式 -->
        <template #limit_cell="{ row }">
          <span class="font-mono font-medium text-foreground">
            {{ formatTokens(row.limit) }}
          </span>
          <span class="ml-1 text-xs text-muted-foreground">tokens</span>
        </template>

        <!-- 配额类型列 -->
        <template #quotaType_cell="{ row }">
          <Tag :color="row.quota_type === 'hard' ? 'red' : 'green'">
            {{ getQuotaTypeText(row.quota_type) }}
          </Tag>
        </template>

        <!-- 预警阈值列 -->
        <template #threshold_cell="{ row }">
          <span v-if="row.warning_threshold != null" class="text-muted-foreground">
            {{ row.warning_threshold }}%
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Tag :color="row.is_active ? 'success' : 'default'">
            {{
              row.is_active
                ? $t('admin.common.enabled')
                : $t('admin.common.disabled')
            }}
          </Tag>
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['ai_quota:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.ai.quota.create')
              }}</span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
