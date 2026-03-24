<script lang="ts" setup>
/**
 * Operation log list page (tenant)
 * 操作日志列表页面（企业端）
 */
import type { tenantApi } from '#/api';

import { onMounted, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';

import { Avatar, Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { tenantApi as tenant } from '#/api';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

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

// Avatar map (for table row avatar display) / 头像映射（用于表格行显示头像）
const avatarMap = ref<Record<number, null | string | undefined>>({});

async function loadAvatarMap() {
  try {
    const list = await tenant.getOperatorsApi();
    const map: Record<number, null | string | undefined> = {};
    for (const op of list) {
      if (op.user_id) map[op.user_id] = op.avatar;
    }
    avatarMap.value = map;
  } catch {
    // ignore / 忽略非关键错误
  }
}

onMounted(() => {
  loadAvatarMap();
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
          <div class="flex items-center gap-2">
            <Avatar
              v-if="row.userId && avatarMap[row.userId]"
              :src="toAvatarDisplayUrl(avatarMap[row.userId])"
              :size="28"
            />
            <Avatar
              v-else
              :size="28"
              class="flex-shrink-0 bg-primary/10 text-xs text-primary"
            >
              {{ (row.nickname || row.username || '?').charAt(0) }}
            </Avatar>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1">
                <span class="truncate text-sm font-medium text-foreground">
                  {{ row.nickname || row.username }}
                </span>
                <Tag
                  :color="getUserTypeColor(row.userType)"
                  class="!m-0 !text-[10px] !leading-tight"
                >
                  {{ getUserTypeLabel(row.userType) }}
                </Tag>
              </div>
              <div
                v-if="row.nickname"
                class="truncate text-xs text-muted-foreground"
              >
                {{ row.username }}
              </div>
            </div>
          </div>
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
      </Grid>
    </Card>
  </Page>
</template>
