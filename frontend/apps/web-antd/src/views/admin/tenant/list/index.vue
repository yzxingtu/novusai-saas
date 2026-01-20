<script lang="ts" setup>
/**
 * 租户列表页面
 */
import type { adminApi } from '#/api';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, message, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import {
  copyToClipboard,
  formatDate,
  formatDateOnly,
  formatRelativeTime,
} from '#/utils/common';

import { useColumns, useGridFormSchema } from './data';
import DomainsModal from './modules/domains-modal.vue';
import Form from './modules/form.vue';
import ResetPasswordModal from './modules/reset-password-modal.vue';

/** 获取名称首字（支持中英文） */
function getFirstChar(name: string): string {
  if (!name) return '?';
  // 英文取首字母大写
  if (/^[a-z]/i.test(name)) {
    return name[0]!.toUpperCase();
  }
  // 中文取首字
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
  const hash = name
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length]!;
}

type TenantInfo = adminApi.TenantInfo;

// 域名管理弹窗引用
const domainsModalRef = ref<InstanceType<typeof DomainsModal>>();

// 重置密码弹窗引用
const resetPasswordModalRef = ref<InstanceType<typeof ResetPasswordModal>>();

/**
 * 复制域名到剪贴板
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
 * 打开域名管理弹窗
 */
function onManageDomains(row: TenantInfo) {
  domainsModalRef.value?.open({
    tenantId: row.id,
    tenantName: row.name,
    tenantCode: row.code,
  });
}

/**
 * 重置租户管理员密码
 */
function onResetPassword(row: TenantInfo) {
  resetPasswordModalRef.value?.open({
    id: row.id,
    name: row.name,
  });
}

/**
 * 一键登录租户后台
 */
async function onImpersonate(row: TenantInfo) {
  const hideLoading = message.loading({
    content: $t('admin.tenant.messages.impersonating', { name: row.name }),
    duration: 0,
    key: 'impersonate_tenant',
  });
  try {
    const result = await admin.tenantImpersonateApi(row.id);
    message.success({
      content: $t('admin.tenant.messages.impersonateSuccess'),
      key: 'impersonate_tenant',
    });
    // 构建跳转 URL 并在新窗口打开
    const targetUrl = `/tenant/impersonate?token=${encodeURIComponent(result.impersonateToken)}`;
    window.open(targetUrl, '_blank');
  } catch {
    hideLoading();
    message.error({
      content: $t('admin.tenant.messages.impersonateFailed'),
      key: 'impersonate_tenant',
    });
  }
}

// 声明式 CRUD 页面（套餐下拉由 ApiSelect 自动加载，导出按钮自动添加）
const { Grid, FormDrawer, ExportModal, onCreate, onRefresh } =
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
    customActions: {
      impersonate: onImpersonate,
      manageDomains: onManageDomains,
      resetPassword: onResetPassword,
    },
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />
    <DomainsModal ref="domainsModalRef" @success="onRefresh" />
    <ResetPasswordModal ref="resetPasswordModalRef" @success="onRefresh" />
    <ExportModal />

    <!-- 表格 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 租户编码列 -->
        <template #code_cell="{ row }">
          <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
            <span
              class="cursor-pointer font-mono text-gray-500 hover:text-primary"
              @click="onCopyDomain(row.code)"
            >
              {{ row.code }}
              <IconifyIcon
                icon="lucide:copy"
                class="ml-1 inline-block size-3 opacity-50"
              />
            </span>
          </Tooltip>
        </template>

        <!-- 租户名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <span
              class="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium text-white"
              :class="getAvatarColor(row.name)"
            >
              {{ getFirstChar(row.name) }}
            </span>
            <span class="truncate font-medium">{{ row.name }}</span>
          </div>
        </template>

        <!-- 域名数列 -->
        <template #domainCount_cell="{ row }">
          <Tag :color="(row.domainCount ?? 0) > 1 ? 'blue' : 'default'">
            {{ row.domainCount ?? 0 }}
          </Tag>
        </template>

        <!-- 主域名列 -->
        <template #primaryDomain_cell="{ row }">
          <template v-if="row.primaryDomain">
            <Tooltip :title="$t('admin.tenant.domain.clickToCopy')">
              <span
                class="cursor-pointer text-primary hover:underline"
                @click="onCopyDomain(row.primaryDomain.domain)"
              >
                {{ row.primaryDomain.domain }}
              </span>
            </Tooltip>
            <a
              :href="`https://${row.primaryDomain.domain}`"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-1 text-gray-400 hover:text-primary"
              @click.stop
            >
              <IconifyIcon
                icon="lucide:external-link"
                class="inline-block size-3"
              />
            </a>
            <span
              v-if="row.primaryDomain.verificationStatus === 'pending'"
              class="ml-1 text-xs text-warning"
            >
              <IconifyIcon icon="lucide:alert-circle" class="inline-block" />
            </span>
          </template>
          <span v-else class="text-gray-300">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 联系人列 -->
        <template #contactName_cell="{ row }">
          <span v-if="row.contactName">{{ row.contactName }}</span>
          <span v-else class="text-gray-300">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 联系电话列 -->
        <template #contactPhone_cell="{ row }">
          <span v-if="row.contactPhone">{{ row.contactPhone }}</span>
          <span v-else class="text-gray-300">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 套餐列 -->
        <template #planInfo_cell="{ row }">
          <template v-if="row.planInfo">
            <Tooltip :title="row.planInfo.name">
              <Tag color="processing" class="max-w-[120px] truncate">
                {{ row.planInfo.name }}
              </Tag>
            </Tooltip>
          </template>
          <span v-else class="text-gray-300">{{
            $t('admin.common.notSet')
          }}</span>
        </template>

        <!-- 到期时间列 -->
        <template #expiresAt_cell="{ row }">
          <Tag v-if="!row.expiresAt" color="success">
            <IconifyIcon
              icon="lucide:infinity"
              class="mr-1 inline-block size-3"
            />
            {{ $t('admin.tenant.expiryStatus.permanent') }}
          </Tag>
          <template v-else>
            <Tag v-if="new Date(row.expiresAt) < new Date()" color="error">
              {{ $t('admin.tenant.expiryStatus.expired') }}
            </Tag>
            <Tag
              v-else-if="
                new Date(row.expiresAt) <
                new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
              "
              color="warning"
            >
              {{ formatDateOnly(row.expiresAt) }}
            </Tag>
            <span v-else class="text-gray-500">
              {{ formatDateOnly(row.expiresAt) }}
            </span>
          </template>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.createdAt)">
            <span class="text-gray-500">{{
              formatRelativeTime(row.createdAt)
            }}</span>
          </Tooltip>
        </template>

        <template #toolbar-tools>
          <Card size="small" class="mr-4 !border-primary/20 !bg-primary/5">
            <span class="text-sm text-gray-600">{{
              $t('admin.tenant.tip')
            }}</span>
          </Card>
          <Card
            v-access:code="['tenant:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{ $t('admin.tenant.create') }}</span>
            </div>
          </Card>
          <!-- 导出按钮由 useCrudPage 自动添加 -->
        </template>
      </Grid>
    </Card>
  </Page>
</template>
