<script lang="ts" setup>
/**
 * Tenant domain management modal - main modal
 * 租户域名管理弹窗 - 主弹窗
 * Shows domain list, provides add/detail/set primary/verify/delete entries
 * 展示域名列表，提供添加、详情、设为主域名、验证、删除等入口
 */
import type {
  DnsGuideData,
  DomainModalData,
  TenantDomainInfo,
} from './domains-types';
import type {
  DevHostDomainStatus,
  DevHostsStatus,
  DevHostsStatusResponse,
} from '#/api/admin/tenant-domain';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  message,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

import DomainsAddDrawer from './DomainsAddDrawer.vue';
import DomainsDetailDrawer from './DomainsDetailDrawer.vue';
import DomainsDnsGuideModal from './DomainsDnsGuideModal.vue';
import DomainsSslDrawer from './DomainsSslDrawer.vue';

// Emits
const emits = defineEmits<{
  success: [];
}>();

// State / 状态
const domains = ref<TenantDomainInfo[]>([]);
const loading = ref(false);
const currentTenant = ref<DomainModalData | null>(null);
const devHostsOverview = ref<DevHostsStatusResponse | null>(null);
const devHostsLoading = ref(false);
const devHostsLoadError = ref(false);
const syncingDomainIds = ref<number[]>([]);
const removingDomainIds = ref<number[]>([]);
const syncingAllDevHosts = ref(false);

// Child component refs / 子组件引用
const addDrawerRef = ref<InstanceType<typeof DomainsAddDrawer>>();
const detailDrawerRef = ref<InstanceType<typeof DomainsDetailDrawer>>();
const dnsGuideModalRef = ref<InstanceType<typeof DomainsDnsGuideModal>>();
const sslDrawerRef = ref<InstanceType<typeof DomainsSslDrawer>>();

// Computed title / 计算标题
const title = computed(() =>
  currentTenant.value
    ? `${$t('admin.tenant.domain.title')} - ${currentTenant.value.tenantName}`
    : $t('admin.tenant.domain.title'),
);

// Modal
const [Modal, modalApi] = useVbenModal({
  async onOpenChange(isOpen) {
    if (isOpen) {
      const data = modalApi.getData<DomainModalData>();
      if (data?.tenantId) {
        currentTenant.value = data;
        await Promise.all([loadDomains(), loadDevHosts()]);
      }
    } else {
      currentTenant.value = null;
      domains.value = [];
      devHostsOverview.value = null;
      devHostsLoadError.value = false;
      syncingDomainIds.value = [];
      removingDomainIds.value = [];
      syncingAllDevHosts.value = false;
    }
  },
  footer: false,
});

/** Load domain list / 加载域名列表 */
async function loadDomains() {
  if (!currentTenant.value?.tenantId) return;

  loading.value = true;
  try {
    const result = await admin.getTenantDomainsApi(
      currentTenant.value.tenantId,
    );
    domains.value = result.items as TenantDomainInfo[];
  } catch {
  } finally {
    loading.value = false;
  }
}

async function loadDevHosts() {
  if (!currentTenant.value?.tenantId) return;

  devHostsLoading.value = true;
  devHostsLoadError.value = false;
  try {
    devHostsOverview.value = await admin.getTenantDevHostsStatusApi(
      currentTenant.value.tenantId,
    );
  } catch {
    devHostsLoadError.value = true;
  } finally {
    devHostsLoading.value = false;
  }
}

/** Open add domain drawer / 打开添加域名抽屉 */
function onOpenAddDrawer() {
  if (!currentTenant.value) return;
  addDrawerRef.value?.open(currentTenant.value.tenantId);
}

/** Add success callback / 添加成功回调 */
async function onAddSuccess(newDomain: TenantDomainInfo) {
  await Promise.all([loadDomains(), loadDevHosts()]);
  emits('success');
  // Open DNS guide / 打开 DNS 引导
  if (newDomain.verificationStatus === 'pending' && currentTenant.value) {
    const guideData: DnsGuideData = {
      domain: newDomain.domain,
      tenantId: currentTenant.value.tenantId,
      domainId: newDomain.id,
      verificationInfo: newDomain.verificationInfo,
      verificationToken: newDomain.verificationToken,
      cnameTarget: newDomain.cnameTarget,
    };
    dnsGuideModalRef.value?.open(guideData);
  }
}

