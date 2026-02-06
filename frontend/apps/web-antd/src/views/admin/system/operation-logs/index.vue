<script lang="ts" setup>
/**
 * 操作日志列表页面
 */
import type { adminApi } from '#/api';

import { ref } from 'vue';

defineOptions({ name: 'SystemOperationLogList' });

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  message,
  Popconfirm,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getMethodColor,
  getStatusColor,
  useColumns,
  useGridFormSchema,
} from './data';
import DetailDrawer from './modules/LogDetail.vue';

type OperationLogInfo = adminApi.OperationLogInfo;

// 详情抽屉
const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: DetailDrawer,
});

// 选中的行
const selectedRows = ref<OperationLogInfo[]>([]);

/**
 * 查看详情
 */
function onViewDetail(row: OperationLogInfo) {
  detailDrawerApi.setData({ id: row.id, mode: 'view' }).open();
}

/**
 * 批量删除
 */
async function onBatchDelete() {
  if (selectedRows.value.length === 0) return;

  const ids = selectedRows.value.map((row) => row.id);
  try {
    await admin.deleteOperationLogsApi(ids);
    message.success($t('admin.system.operationLog.messages.deleteSuccess'));
    selectedRows.value = [];
    onRefresh();
  } catch {
    // Error handled by request interceptor
  }
}

// CRUD 页面（只读列表，不需要表单组件）
const { Grid, onRefresh } = useCrudPage<OperationLogInfo>({
  api: {
    list: admin.getOperationLogListApi,
    resource: '/admin/operation-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.operationLog',
  nameField: 'id',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
});

/**
 * 监听选中变化
 */
function onSelectionChange(rows: OperationLogInfo[]) {
  selectedRows.value = rows;
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <DetailDrawerComp />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid @selection-change="onSelectionChange">
        <!-- 用户名列 -->
        <template #username_cell="{ row }">
          <span class="font-medium">{{ row.nickname || row.username }}</span>
        </template>

        <!-- 模块列 -->
        <template #module_cell="{ row }">
          <Tag color="blue">{{ row.moduleLabel || row.module }}</Tag>
        </template>

        <!-- 操作类型列 -->
        <template #action_cell="{ row }">
          <Tag color="purple">{{ row.actionLabel || row.action }}</Tag>
        </template>

        <!-- 请求方法列 -->
        <template #method_cell="{ row }">
          <Tag :color="getMethodColor(row.method)">
            {{ row.method }}
          </Tag>
        </template>

        <!-- 请求路径列 -->
        <template #path_cell="{ row }">
          <Tooltip :title="row.path">
            <code
              class="max-w-[300px] truncate rounded bg-accent px-1 py-0.5 text-xs"
            >
              {{ row.path }}
            </code>
          </Tooltip>
        </template>

        <!-- 状态码列 -->
        <template #statusCode_cell="{ row }">
          <Tag :color="getStatusColor(row.statusCode)">
            {{ row.statusCode }}
          </Tag>
        </template>

        <!-- 耗时列 -->
        <template #durationMs_cell="{ row }">
          <span
            :class="
              row.durationMs > 1000
                ? 'font-medium text-warning'
                : 'text-muted-foreground'
            "
          >
            {{ row.durationMs }} ms
          </span>
        </template>

        <!-- IP 地址列 -->
        <template #ip_cell="{ row }">
          <code class="rounded bg-accent px-1 py-0.5 text-xs">
            {{ row.ip }}
          </code>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-muted-foreground">{{
              formatRelativeTime(row.createdAt)
            }}</span>
          </Tooltip>
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Popconfirm
            v-if="selectedRows.length > 0"
            :title="
              $t('admin.system.operationLog.messages.batchDeleteConfirm', {
                count: selectedRows.length,
              })
            "
            :ok-text="$t('shared.common.confirm')"
            :cancel-text="$t('shared.common.cancel')"
            :ok-button-props="{ danger: true }"
            @confirm="onBatchDelete"
          >
            <Button
              v-access:code="['operation_log:delete']"
              danger
              class="mr-2"
            >
              <template #icon>
                <IconifyIcon icon="lucide:trash-2" />
              </template>
              {{ $t('admin.system.operationLog.batchDelete') }} ({{
                selectedRows.length
              }})
            </Button>
          </Popconfirm>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
