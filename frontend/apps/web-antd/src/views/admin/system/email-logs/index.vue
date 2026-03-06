<script lang="ts" setup>
/**
 * 邮件日志管理列表页面
 */
import type { EmailLogInfo } from '#/api/admin/email-log';

import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getEmailLogListApi } from '#/api/admin/email-log';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getStatusColor,
  getTriggerColor,
  useColumns,
  useGridFormSchema,
} from './data';
import EmailPreviewDrawer from './modules/EmailPreviewDrawer.vue';
import SendEmailDrawer from './modules/SendEmailDrawer.vue';

defineOptions({ name: 'SystemEmailLogList' });

const [SendEmailDrawerComp, sendDrawerApi] = useVbenDrawer({
  connectedComponent: SendEmailDrawer,
});

const [PreviewDrawerComp, previewDrawerApi] = useVbenDrawer({
  connectedComponent: EmailPreviewDrawer,
});

function onOpenSendDrawer() {
  sendDrawerApi.open();
}

function onPreview(row: EmailLogInfo) {
  previewDrawerApi.setData({ id: row.id });
  previewDrawerApi.open();
}

const { Grid, onRefresh } = useCrudPage<EmailLogInfo>({
  api: {
    list: getEmailLogListApi,
    resource: '/admin/email-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.emailLog',
  nameField: 'subject',
  defaultSort: '-created_at',
  customActions: {
    detail: onPreview,
  },
});

const cleanupPageContext = registerPageContext('admin/system/email-logs', () => ({
  page_key: 'admin.system.email-logs',
  page_title: $t('admin.system.emailLog.name'),
  page_data: {
    resource: '/admin/email-logs',
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.email-logs', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the email log list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Email log list refreshed' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <SendEmailDrawerComp @success="onRefresh" />
    <PreviewDrawerComp />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 收件人列 -->
        <template #toAddress_cell="{ row }">
          <Tooltip :title="row.toAddress">
            <span class="truncate text-sm">{{ row.toAddress }}</span>
          </Tooltip>
        </template>

        <!-- 主题列 -->
        <template #subject_cell="{ row }">
          <span class="line-clamp-1 text-sm font-medium text-foreground">
            {{ row.subject }}
          </span>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ $t(`admin.system.emailLog.status.${row.status}`) }}
          </Tag>
        </template>

        <!-- 触发来源列 -->
        <template #trigger_cell="{ row }">
          <Tag :color="getTriggerColor(row.triggeredBy)">
            {{ $t(`admin.system.emailLog.trigger.${row.triggeredBy}`) }}
          </Tag>
        </template>

        <!-- 错误信息列 -->
        <template #error_cell="{ row }">
          <Tooltip v-if="row.errorMessage" :title="row.errorMessage">
            <span class="line-clamp-1 text-xs text-destructive">
              {{ row.errorMessage }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-muted-foreground">
              {{ formatRelativeTime(row.createdAt) }}
            </span>
          </Tooltip>
        </template>

        <!-- 左侧工具栏：发送邮件 -->
        <template #toolbar-actions>
          <Button
            v-access:code="['email_log:send']"
            type="primary"
            @click="onOpenSendDrawer"
          >
            <template #icon>
              <IconifyIcon icon="lucide:send" class="size-4" />
            </template>
            {{ $t('admin.system.emailLog.send.title') }}
          </Button>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
