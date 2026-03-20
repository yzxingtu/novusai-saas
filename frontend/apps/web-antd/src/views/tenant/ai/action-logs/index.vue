<script lang="ts" setup>
/**
 * 企业端 AI 操作审计日志列表页面 / Tenant AI action audit log list page
 *
 * 包含统计卡片 + 操作列表
 */
import type { ActionLogItem, ActionLogStats } from '#/api/tenant/action-logs';

import { onMounted, onUnmounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Col, Row, Statistic, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getActionLogListApi,
  getActionLogStatsApi,
} from '#/api/tenant/action-logs';
import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  getStatusColor,
  getStatusText,
  getTypeColor,
  getTypeText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'TenantAIActionLogList' });

// ============ 统计 ============

const stats = ref<ActionLogStats>({
  total: 0,
  success_count: 0,
  failed_count: 0,
  rejected_count: 0,
  pending_count: 0,
  level_read: 0,
  level_safe_write: 0,
  level_dangerous: 0,
  avg_duration_ms: null,
});

async function fetchStats() {
  try {
    stats.value = await getActionLogStatsApi();
  } catch {
    // ignore
  }
}

const successRate = ref('0%');
function computeSuccessRate() {
  const total = stats.value.total;
  if (total === 0) {
    successRate.value = '-';
    return;
  }
  const rate = (stats.value.success_count / total) * 100;
  successRate.value = `${rate.toFixed(1)}%`;
}

onMounted(() => {
  fetchStats().then(computeSuccessRate);
});

// ============ 列表 ============

const { Grid, onRefresh, gridApi } = useCrudPage<ActionLogItem>({
  api: {
    list: getActionLogListApi,
    resource: '/tenant/ai/action-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'tenant.ai.actionLog',
  defaultSort: '-created_at',
});

const cleanupPageContext = registerPageContext('tenant/ai/action-logs', () => ({
  page_key: 'tenant.ai.action-logs',
  page_title: $t('tenant.ai.actionLog.name'),
  page_data: {
    resource: '/tenant/ai/action-logs',
  },
}));

const cleanupPageOps = registerPageOperations('tenant.ai.action-logs', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the action log list',
    readonly: true,
    handler: async () => {
      onRefresh();
      await fetchStats();
      return { success: true, message: 'Action log list refreshed' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search action logs by action type',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Action type keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[action_type][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.actionLog.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 统计卡片 -->
    <Row :gutter="16">
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t('tenant.ai.actionLog.stats.totalActions')"
            :value="stats.total"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:activity" class="mr-1 text-primary" />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t('tenant.ai.actionLog.stats.successRate')"
            :value="successRate"
          >
            <template #prefix>
              <IconifyIcon
                icon="lucide:check-circle"
                class="mr-1 text-success"
              />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t('tenant.ai.actionLog.stats.rejectedCount')"
            :value="stats.rejected_count"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:shield-x" class="mr-1 text-warning" />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t('tenant.ai.actionLog.status_options.failed')"
            :value="stats.failed_count"
            :value-style="{
              color: stats.failed_count > 0 ? '#ff4d4f' : undefined,
            }"
          >
            <template #prefix>
              <IconifyIcon
                icon="lucide:alert-triangle"
                class="mr-1 text-destructive"
              />
            </template>
          </Statistic>
        </Card>
      </Col>
    </Row>

    <!-- 列表 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>

        <!-- 操作名称列 -->
        <template #actionName_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon icon="lucide:zap" class="size-3.5 text-primary" />
            <code class="rounded bg-accent px-1 py-0.5 text-xs font-medium">
              {{ row.action_name }}
            </code>
          </div>
        </template>

        <!-- 类型列 -->
        <template #actionType_cell="{ row }">
          <Tag :color="getTypeColor(row.action_type)">
            {{ getTypeText(row.action_type) }}
          </Tag>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 耗时列 -->
        <template #executionTime_cell="{ row }">
          <span v-if="row.duration_ms" class="text-muted-foreground">
            {{ row.duration_ms }}ms
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
