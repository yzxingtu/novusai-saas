<script lang="ts" setup>
/**
 * 套餐列表页面
 */
import type { adminApi } from '#/api';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, message, Tag, Tooltip } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { copyToClipboard, formatDate, formatRelativeTime } from '#/utils/common';

import { getBillingCycleText, getFormDefaults, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';
import PermissionsModal from './modules/permissions-modal.vue';

type TenantPlanInfo = adminApi.TenantPlanInfo;

/** 获取名称首字（支持中英文） */
function getFirstChar(name: string): string {
  if (!name) return '?';
  if (/^[a-z]/i.test(name)) {
    return name[0]!.toUpperCase();
  }
  return name[0] || '?';
}

/** 根据名称生成背景色 */
function getAvatarColor(name: string): string {
  const colors = [
    'bg-blue-500',
    'bg-green-500',
    'bg-purple-500',
    'bg-orange-500',
    'bg-pink-500',
    'bg-cyan-500',
    'bg-indigo-500',
    'bg-teal-500',
  ];
  const hash = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length]!;
}

/** 复制编码到剪贴板 */
async function onCopyCode(code: string) {
  const success = await copyToClipboard(code);
  if (success) {
    message.success($t('admin.tenant.domain.copySuccess'));
  } else {
    message.error($t('admin.tenant.domain.copyFailed'));
  }
}

/** 获取计费周期 Tag 颜色 */
function getBillingCycleColor(cycle: string): string {
  switch (cycle) {
    case 'lifetime': return 'purple';
    case 'yearly': return 'gold';
    case 'quarterly': return 'blue';
    case 'monthly': return 'cyan';
    case 'one_time': return 'green';
    default: return 'default';
  }
}

/** 格式化价格 */
function formatPriceDisplay(price?: null | number | string): string {
  if (price === null || price === undefined) return '免费';
  const priceNum = typeof price === 'string' ? Number.parseFloat(price) : price;
  if (Number.isNaN(priceNum) || priceNum === 0) return '免费';
  return `¥${priceNum.toFixed(2)}`;
}

// 权限弹窗相关
const permissionsModalRef = ref<InstanceType<typeof PermissionsModal>>();

// 处理设置权限
function handleSetPermissions(row: TenantPlanInfo) {
  permissionsModalRef.value?.open(row);
}

// 声明式 CRUD 页面（导出按钮自动添加）
const {
  Grid,
  FormDrawer,
  ExportModal,
  gridApi,
  onCreate,
  onRefresh,
} = useCrudPage<TenantPlanInfo>({
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
  customActions: {
    permissions: handleSetPermissions,
  },
});

// 拖拽排序（自动初始化）
useAutoTableDragSort(() => gridApi.grid, {
  onUpdate: (id, sortOrder) =>
    admin.updateTenantPlanApi(id as number, { sort_order: sortOrder }),
  keyField: 'id',
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
        <!-- 套餐名称列：首字头像 + 名称 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <span
              class="flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-medium text-white"
              :class="getAvatarColor(row.name)"
            >
              {{ getFirstChar(row.name) }}
            </span>
            <span class="truncate font-medium">{{ row.name }}</span>
          </div>
        </template>

        <!-- 套餐编码列：等宽字体 + 点击复制 -->
        <template #code_cell="{ row }">
          <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
            <span
              class="cursor-pointer font-mono text-gray-500 hover:text-primary"
              @click="onCopyCode(row.code)"
            >
              {{ row.code }}
              <IconifyIcon icon="lucide:copy" class="ml-1 inline-block size-3 opacity-50" />
            </span>
          </Tooltip>
        </template>

        <!-- 价格列：突出显示 -->
        <template #price_cell="{ row }">
          <span
            class="text-lg font-semibold"
            :class="row.price && row.price > 0 ? 'text-orange-500' : 'text-green-500'"
          >
            {{ formatPriceDisplay(row.price) }}
          </span>
        </template>

        <!-- 计费周期列：Tag 标签 -->
        <template #billingCycle_cell="{ row }">
          <Tag :color="getBillingCycleColor(row.billingCycle)">
            {{ getBillingCycleText(row.billingCycle) }}
          </Tag>
        </template>

        <!-- 创建时间列：相对时间 + Tooltip -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-gray-500">{{ formatRelativeTime(row.createdAt) }}</span>
          </Tooltip>
        </template>

        <template #toolbar-tools>
          <Card
            v-access:code="['tenant_plan:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.tenant.plan.create')
              }}</span>
            </div>
          </Card>
          <!-- 导出按钮由 useCrudPage 自动添加 -->
        </template>
      </Grid>
    </Card>
  </Page>
</template>