/** Open detail drawer / 打开详情抽屉 */
function onOpenDetail(domain: TenantDomainInfo) {
  if (!currentTenant.value) return;
  detailDrawerRef.value?.open({
    domainId: domain.id,
    tenantId: currentTenant.value.tenantId,
  });
}

/** Detail update success callback / 详情更新成功回调 */
async function onDetailSuccess() {
  await Promise.all([loadDomains(), loadDevHosts()]);
  emits('success');
}

/** Open DNS guide / 打开 DNS 引导 */
function onOpenDnsGuide(domain: TenantDomainInfo) {
  if (!currentTenant.value) return;
  const guideData: DnsGuideData = {
    domain: domain.domain,
    tenantId: currentTenant.value.tenantId,
    domainId: domain.id,
    verificationInfo: domain.verificationInfo,
    verificationToken: domain.verificationToken,
    cnameTarget: domain.cnameTarget,
  };
  dnsGuideModalRef.value?.open(guideData);
}

/** Open SSL management drawer / 打开 SSL 管理抽屉 */
function onOpenSslDrawer(domain: TenantDomainInfo) {
  if (!currentTenant.value) return;
  sslDrawerRef.value?.open({
    domainId: domain.id,
    tenantId: currentTenant.value.tenantId,
    domain: domain.domain,
    isDefault: domain.domainType === 'default',
  });
}

/** Set primary domain / 设置主域名 */
async function onSetPrimary(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId || domain.isPrimary) return;

  try {
    await admin.setPrimaryDomainApi(currentTenant.value.tenantId, domain.id);
    message.success($t('admin.tenant.domain.setPrimarySuccess'));
    await Promise.all([loadDomains(), loadDevHosts()]);
    emits('success');
  } catch {}
}

/** Verify domain / 验证域名 */
async function onVerifyDomain(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId) return;

  try {
    const result = await admin.verifyTenantDomainApi(
      currentTenant.value.tenantId,
      domain.id,
    );
    if (result.verificationStatus === 'verified') {
      message.success($t('admin.tenant.domain.verifySuccess'));
    } else {
      message.warning($t('admin.tenant.domain.verifyFailed'));
    }
    await Promise.all([loadDomains(), loadDevHosts()]);
    emits('success');
  } catch {}
}

/** Delete domain / 删除域名 */
async function onDeleteDomain(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId) return;

  try {
    await admin.deleteTenantDomainApi(currentTenant.value.tenantId, domain.id);
    message.success($t('admin.tenant.domain.deleteSuccess'));
    await Promise.all([loadDomains(), loadDevHosts()]);
    emits('success');
  } catch {}
}

function getDevHostsDomainStatus(domainId: number) {
  return (
    devHostsOverview.value?.domains.find((item) => item.domainId === domainId) ||
    null
  );
}

function getDevHostsTagConfig(status: DevHostsStatus) {
  switch (status) {
    case 'managed_present': {
      return {
        color: 'success',
        icon: 'lucide:hard-drive-download',
      };
    }
    case 'manual_present': {
      return {
        color: 'processing',
        icon: 'lucide:file-pen-line',
      };
    }
    case 'not_required': {
      return {
        color: 'default',
        icon: 'lucide:minus-circle',
      };
    }
    case 'unsupported': {
      return {
        color: 'default',
        icon: 'lucide:ban',
      };
    }
    default: {
      return {
        color: 'warning',
        icon: 'lucide:triangle-alert',
      };
    }
  }
}

function isSyncingDomain(domainId: number) {
  return syncingDomainIds.value.includes(domainId);
}

function isRemovingDomain(domainId: number) {
  return removingDomainIds.value.includes(domainId);
}

function canSyncDevHost(domainStatus: DevHostDomainStatus | null) {
  if (!domainStatus || !devHostsOverview.value?.runtime.enabled) return false;
  return domainStatus.eligible && domainStatus.status !== 'unsupported';
}

