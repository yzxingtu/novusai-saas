<script lang="ts" setup>
/**
 * 邮件日志管理列表页面
 */
import type { EmailLogInfo } from '#/api/admin/email-log';

defineOptions({ name: 'SystemEmailLogList' });

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

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
import SendEmailDrawer from './modules/SendEmailDrawer.vue';

const [SendEmailDrawerComp, sendDrawerApi] = useVbenDrawer({
  connectedComponent: SendEmailDrawer,
});

function onOpenSendDrawer() {
  sendDrawerApi.open();
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
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <SendEmailDrawerComp @success="onRefresh" />

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

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['email_log:send']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onOpenSendDrawer"
          >
            <div class="flex items-center gap-2 text-primary">
              <IconifyIcon icon="lucide:send" class="size-4" />
              <span class="font-medium">
                {{ $t('admin.system.emailLog.send.title') }}
              </span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
