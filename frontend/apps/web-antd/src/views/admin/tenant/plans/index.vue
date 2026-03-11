<script lang="ts" setup>
/**
 * Plan list page
 * 套餐列表页面
 */
import type { adminApi } from '#/api';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Popover, Tag, Tooltip } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import {
  copyToClipboard,
  formatDate,
  formatRelativeTime,
} from '#/utils/common';

import {
  getBillingCycleText,
  getFormDefaults,
  useColumns,
  useGridFormSchema,
} from './data';
import PermissionsModal from './modules/PermissionsModal.vue';
import Form from './modules/PlanForm.vue';

defineOptions({ name: 'TenantPlanList' });

type TenantPlanInfo = adminApi.TenantPlanInfo;

/** Copy code to clipboard / 复制编码到剪贴板 */
async function onCopyCode(code: string) {
  const success = await copyToClipboard(code);
  if (success) {
    message.success($t('admin.tenant.domain.copySuccess'));
  } else {
    message.error($t('admin.tenant.domain.copyFailed'));
  }
}

// Permissions modal / 权限弹窗相关
const permissionsModalRef = ref<InstanceType<typeof PermissionsModal>>();

// Handle set permissions / 处理设置权限
function handleSetPermissions(row: TenantPlanInfo) {
  permissionsModalRef.value?.open(row);
}