/** Translate reason code to i18n string / 将 reason 内部码转换为 i18n 文本 */
function getDevHostsReasonText(reason?: null | string): string {
  if (!reason) return '';
  const key = `admin.tenant.domain.devHosts.reason.${reason}`;
  const translated = $t(key);
  return translated === key ? reason : translated;
}

function canRemoveDevHost(domainStatus: DevHostDomainStatus | null) {
  if (!domainStatus) return false;
  return domainStatus.managed;
}

function getDevHostsCliCommand(domain?: string) {
  if (!domain) return '';
  return $t('admin.tenant.domain.devHosts.cliCommand', { domain });
}

async function onCopyDevHostsCommand(domain?: string) {
  const command = getDevHostsCliCommand(domain);
  if (!command) return;
  const success = await copyToClipboard(command);
  if (success) {
    message.success($t('admin.tenant.domain.copySuccess'));
  } else {
    message.error($t('admin.tenant.domain.copyFailed'));
  }
}

async function onSyncAllDevHosts() {
  if (!currentTenant.value?.tenantId) return;

  syncingAllDevHosts.value = true;
  try {
    const result = await admin.syncAllTenantDevHostsApi(currentTenant.value.tenantId);
    devHostsOverview.value = {
      runtime: result.runtime,
      domains: result.domains,
    };
    message.success(
      $t('admin.tenant.domain.devHosts.syncAllSuccess', {
        skipped: result.skipped,
        synced: result.synced,
      }),
    );
    await loadDomains();
  } catch {
  } finally {
    syncingAllDevHosts.value = false;
  }
}

async function onSyncDevHost(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId || isSyncingDomain(domain.id)) return;

  syncingDomainIds.value = [...syncingDomainIds.value, domain.id];
  try {
    const result = await admin.syncTenantDevHostApi(
      currentTenant.value.tenantId,
      domain.id,
    );
    if (devHostsOverview.value) {
      devHostsOverview.value = {
        runtime: result.runtime,
        domains: devHostsOverview.value.domains.map((item) =>
          item.domainId === domain.id ? result.domain : item,
        ),
      };
    } else {
      await loadDevHosts();
    }
    message.success($t('admin.tenant.domain.devHosts.syncSuccess'));
  } catch {
  } finally {
    syncingDomainIds.value = syncingDomainIds.value.filter((id) => id !== domain.id);
  }
}

async function onRemoveDevHost(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId || isRemovingDomain(domain.id)) return;

  removingDomainIds.value = [...removingDomainIds.value, domain.id];
  try {
    const result = await admin.removeTenantDevHostApi(
      currentTenant.value.tenantId,
      domain.id,
    );
    if (devHostsOverview.value) {
      devHostsOverview.value = {
        runtime: result.runtime,
        domains: devHostsOverview.value.domains.map((item) =>
          item.domainId === domain.id ? result.domain : item,
        ),
      };
    } else {
      await loadDevHosts();
    }
    message.success($t('admin.tenant.domain.devHosts.removeSuccess'));
  } catch {
  } finally {
    removingDomainIds.value = removingDomainIds.value.filter((id) => id !== domain.id);
  }
}

/** Get verification status tag config / 获取验证状态标签配置 */
function getVerificationTagConfig(status: string) {
  switch (status) {
    case 'failed': {
      return {
        color: 'error',
        icon: 'lucide:x-circle',
        text: $t('admin.tenant.domain.verifyFailed'),
      };
    }
    case 'verified': {
      return {
        color: 'success',
        icon: 'lucide:check-circle',
        text: $t('admin.tenant.domain.verified'),
      };
    }
    default: {
      return {
        color: 'warning',
        icon: 'lucide:clock',
        text: $t('admin.tenant.domain.pending'),
      };
    }
  }
}

/** Get SSL status tag config / 获取 SSL 状态标签配置 */
function getSslTagConfig(status: string) {
  switch (status) {
    case 'active': {
      return {
        color: 'success',
        icon: 'lucide:shield-check',
        text: $t('admin.tenant.domain.ssl.status.active'),
      };
    }
    case 'expired': {
      return {
        color: 'error',
        icon: 'lucide:shield-off',
        text: $t('admin.tenant.domain.ssl.status.expired'),
      };
    }
    case 'pending': {
      return {
        color: 'processing',
        icon: 'lucide:shield',
        text: $t('admin.tenant.domain.ssl.status.pending'),
      };
    }
    default: {
      return {
        color: 'default',
        icon: 'lucide:shield-x',
        text: $t('admin.tenant.domain.ssl.status.none'),
      };
    }
  }
}

