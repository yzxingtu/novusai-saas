<script lang="ts" setup>
/**
 * Tenant list page
 * 企业列表页面
 */
import type { adminApi } from '#/api';

import { computed, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Dropdown,
  Menu,
  MenuItem,
  message,
  Popconfirm,
  Popover,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import {
  copyToClipboard,
  formatDate,
  formatDateOnly,
  formatRelativeTime,
} from '#/utils/common';

import { useColumns, useFormSchema, useGridFormSchema } from './data';
import DomainsModal from './modules/DomainsModal.vue';
import ResetPasswordModal from './modules/ResetPasswordModal.vue';
import TenantAdminPanel from './modules/TenantAdminPanel.vue';
import Form from './modules/TenantForm.vue';
import TenantStorageDrawer from './modules/TenantStorageDrawer.vue';

defineOptions({ name: 'TenantList' });

type TenantInfo = adminApi.TenantInfo;

// Check if in dev mode / 检测是否为开发模式
const isDev = computed(() => import.meta.env.DEV);

/**
 * Build tenant origin URL
 * 构建企业端 origin URL
 * Dev mode: tenant domain + current port
 * 开发模式下使用企业域名 + 当前端口
 * Production: tenant primary domain
 * 生产模式下使用企业主域名
 */
function getTenantOrigin(domain: string): string {
  if (isDev.value) {
    return `${window.location.protocol}//${domain}:${window.location.port}`;
  }
  return `${window.location.protocol}//${domain}`;
}

// Domain management modal ref / 域名管理弹窗引用
const domainsModalRef = ref<InstanceType<typeof DomainsModal>>();

// Reset password modal ref / 重置密码弹窗引用
const resetPasswordModalRef = ref<InstanceType<typeof ResetPasswordModal>>();

// Storage config drawer ref / 存储配置抽屉引用
const storageDrawerRef = ref<InstanceType<typeof TenantStorageDrawer>>();

/**
 * Copy domain to clipboard / 复制域名到剪贴板
 */
async function onCopyDomain(domain: string) {
  const success = await copyToClipboard(domain);
  if (success) {
    message.success($t('admin.tenant.domain.copySuccess'));
  } else {
    message.error($t('admin.tenant.domain.copyFailed'));
  }
}

/**
 * Open domain management modal / 打开域名管理弹窗
 */
function onManageDomains(row: TenantInfo) {
  domainsModalRef.value?.open({
    tenantId: row.id,
    tenantName: row.name,
    tenantCode: row.code,
  });
}

/**
 * Reset tenant admin password / 重置企业管理员密码
 */
function onResetPassword(row: TenantInfo) {
  resetPasswordModalRef.value?.open({
    id: row.id,
    name: row.name,
  });
}

/**
 * Open storage config drawer / 打开存储配置抽屉
 */
function onStorageConfig(row: TenantInfo) {
  storageDrawerRef.value?.open({
    id: row.id,
    name: row.name,
  });
}

/**
 * One-click login to tenant backend (new window) / 一键登录企业后台(新窗口)
 */
async function onImpersonate(row: TenantInfo) {
  const hideLoading = message.loading({
    content: $t('admin.tenant.messages.impersonating', { name: row.name }),
    duration: 0,
    key: 'impersonate_tenant',
  });
  try {
    if (!row.primaryDomain?.domain) {
      hideLoading();
      message.warning($t('admin.tenant.messages.noPrimaryDomain'));
      return;
    }
    const result = await admin.tenantImpersonateApi(row.id);
    message.success({
      content: $t('admin.tenant.messages.impersonateSuccess'),
      key: 'impersonate_tenant',
    });
    const targetUrl = `${getTenantOrigin(row.primaryDomain.domain)}/tenant/impersonate?token=${encodeURIComponent(result.impersonateToken)}`;
    window.open(targetUrl, '_blank');
  } catch {
    hideLoading();
    message.error({
      content: $t('admin.tenant.messages.impersonateFailed'),
      key: 'impersonate_tenant',
    });
  }
}

/**
 * One-click login to tenant backend (current tab) - dev mode only / 一键登录企业后台(当前标签页) - 仅开发模式
 */
async function onImpersonateInCurrentTab(row: TenantInfo) {
  const hideLoading = message.loading({
    content: $t('admin.tenant.messages.impersonating', { name: row.name }),
    duration: 0,
    key: 'impersonate_tenant_current',
  });
  try {
    if (!row.primaryDomain?.domain) {
      hideLoading();
      message.warning($t('admin.tenant.messages.noPrimaryDomain'));
      return;
    }
    const result = await admin.tenantImpersonateApi(row.id);
    message.success({
      content: $t('admin.tenant.messages.impersonateSuccess'),
      key: 'impersonate_tenant_current',
    });
    const targetUrl = `${getTenantOrigin(row.primaryDomain.domain)}/tenant/impersonate?token=${encodeURIComponent(result.impersonateToken)}`;
    window.location.href = targetUrl;
  } catch {
    hideLoading();
    message.error({
      content: $t('admin.tenant.messages.impersonateFailed'),
      key: 'impersonate_tenant_current',
    });
  }
}

// Declarative CRUD page (plan dropdown auto-loaded by ApiSelect, export button auto-added) / 声明式 CRUD 页面（套餐下拉由 ApiSelect 自动加载，导出按钮自动添加）
const { Grid, FormDrawer, ExportModal, onRefresh, onCreate, gridApi, handleActionClick, openExportModal, formAiOperations } =
  useCrudPage<TenantInfo>({
    api: {
      list: admin.getTenantListApi,
      resource: '/admin/tenants',
      toggles: { is_active: admin.toggleTenantStatusApi },
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    i18nPrefix: 'admin.tenant',
    nameField: 'name',
    recycleBin: true,
    createPermission: 'tenant:create',
    gridOptions: {
      expandConfig: {
        accordion: true,
        iconOpen: 'vxe-icon-square-minus',
        iconClose: 'vxe-icon-square-plus',
        height: 'auto',
      },
    },
    customActions: {
      impersonate: onImpersonate,
      impersonateInCurrentTab: onImpersonateInCurrentTab,
      manageDomains: onManageDomains,
      resetPassword: onResetPassword,
      storageConfig: onStorageConfig,
    },
    ai: { pageKey: 'admin.tenant.list', formSchema: useFormSchema },
  });

const cleanupPageContext = registerPageContext('admin/tenant/list', () => ({
  page_key: 'admin.tenant.list',
  page_title: $t('admin.tenant.name'),
  page_data: {
    resource: '/admin/tenants',
  },
}));

const cleanupPageOps = registerPageOperations('admin.tenant.list', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the tenant list data',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Tenant list refreshed' };
    },
  },
  {
    name: 'create_record',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open the create tenant form',
    readonly: false,
    handler: async () => {
      onCreate();
      return { success: true, message: 'Create tenant form opened' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search tenants by name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Tenant name keyword' },
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
    description: 'Open the data export dialog for the tenant list',
    readonly: true,
    handler: async () => {
      openExportModal();
      return { success: true, message: 'Export dialog opened' };
    },
  },
  ...formAiOperations,
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />
    <DomainsModal ref="domainsModalRef" @success="onRefresh" />
    <ResetPasswordModal ref="resetPasswordModalRef" @success="onRefresh" />
    <TenantStorageDrawer ref="storageDrawerRef" />
    <ExportModal />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 企业管理员展开行 -->
        <template #expand_content="{ row }">
          <TenantAdminPanel :tenant-id="row.id" :tenant-name="row.name" />
        </template>
        <!-- 企业名称 + 账号列 -->
        <template #name_cell="{ row }">
          <div class="flex flex-col gap-0.5">
            <span class="font-medium text-foreground">{{ row.name }}</span>
            <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
              <span
                class="cursor-pointer font-mono text-xs text-muted-foreground transition-colors hover:text-primary"
                @click="onCopyDomain(row.code)"
              >
                {{ row.code }}
                <IconifyIcon
                  icon="lucide:copy"
                  class="ml-0.5 inline-block size-3 opacity-40"
                />
              </span>
            </Tooltip>
          </div>
        </template>

        <!-- 主域名列 -->
        <template #primaryDomain_cell="{ row }">
          <div class="flex items-center gap-2">
            <template v-if="row.primaryDomain">
              <div class="flex items-center gap-1">
                <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
                  <span
                    class="cursor-pointer text-sm text-primary transition-colors hover:underline"
                    @click="onCopyDomain(row.primaryDomain.domain)"
                  >
                    {{ row.primaryDomain.domain }}
                  </span>
                </Tooltip>
                <a
                  :href="`https://${row.primaryDomain.domain}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-muted-foreground transition-colors hover:text-primary"
                  @click.stop
                >
                  <IconifyIcon icon="lucide:external-link" class="size-3" />
                </a>
                <Tooltip
                  v-if="row.primaryDomain.verificationStatus === 'pending'"
                  :title="$t('admin.tenant.unverified')"
                >
                  <IconifyIcon
                    icon="lucide:alert-circle"
                    class="size-3 text-warning"
                  />
                </Tooltip>
              </div>
            </template>
            <span v-else class="text-muted-foreground">{{
              $t('admin.common.notSet')
            }}</span>

            <!-- 域名管理入口 -->
            <Tooltip :title="$t('admin.tenant.manageDomains')">
              <Button
                type="link"
                size="small"
                class="!p-0"
                @click.stop="onManageDomains(row)"
              >
                <IconifyIcon icon="lucide:settings" class="size-3" />
              </Button>
            </Tooltip>

            <!-- 更多域名 -->
            <Popover
              v-if="row.domains && row.domains.length > 1"
              :title="
                $t('admin.tenant.domain.totalCount', {
                  count: row.domains.length,
                })
              "
            >
              <template #content>
                <div class="flex max-h-60 flex-col gap-1 overflow-y-auto p-1">
                  <div
                    v-for="d in row.domains"
                    :key="d.id"
                    class="flex items-center justify-between gap-3 rounded-md px-2 py-1 hover:bg-muted"
                  >
                    <span
                      :class="{
                        'font-medium text-primary': d.isPrimary || d.is_primary,
                      }"
                      class="text-sm text-foreground"
                      >{{ d.domain }}</span
                    >
                    <div class="flex shrink-0 items-center gap-2">
                      <a
                        :href="`https://${d.domain}`"
                        target="_blank"
                        class="text-muted-foreground transition-colors hover:text-primary"
                      >
                        <IconifyIcon
                          icon="lucide:external-link"
                          class="size-3"
                        />
                      </a>
                      <Tag
                        v-if="d.isPrimary || d.is_primary"
                        class="!mr-0 rounded bg-primary/10 text-xs text-primary"
                      >
                        {{ $t('admin.tenant.domain.primaryTag') }}
                      </Tag>
                      <Tag
                        v-else-if="
                          d.verificationStatus === 'pending' ||
                          d.is_verified === false
                        "
                        class="!mr-0 rounded bg-warning/10 text-xs text-warning"
                      >
                        {{ $t('admin.tenant.domain.unverifiedTag') }}
                      </Tag>
                    </div>
                  </div>
                </div>
              </template>
              <Tag
                class="!mr-0 cursor-pointer rounded-md bg-muted text-xs text-muted-foreground"
              >
                +{{ row.domains.length - 1 }}
              </Tag>
            </Popover>
          </div>
        </template>

        <!-- 联系人列 -->
        <template #contactName_cell="{ row }">
          <span v-if="row.contactName" class="text-foreground">{{
            row.contactName
          }}</span>
          <span v-else class="text-muted-foreground">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 联系电话列 -->
        <template #contactPhone_cell="{ row }">
          <span v-if="row.contactPhone" class="text-foreground">{{
            row.contactPhone
          }}</span>
          <span v-else class="text-muted-foreground">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 套餐列 -->
        <template #planInfo_cell="{ row }">
          <template v-if="row.planInfo">
            <Tooltip :title="row.planInfo.name">
              <Tag
                :color="
                  row.planInfo.code === 'enterprise'
                    ? 'gold'
                    : row.planInfo.code === 'pro'
                      ? 'green'
                      : 'blue'
                "
                class="max-w-[120px] truncate rounded bg-primary/10 text-primary"
              >
                {{ row.planInfo.name }}
              </Tag>
            </Tooltip>
          </template>
          <span v-else class="text-muted-foreground">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 到期时间列 -->
        <template #expiresAt_cell="{ row }">
          <div class="flex justify-center">
            <Tag
              v-if="!row.expiresAt"
              class="rounded-lg bg-success/10 text-success"
            >
              <IconifyIcon
                icon="lucide:infinity"
                class="mr-1 inline-block size-3"
              />
              {{ $t('admin.tenant.expiryStatus.permanent') }}
            </Tag>
            <Tag
              v-else-if="new Date(row.expiresAt) < new Date()"
              class="rounded-lg bg-destructive/10 text-destructive"
            >
              {{ $t('admin.tenant.expiryStatus.expired') }}
            </Tag>
            <Tag
              v-else-if="
                new Date(row.expiresAt) <
                new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
              "
              class="rounded-lg bg-warning/10 text-warning"
            >
              {{ formatDateOnly(row.expiresAt) }}
            </Tag>
            <span v-else class="text-muted-foreground">
              {{ formatDateOnly(row.expiresAt) }}
            </span>
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

        <!-- 操作列 -->
        <template #operation_cell="{ row }">
          <div class="flex items-center justify-center gap-1">
            <!-- 更多下拉菜单 -->
            <Dropdown>
              <template #overlay>
                <Menu>
                  <MenuItem @click="onManageDomains(row)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:globe" class="size-4" />
                      <span>{{ $t('admin.tenant.manageDomains') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem @click="onStorageConfig(row)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:database" class="size-4" />
                      <span>{{ $t('shared.storage.adminTab.title') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem @click="onResetPassword(row)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:key-round" class="size-4" />
                      <span>{{ $t('admin.tenant.resetPassword') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem @click="onImpersonate(row)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:log-in" class="size-4" />
                      <span>{{ $t('admin.tenant.enterBackend') }}</span>
                    </div>
                  </MenuItem>
                  <!-- 开发模式: 当前标签页进入 -->
                  <MenuItem
                    v-if="isDev"
                    @click="onImpersonateInCurrentTab(row)"
                  >
                    <div class="flex items-center gap-2 text-warning">
                      <IconifyIcon icon="lucide:arrow-right" class="size-4" />
                      <span
                        >{{ $t('admin.tenant.enterCurrentTab') }} (Dev)</span
                      >
                    </div>
                  </MenuItem>
                </Menu>
              </template>
              <Tooltip :title="$t('admin.common.more')">
                <button class="action-icon-btn">
                  <IconifyIcon
                    icon="lucide:more-horizontal"
                    class="text-base"
                  />
                </button>
              </Tooltip>
            </Dropdown>
            <!-- 编辑按钮 -->
            <Tooltip :title="$t('common.edit')">
              <button
                class="action-icon-btn"
                @click="handleActionClick({ code: 'edit', row })"
              >
                <IconifyIcon icon="lucide:pencil" class="text-base" />
              </button>
            </Tooltip>
            <!-- 删除按钮 -->
            <Popconfirm
              :title="$t('ui.actionTitle.delete', [$t('admin.tenant.name')])"
              :description="$t('ui.actionMessage.deleteConfirm', [row.name])"
              placement="topLeft"
              @confirm="handleActionClick({ code: 'delete', row })"
            >
              <Tooltip :title="$t('common.delete')">
                <button class="action-icon-btn text-destructive">
                  <IconifyIcon icon="lucide:trash-2" class="text-base" />
                </button>
              </Tooltip>
            </Popconfirm>
          </div>
        </template>

        <template #toolbar-tools>
          <Card size="small" class="mr-4 !border-primary/20 !bg-primary/5">
            <span class="text-sm text-gray-600">{{
              $t('admin.tenant.tip')
            }}</span>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>

<style scoped>
:deep(.vxe-body--expanded-cell) {
  padding: 0 !important;
}
</style>
