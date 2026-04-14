<script lang="ts" setup>
/**
 * 企业端 AI 操作审计日志列表页面 / Tenant AI action audit log list page
 *
 * 路由壳层仅保留布局、CRUD 装配与局部模块接线。
 */
import type { ActionLogItem } from '#/api/tenant/action-logs';

import { Page } from '@vben/common-ui';

import { useCrudPage } from '#/adapter/vxe-table';
import { getActionLogListApi } from '#/api/tenant/action-logs';

import { useColumns, useGridFormSchema } from './data';
import ActionLogHero from './modules/ActionLogHero.vue';
import ActionLogTableSection from './modules/ActionLogTableSection.vue';
import { useActionLogDetail } from './use-action-log-detail';

defineOptions({ name: 'TenantAIActionLogList' });

const detailController = useActionLogDetail();

const { Grid } = useCrudPage<ActionLogItem>({
  api: {
    list: getActionLogListApi,
    resource: '/tenant/ai/action-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  search: {
    defaultOpen: false,
    quickSearch: {
      defaultField: 'filter[action_name][ilike]',
      fields: [
        'filter[action_name][ilike]',
        'filter[trace_id][ilike]',
        'filter[tool_call_id][ilike]',
      ],
    },
  },
  i18nPrefix: 'tenant.ai.actionLog',
  defaultSort: '-created_at',
  rowHeight: 72,
  customActions: {
    detail: detailController.openDetail,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <ActionLogHero />
    <ActionLogTableSection
      :controller="detailController"
      :grid-component="Grid"
    />
  </Page>
</template>
