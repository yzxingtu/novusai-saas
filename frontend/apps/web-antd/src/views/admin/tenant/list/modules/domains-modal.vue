<script lang="ts" setup>
/**
 * 租户域名管理弹窗 - 主弹窗
 * 展示域名列表，提供添加、详情、设为主域名、验证、删除等入口
 */
import type { DnsGuideData, DomainModalData, TenantDomainInfo } from './domains-types';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  message,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';

import DomainsAddDrawer from './domains-add-drawer.vue';
import DomainsDetailDrawer from './domains-detail-drawer.vue';
import DomainsDnsGuideModal from './domains-dns-guide-modal.vue';
import DomainsSslDrawer from './domains-ssl-drawer.vue';

// Emits
const emits = defineEmits<{
  success: [];
}>();

// 状态
const domains = ref<TenantDomainInfo[]>([]);
const loading = ref(false);
const currentTenant = ref<DomainModalData | null>(null);

// 子组件引用
const addDrawerRef = ref<InstanceType<typeof DomainsAddDrawer>>();
const detailDrawerRef = ref<InstanceType<typeof DomainsDetailDrawer>>();
const dnsGuideModalRef = ref<InstanceType<typeof DomainsDnsGuideModal>>();
const sslDrawerRef = ref<InstanceType<typeof DomainsSslDrawer>>();

// 计算标题
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
        await loadDomains();
      }
    } else {
      currentTenant.value = null;
      domains.value = [];
    }
  },
  footer: false,
});

/** 加载域名列表 */
async function loadDomains() {
  if (!currentTenant.value?.tenantId) return;

  loading.value = true;
  try {
    const result = await admin.getTenantDomainsApi(
      currentTenant.value.tenantId,
    );
    domains.value = result.items as TenantDomainInfo[];
  } catch (error) {
    console.error('Failed to load domains:', error);
  } finally {
    loading.value = false;
  }
}

/** 打开添加域名抽屉 */
function onOpenAddDrawer() {
  if (!currentTenant.value) return;
  addDrawerRef.value?.open(currentTenant.value.tenantId);
}

/** 添加成功回调 */
async function onAddSuccess(newDomain: TenantDomainInfo) {
  await loadDomains();
  emits('success');
  // 打开 DNS 引导
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

/** 打开详情抽屉 */
function onOpenDetail(domain: TenantDomainInfo) {
  if (!currentTenant.value) return;
  detailDrawerRef.value?.open({
    domainId: domain.id,
    tenantId: currentTenant.value.tenantId,
  });
}

/** 详情更新成功回调 */
async function onDetailSuccess() {
  await loadDomains();
  emits('success');
}

/** 打开 DNS 引导 */
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

/** 打开 SSL 管理抽屉 */
function onOpenSslDrawer(domain: TenantDomainInfo) {
  if (!currentTenant.value) return;
  sslDrawerRef.value?.open({
    domainId: domain.id,
    tenantId: currentTenant.value.tenantId,
    domain: domain.domain,
  });
}

/** 设置主域名 */
async function onSetPrimary(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId || domain.isPrimary) return;

  try {
    await admin.setPrimaryDomainApi(currentTenant.value.tenantId, domain.id);
    message.success($t('admin.tenant.domain.setPrimarySuccess'));
    await loadDomains();
    emits('success');
  } catch (error) {
    console.error('Failed to set primary domain:', error);
  }
}

/** 验证域名 */
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
    await loadDomains();
    emits('success');
  } catch (error) {
    console.error('Failed to verify domain:', error);
  }
}

/** 删除域名 */
async function onDeleteDomain(domain: TenantDomainInfo) {
  if (!currentTenant.value?.tenantId) return;

  try {
    await admin.deleteTenantDomainApi(currentTenant.value.tenantId, domain.id);
    message.success($t('admin.tenant.domain.deleteSuccess'));
    await loadDomains();
    emits('success');
  } catch (error) {
    console.error('Failed to delete domain:', error);
  }
}

/** 获取验证状态标签配置 */
function getVerificationTagConfig(status: string) {
  switch (status) {
    case 'verified': {
      return { color: 'success', icon: 'lucide:check-circle', text: $t('admin.tenant.domain.verified') };
    }
    case 'failed': {
      return { color: 'error', icon: 'lucide:x-circle', text: $t('admin.tenant.domain.verifyFailed') };
    }
    default: {
      return { color: 'warning', icon: 'lucide:clock', text: $t('admin.tenant.domain.pending') };
    }
  }
}