/** Open modal / 打开弹窗 */
function open(data: DomainModalData) {
  modalApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Modal :title="title" :loading="loading" class="w-[800px]">
    <div class="min-h-[400px]">
      <Spin :spinning="loading">
        <div class="mb-4 flex flex-wrap items-center gap-2">
          <Button type="primary" @click="onOpenAddDrawer">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
            {{ $t('admin.tenant.domain.addDomain') }}
          </Button>
          <Button :loading="devHostsLoading" @click="loadDevHosts">
            <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
            {{ $t('admin.tenant.domain.devHosts.refresh') }}
          </Button>
          <Button
            v-if="devHostsOverview?.runtime.enabled"
            :loading="syncingAllDevHosts"
            @click="onSyncAllDevHosts"
          >
            <IconifyIcon icon="lucide:hard-drive-download" class="mr-1 size-4" />
            {{ $t('admin.tenant.domain.devHosts.syncAll') }}
          </Button>
        </div>

        <div class="mb-4 rounded-lg border border-border bg-card p-4">
          <div class="mb-3 flex items-center gap-2">
            <IconifyIcon icon="lucide:laptop" class="size-4 text-primary" />
            <span class="font-medium">{{
              $t('admin.tenant.domain.devHosts.title')
            }}</span>
          </div>

          <Spin :spinning="devHostsLoading">
            <template v-if="devHostsOverview">
              <div class="grid gap-3 md:grid-cols-3">
                <div class="rounded-md bg-accent/30 p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.tenant.domain.devHosts.os') }}
                  </div>
                  <div class="mt-1 font-medium">
                    {{ devHostsOverview.runtime.osName || '--' }}
                  </div>
                </div>
                <div class="rounded-md bg-accent/30 p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.tenant.domain.devHosts.hostsPath') }}
                  </div>
                  <div class="mt-1 break-all font-mono text-xs">
                    {{ devHostsOverview.runtime.hostsPath || '--' }}
                  </div>
                </div>
                <div class="rounded-md bg-accent/30 p-3">
                  <div class="text-xs text-muted-foreground">
                    {{ $t('admin.tenant.domain.devHosts.writeAccess') }}
                  </div>
                  <div class="mt-1 font-medium">
                    {{
                      devHostsOverview.runtime.canWriteHint
                        ? $t('admin.tenant.domain.devHosts.writeYes')
                        : $t('admin.tenant.domain.devHosts.writeNo')
                    }}
                  </div>
                </div>
              </div>

              <Alert
                v-if="!devHostsOverview.runtime.enabled"
                class="mt-3"
                type="warning"
                show-icon
                :message="$t('admin.tenant.domain.devHosts.disabled')"
              />

              <Alert
                v-else-if="devHostsOverview.runtime.requiresElevation"
                class="mt-3"
                type="warning"
                show-icon
              >
                <template #message>
                  {{ $t('admin.tenant.domain.devHosts.elevationHint') }}
                </template>
                <template #description>
                  <div class="flex flex-wrap items-center gap-2">
                    <code class="rounded bg-accent/30 px-2 py-1 text-xs">
                      {{ getDevHostsCliCommand(domains[0]?.domain) }}
                    </code>
                    <Button
                      v-if="domains[0]?.domain"
                      size="small"
                      type="link"
                      @click="onCopyDevHostsCommand(domains[0]?.domain)"
                    >
                      {{ $t('admin.tenant.domain.clickToCopy') }}
                    </Button>
                  </div>
                </template>
              </Alert>

              <Alert
                v-if="devHostsOverview.runtime.enabled"
                class="mt-3"
                type="info"
                show-icon
                :message="$t('admin.tenant.domain.devHosts.remoteWarning')"
              />
            </template>

            <template v-else-if="!devHostsLoading">
              <Alert
                v-if="devHostsLoadError"
                type="error"
                show-icon
                :message="$t('admin.tenant.domain.devHosts.loadError')"
              >
                <template #action>
                  <Button size="small" @click="loadDevHosts">
                    {{ $t('admin.tenant.domain.devHosts.refresh') }}
                  </Button>
                </template>
              </Alert>
            </template>
          </Spin>
        </div>

        <div class="flex flex-col gap-3">
          <div
            v-for="domain in domains"
            :key="domain.id"
            class="rounded-lg border border-border p-4 transition-all hover:border-primary hover:shadow-sm"
          >
            <!-- 域名信息头部 -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <IconifyIcon icon="lucide:globe" class="size-5 text-primary" />
                <span class="font-mono text-base font-medium">{{
                  domain.domain
                }}</span>
                <Tag v-if="domain.isPrimary" color="blue">
                  {{ $t('admin.tenant.domain.primaryDomain') }}
                </Tag>
                <Tag v-if="domain.domainType === 'default'" color="default">
                  {{ $t('admin.tenant.domain.defaultDomain') }}
                </Tag>
              </div>
            </div>

            <!-- 状态标签 -->
            <div class="mt-3 flex flex-wrap items-center gap-4">
              <!-- 域名类型 -->
              <div
                class="flex items-center gap-1 text-sm text-muted-foreground"
              >
                <span>{{ $t('admin.tenant.domain.type') }}:</span>
                <span>{{
                  domain.domainType === 'default'
                    ? $t('admin.tenant.domain.defaultDomain')
                    : $t('admin.tenant.domain.customDomain')
                }}</span>
              </div>

              <!-- 验证状态 -->
              <div class="flex items-center gap-1">
                <span class="text-sm text-muted-foreground"
                  >{{ $t('admin.tenant.domain.verificationStatus') }}:</span
                >
                <Tag
                  :color="
                    getVerificationTagConfig(domain.verificationStatus).color
                  "
                >
                  <IconifyIcon
                    :icon="
                      getVerificationTagConfig(domain.verificationStatus).icon
                    "
                    class="mr-1 size-3"
                  />
                  {{ getVerificationTagConfig(domain.verificationStatus).text }}
                </Tag>
              </div>

              <!-- SSL 状态 (只显示自定义域名) -->
              <div
                v-if="domain.domainType === 'custom'"
                class="flex items-center gap-1"
              >
                <span class="text-sm text-muted-foreground">SSL:</span>
                <Tag :color="getSslTagConfig(domain.sslStatus).color">
                  <IconifyIcon
                    :icon="getSslTagConfig(domain.sslStatus).icon"
                    class="mr-1 size-3"
                  />
                  {{ getSslTagConfig(domain.sslStatus).text }}
                </Tag>
              </div>

              <div
                v-if="getDevHostsDomainStatus(domain.id)"
                class="flex items-center gap-1"
              >
                <span class="text-sm text-muted-foreground">
                  {{ $t('admin.tenant.domain.devHosts.title') }}:
                </span>
                <Tag
                  :color="
                    getDevHostsTagConfig(getDevHostsDomainStatus(domain.id)!.status)
                      .color
                  "
                >
                  <IconifyIcon
                    :icon="
                      getDevHostsTagConfig(getDevHostsDomainStatus(domain.id)!.status)
                        .icon
                    "
                    class="mr-1 size-3"
                  />
                  {{
                    $t(
                      `admin.tenant.domain.devHosts.status.${getDevHostsDomainStatus(domain.id)!.status}`,
                    )
                  }}
                </Tag>
                <span
                  v-if="getDevHostsDomainStatus(domain.id)?.matchedIp"
                  class="text-xs text-muted-foreground"
                >
                  {{ getDevHostsDomainStatus(domain.id)?.matchedIp }}
                </span>
              </div>
            </div>

            <!-- 备注 -->
            <div
              v-if="domain.remark"
              class="mt-2 text-sm text-muted-foreground"
            >
              <span class="font-medium"
                >{{ $t('admin.tenant.domain.remark') }}:</span
              >
              <span class="ml-1">{{ domain.remark }}</span>
            </div>

            <div
              v-if="getDevHostsDomainStatus(domain.id)?.reason"
              class="mt-2 text-xs text-muted-foreground"
            >
              {{ getDevHostsReasonText(getDevHostsDomainStatus(domain.id)?.reason) }}
            </div>

            <!-- 操作按钮 -->
            <div
              class="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3"
            >
              <!-- 编辑域名 -->
              <Button type="link" size="small" @click="onOpenDetail(domain)">
                <IconifyIcon icon="lucide:pencil" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.editDomain') }}
              </Button>

              <!-- SSL 管理 (已验证的自定义域名才显示) -->
              <Button
                v-if="
                  domain.verificationStatus === 'verified' &&
                  domain.domainType === 'custom'
                "
                type="link"
                size="small"
                @click="onOpenSslDrawer(domain)"
              >
                <IconifyIcon icon="lucide:shield" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.ssl.manage') }}
              </Button>

              <!-- DNS 配置引导 (待验证才显示) -->
              <Button
                v-if="domain.verificationStatus === 'pending'"
                type="link"
                size="small"
                @click="onOpenDnsGuide(domain)"
              >
                <IconifyIcon icon="lucide:info" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.dnsGuide.title') }}
              </Button>

              <!-- 验证域名 (待验证才显示) -->
              <Button
                v-if="domain.verificationStatus === 'pending'"
                type="link"
                size="small"
                @click="onVerifyDomain(domain)"
              >
                <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.verifyDomain') }}
              </Button>

              <!-- 设为主域名 (非主域名显示，未验证时禁用) -->
              <Tooltip
                v-if="!domain.isPrimary"
                :title="
                  domain.verificationStatus !== 'verified'
                    ? $t('admin.tenant.domain.verifyFirst')
                    : ''
                "
              >
                <Button
                  type="link"
                  size="small"
                  :disabled="domain.verificationStatus !== 'verified'"
                  @click="onSetPrimary(domain)"
                >
                  <IconifyIcon icon="lucide:star" class="mr-1 size-4" />
                  {{ $t('admin.tenant.domain.setPrimary') }}
                </Button>
              </Tooltip>

              <Button
                v-if="canSyncDevHost(getDevHostsDomainStatus(domain.id))"
                type="link"
                size="small"
                :loading="isSyncingDomain(domain.id)"
                @click="onSyncDevHost(domain)"
              >
                <IconifyIcon
                  icon="lucide:hard-drive-download"
                  class="mr-1 size-4"
                />
                {{ $t('admin.tenant.domain.devHosts.sync') }}
              </Button>

              <Button
                v-if="canRemoveDevHost(getDevHostsDomainStatus(domain.id))"
                type="link"
                size="small"
                :loading="isRemovingDomain(domain.id)"
                @click="onRemoveDevHost(domain)"
              >
                <IconifyIcon icon="lucide:eraser" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.devHosts.remove') }}
              </Button>

              <!-- 删除 (自定义域名且非主域名才显示) -->
              <Popconfirm
                v-if="domain.domainType === 'custom' && !domain.isPrimary"
                :title="
                  $t('admin.tenant.domain.confirmDelete', {
                    domain: domain.domain,
                  })
                "
                @confirm="onDeleteDomain(domain)"
              >
                <Button type="link" size="small" danger>
                  <IconifyIcon icon="lucide:trash-2" class="mr-1 size-4" />
                  {{ $t('admin.tenant.domain.deleteDomain') }}
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div
          v-if="!loading && domains.length === 0"
          class="flex flex-col items-center justify-center py-16 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:globe" class="mb-3 size-16 opacity-30" />
          <span class="text-sm">{{ $t('admin.tenant.domain.noDomains') }}</span>
        </div>
      </Spin>
    </div>
  </Modal>

  <!-- 添加域名抽屉 -->
  <DomainsAddDrawer ref="addDrawerRef" @success="onAddSuccess" />

  <!-- 域名详情抽屉 -->
  <DomainsDetailDrawer ref="detailDrawerRef" @success="onDetailSuccess" />

  <!-- DNS 引导弹窗 -->
  <DomainsDnsGuideModal ref="dnsGuideModalRef" @success="loadDomains" />

  <!-- SSL 管理抽屉 -->
  <DomainsSslDrawer ref="sslDrawerRef" />
</template>
