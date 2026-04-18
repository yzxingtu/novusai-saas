<script lang="ts" setup>
/**
 * Operation log list page (tenant)
 * 操作日志列表页面（企业端）
 */
import type { tenantApi } from '#/api';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { tenantApi as tenant } from '#/api';
import { formatDate, formatRelativeTime } from '#/utils/common';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  getMethodColor,
  getStatusColor,
  getUserTypeColor,
  getUserTypeLabel,
  useColumns,
  useGridFormSchema,
} from './data';
import DetailDrawer from './modules/LogDetail.vue';

defineOptions({ name: 'TenantOperationLogList' });

type OperationLogInfo = tenantApi.OperationLogInfo;

// Detail drawer / 详情抽屉
const [DetailDrawerComp, detailDrawerApi] = useVbenDrawer({
  connectedComponent: DetailDrawer,
});

/**
 * View detail / 查看详情
 */
function onViewDetail(row: OperationLogInfo) {
  detailDrawerApi.setData({ id: row.id }).open();
}

function buildOperatorIdentityModel(row: OperationLogInfo) {
  return {
    avatar: row.avatar,
    badges: row.userType
      ? [
          {
            color: getUserTypeColor(row.userType),
            key: `type-${row.id}`,
            label: getUserTypeLabel(row.userType),
          },
        ]
      : [],
    displayName: row.displayName,
    id: row.userId ?? row.id,
    isActive: row.isActive,
    isLeader: row.isLeader,
    isOwner: row.isOwner,
    nickname: row.nickname || row.username,
    orgNodeName: row.orgNodeName,
    roleName: row.roleName,
    userType: row.userType,
  };
}

function buildOperatorMeta(row: OperationLogInfo): IdentityDetailMeta {
  return {
    orgNodeName: row.orgNodeName,
    roleName: row.roleName,
    scope: 'tenant',
    subjectType: row.userType,
    userType: row.userType,
    username: row.username,
  };
}

// User type filter linkage: after selecting type, operator dropdown only shows users of that type / 用户类型筛选联动：选择类型后，操作人下拉只显示对应类型的用户
function onUserTypeChange(userType: string | undefined) {
  // Clear selected operator (may not belong to the new type) / 清空已选操作人（因为可能不属于新类型）
  gridApi.formApi?.setValues({ 'filter[username]': undefined });
  // Update ApiSelect params, inject user_type / 更新 ApiSelect 的请求参数，注入 user_type
  gridApi.formApi?.updateSchema([
    {
      componentProps: {
        params: { user_type: userType || undefined },
      },
      fieldName: 'filter[username]',
    },
  ]);
}

// CRUD page (read-only list) / CRUD 页面（只读列表）
const { Grid, gridApi } = useCrudPage<OperationLogInfo>({
  api: {
    list: tenant.getOperationLogListApi,
    resource: '/tenant/operation-logs',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema({ onUserTypeChange }),
  i18nPrefix: 'tenant.system.operationLog',
  nameField: 'id',
  defaultSort: '-created_at',
  customActions: {
    detail: onViewDetail,
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <DetailDrawerComp />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 用户名列（含头像 + 用户类型标签） -->
        <template #username_cell="{ row }">
          <IdentityTrigger
            :avatar-size="32"
            :model="buildOperatorIdentityModel(row)"
            :meta="buildOperatorMeta(row)"
            :show-status-badge="false"
          />
        </template>

        <!-- 模块列 -->
        <template #module_cell="{ row }">
          <Tag color="blue">{{ row.moduleLabel || row.module || '-' }}</Tag>
        </template>

        <!-- 操作类型列 -->
        <template #action_cell="{ row }">
          <Tag color="purple">{{ row.actionLabel || row.action || '-' }}</Tag>
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
      </Grid>
    </Card>
  </Page>
</template>