/** 获取 SSL 状态标签配置 */
function getSslTagConfig(status: string) {
  switch (status) {
    case 'active': {
      return { color: 'success', icon: 'lucide:shield-check', text: $t('admin.tenant.domain.ssl.status.active') };
    }
    case 'expired': {
      return { color: 'error', icon: 'lucide:shield-off', text: $t('admin.tenant.domain.ssl.status.expired') };
    }
    case 'pending': {
      return { color: 'processing', icon: 'lucide:shield', text: $t('admin.tenant.domain.ssl.status.pending') };
    }
    default: {
      return { color: 'default', icon: 'lucide:shield-x', text: $t('admin.tenant.domain.ssl.status.none') };
    }
  }
}

/** 打开弹窗 */
function open(data: DomainModalData) {
  modalApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Modal :title="title" :loading="loading" class="w-[800px]">
    <div class="min-h-[400px]">
      <Spin :spinning="loading">
        <!-- 添加域名按钮 -->
        <div class="mb-4">
          <Button type="primary" @click="onOpenAddDrawer">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
            {{ $t('admin.tenant.domain.addDomain') }}
          </Button>
        </div>

        <!-- 域名卡片列表 -->
        <div class="flex flex-col gap-3">
          <div
            v-for="domain in domains"
            :key="domain.id"
            class="rounded-lg border border-gray-200 p-4 transition-all hover:border-primary hover:shadow-sm"
          >
            <!-- 域名信息头部 -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <IconifyIcon icon="lucide:globe" class="size-5 text-primary" />
                <span class="font-mono text-base font-medium">{{ domain.domain }}</span>
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
              <div class="flex items-center gap-1 text-sm text-gray-500">
                <span>{{ $t('admin.tenant.domain.type') }}:</span>
                <span>{{ domain.domainType === 'default' ? $t('admin.tenant.domain.defaultDomain') : $t('admin.tenant.domain.customDomain') }}</span>
              </div>

              <!-- 验证状态 -->
              <div class="flex items-center gap-1">
                <span class="text-sm text-gray-500">{{ $t('admin.tenant.domain.verificationStatus') }}:</span>
                <Tag :color="getVerificationTagConfig(domain.verificationStatus).color">
                  <IconifyIcon :icon="getVerificationTagConfig(domain.verificationStatus).icon" class="mr-1 size-3" />
                  {{ getVerificationTagConfig(domain.verificationStatus).text }}
                </Tag>
              </div>

              <!-- SSL 状态 (只显示自定义域名) -->
              <div v-if="domain.domainType === 'custom'" class="flex items-center gap-1">
                <span class="text-sm text-gray-500">SSL:</span>
                <Tag :color="getSslTagConfig(domain.sslStatus).color">
                  <IconifyIcon :icon="getSslTagConfig(domain.sslStatus).icon" class="mr-1 size-3" />
                  {{ getSslTagConfig(domain.sslStatus).text }}
                </Tag>
              </div>
            </div>

            <!-- 备注 -->
            <div v-if="domain.remark" class="mt-2 text-sm text-gray-500">
              <span class="font-medium">{{ $t('admin.tenant.domain.remark') }}:</span>
              <span class="ml-1">{{ domain.remark }}</span>
            </div>

            <!-- 操作按钮 -->
            <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
              <!-- 编辑域名 -->
              <Button type="link" size="small" @click="onOpenDetail(domain)">
                <IconifyIcon icon="lucide:pencil" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.editDomain') }}
              </Button>

              <!-- SSL 管理 (已验证的自定义域名才显示) -->
              <Button
                v-if="domain.verificationStatus === 'verified' && domain.domainType === 'custom'"
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
                :title="domain.verificationStatus !== 'verified' ? $t('admin.tenant.domain.verifyFirst') : ''"
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

              <!-- 删除 (自定义域名且非主域名才显示) -->
              <Popconfirm
                v-if="domain.domainType === 'custom' && !domain.isPrimary"
                :title="$t('admin.tenant.domain.confirmDelete', { domain: domain.domain })"
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
          class="flex flex-col items-center justify-center py-16 text-gray-400"
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