// Declarative CRUD page (export button auto-added) / 声明式 CRUD 页面（导出按钮自动添加）
const { Grid, FormDrawer, ExportModal, openExportModal, gridApi, onRefresh } =
  useCrudPage<TenantPlanInfo>({
    api: {
      list: admin.getTenantPlanListApi,
      resource: '/admin/plans',
      toggles: { is_active: admin.toggleTenantPlanStatusApi },
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.tenant.plan',
    nameField: 'name',
    defaultSort: 'sort_order',
    recycleBin: true,
    createPermission: 'tenant_plan:create',
    customActions: {
      permissions: handleSetPermissions,
    },
  });

// Drag sort (auto-initialized) / 拖拽排序（自动初始化）
useAutoTableDragSort(() => gridApi.grid, {
  onBatchUpdate: (ids) => admin.reorderTenantPlansApi(ids as number[]),
  keyField: 'id',
});

const cleanupPageContext = registerPageContext('admin/tenant/plans', () => ({
  page_key: 'admin.tenant.plans',
  page_title: $t('admin.tenant.plan.name'),
  page_data: {
    resource: '/admin/plans',
  },
}));

const cleanupPageOps = registerPageOperations('admin.tenant.plans', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the tenant plan list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Plan list refreshed' };
    },
  },
  {
    name: 'search_plans',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search tenant plans by name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Plan name keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  {
    name: 'export_data',
    label: $t('shared.pageOperation.exportData'),
    description: 'Open the export dialog for tenant plans',
    readonly: true,
    handler: async () => {
      openExportModal();
      return { success: true, message: 'Export dialog opened' };
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
    <FormDrawer @success="onRefresh" />
    <ExportModal />

    <!-- 权限设置弹窗 -->
    <PermissionsModal ref="permissionsModalRef" />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 套餐名称列：添加图标和美化 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg bg-primary/10"
            >
              <IconifyIcon
                :icon="
                  row.isDefault
                    ? 'lucide:sparkles'
                    : row.billingCycle === 'yearly'
                      ? 'lucide:crown'
                      : 'lucide:package'
                "
                class="size-4 text-primary"
              />
            </div>
            <div class="flex flex-col">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <span v-if="row.isDefault" class="text-xs text-muted-foreground">
                {{ $t('admin.tenant.plan.defaultPlan') }}
              </span>
            </div>
          </div>
        </template>

        <!-- 套餐编码列：等宽字体 + 点击复制 -->
        <template #code_cell="{ row }">
          <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
            <span
              class="cursor-pointer font-mono text-muted-foreground transition-colors hover:text-primary"
              @click="onCopyCode(row.code)"
            >
              {{ row.code }}
              <IconifyIcon
                icon="lucide:copy"
                class="ml-1 inline-block size-3 opacity-50"
              />
            </span>
          </Tooltip>
        </template>

        <!-- 价格列 -->
        <template #price_cell="{ row }">
          <div class="flex justify-center">
            <div
              v-if="row.price && row.price > 0"
              class="rounded-lg bg-primary/10 px-3 py-1 text-center"
            >
              <span class="font-semibold text-primary">
                ¥{{ Number.parseFloat(row.price as string).toFixed(2) }}
              </span>
            </div>
            <Tag v-else class="rounded-lg bg-success/10 text-success">
              {{ $t('admin.tenant.plan.free') }}
            </Tag>
          </div>
        </template>

        <!-- 配额列：居中显示 -->
        <template #quota_cell="{ row }">
          <div class="flex justify-center">
            <Popover
              v-if="row.quota"
              :title="$t('admin.tenant.plan.quotaDetail')"
            >
              <template #content>
                <div class="flex flex-col gap-2 text-xs">
                  <div class="flex items-center justify-between gap-4">
                    <span class="text-muted-foreground"
                      >{{ $t('admin.tenant.plan.maxUsers') }}:</span
                    >
                    <span class="font-medium text-foreground">{{
                      row.quota.maxUsers ?? '∞'
                    }}</span>
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <span class="text-muted-foreground"
                      >{{ $t('admin.tenant.plan.maxAdmins') }}:</span
                    >
                    <span class="font-medium text-foreground">{{
                      row.quota.maxAdmins ?? '∞'
                    }}</span>
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <span class="text-muted-foreground"
                      >{{ $t('admin.tenant.plan.storageLimitGb') }}:</span
                    >
                    <span class="font-medium text-foreground"
                      >{{ row.quota.storageLimitGb ?? '∞' }} GB</span
                    >
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <span class="text-muted-foreground"
                      >{{ $t('admin.tenant.plan.maxCustomDomains') }}:</span
                    >
                    <span class="font-medium text-foreground">{{
                      row.quota.maxCustomDomains ?? '∞'
                    }}</span>
                  </div>
                  <div class="flex items-center justify-between gap-4">
                    <span class="text-muted-foreground"
                      >{{ $t('admin.tenant.plan.apiCallsPerMonth') }}:</span
                    >
                    <span class="font-medium text-foreground">{{
                      row.quota.apiCallsPerMonth ?? '∞'
                    }}</span>
                  </div>
                </div>
              </template>
              <div class="flex cursor-pointer flex-wrap justify-center gap-1">
                <Tag
                  v-if="row.quota.maxUsers"
                  class="!mr-0 rounded bg-primary/10 text-xs text-primary"
                >
                  {{ row.quota.maxUsers }}
                  {{ $t('admin.tenant.plan.userUnit') }}
                </Tag>
                <Tag
                  v-if="row.quota.storageLimitGb"
                  class="!mr-0 rounded bg-accent text-xs text-accent-foreground"
                >
                  {{ row.quota.storageLimitGb }} GB
                </Tag>
                <Tag
                  v-if="!row.quota.maxUsers && !row.quota.storageLimitGb"
                  class="!mr-0 rounded bg-success/10 text-xs text-success"
                >
                  {{ $t('admin.common.unlimited') }}
                </Tag>
              </div>
            </Popover>
            <span v-else class="text-muted-foreground">-</span>
          </div>
        </template>

        <!-- 特性列：居中显示 -->
        <template #features_cell="{ row }">
          <div class="flex justify-center">
            <div
              v-if="row.features"
              class="flex flex-wrap justify-center gap-1"
            >
              <Tag
                v-if="row.features.aiEnabled"
                class="!mr-0 rounded bg-purple-500/10 text-purple-500"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:sparkles" class="size-3" />
                </template>
                {{ $t('admin.tenant.plan.featureAI') }}
              </Tag>
              <Tag
                v-if="row.features.advancedAnalytics"
                class="!mr-0 rounded bg-cyan-500/10 text-cyan-500"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:bar-chart-3" class="size-3" />
                </template>
                {{ $t('admin.tenant.plan.featureAnalytics') }}
              </Tag>
              <Tag
                v-if="row.features.whiteLabel"
                class="!mr-0 rounded bg-orange-500/10 text-orange-500"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:palette" class="size-3" />
                </template>
                {{ $t('admin.tenant.plan.featureWhiteLabel') }}
              </Tag>
              <Tag
                v-if="row.features.prioritySupport"
                class="!mr-0 rounded bg-pink-500/10 text-pink-500"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:headphones" class="size-3" />
                </template>
                {{ $t('admin.tenant.plan.featureSupport') }}
              </Tag>
            </div>
            <span v-else class="text-muted-foreground">-</span>
          </div>
        </template>

        <!-- 计费周期列 -->
        <template #billingCycle_cell="{ row }">
          <div class="flex justify-center">
            <Tag
              :class="
                row.billingCycle === 'yearly'
                  ? 'rounded-lg bg-amber-500/10 text-amber-500'
                  : 'rounded-lg bg-blue-500/10 text-blue-500'
              "
            >
              <template #icon>
                <IconifyIcon
                  :icon="
                    row.billingCycle === 'yearly'
                      ? 'lucide:calendar'
                      : 'lucide:refresh-cw'
                  "
                  class="size-3"
                />
              </template>
              {{ getBillingCycleText(row.billingCycle) }}
            </Tag>
          </div>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <div class="flex justify-center">
            <Tooltip :title="formatDate(row.createdAt)">
              <span class="text-muted-foreground">{{
                formatRelativeTime(row.createdAt)
              }}</span>
            </Tooltip>
          </div>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
