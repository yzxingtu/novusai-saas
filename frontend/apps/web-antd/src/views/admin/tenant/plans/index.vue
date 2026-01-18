<script lang="ts" setup>
/**
 * 套餐列表页面
 */
import type { adminApi } from '#/api';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { Download, Plus } from '@vben/icons';

import { Button, Card, Tooltip } from 'ant-design-vue';

import { useAutoTableDragSort, useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';

import { getFormDefaults, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';
import PermissionsModal from './modules/permissions-modal.vue';

type TenantPlanInfo = adminApi.TenantPlanInfo;

// 权限弹窗相关
const permissionsModalRef = ref<InstanceType<typeof PermissionsModal>>();

// 处理设置权限
function handleSetPermissions(row: TenantPlanInfo) {
  permissionsModalRef.value?.open(row);
}

// 声明式 CRUD 页面
const {
  Grid,
  FormDrawer,
  ExportModal,
  gridApi,
  onCreate,
  onRefresh,
  openExportModal,
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
          <Tooltip :title="$t('shared.common.export')">
            <Button
              type="primary"
              shape="circle"
              @click="openExportModal"
            >
              <template #icon>
                <Download class="size-4" />
              </template>
            </Button>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
