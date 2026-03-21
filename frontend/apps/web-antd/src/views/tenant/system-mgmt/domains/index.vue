<script lang="ts" setup>
import type { TenantDomainInfo } from './modules/domains-types';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Empty,
  message,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  deleteTenantDomainApi,
  getTenantDomainsApi,
  setPrimaryDomainApi,
  verifyTenantDomainApi,
} from '#/api/tenant/domain';
import {
  usePageAIContext,
  usePageAIOperations,
} from '#/composables/use-page-ai-registration';
import {
  createOpenRecordPageOperation,
  createPrefilledCreatePageOperation,
  createRefreshPageOperation,
  createRecordActionPageOperation,
} from '#/composables/use-page-ai-operation-helpers';
import { $t } from '#/locales';
import { copyToClipboard, formatDate } from '#/utils/common';

import {
  getDomainTypeConfig,
  getSslStatusConfig,
  getVerificationStatusConfig,
} from './data';
import type { DnsGuideData } from './modules/domains-types';
import DomainsAddDrawer from './modules/DomainsAddDrawer.vue';
import DomainsDetailDrawer from './modules/DomainsDetailDrawer.vue';
import DomainsDnsGuideModal from './modules/DomainsDnsGuideModal.vue';
import DomainsSslDrawer from './modules/DomainsSslDrawer.vue';

defineOptions({ name: 'TenantDomains' });

const t = (key: string) => $t(`tenant.system.domain.${key}`);
const AI_PAGE_KEY = 'tenant.system.domains';

// State / 状态
const domains = ref<TenantDomainInfo[]>([]);
const loading = ref(false);
const refreshing = ref(false);
const verifiedDomainCount = computed(
  () => domains.value.filter((domain) => domain.verificationStatus === 'verified').length,
);
const pendingDomainCount = computed(
  () => domains.value.filter((domain) => domain.verificationStatus === 'pending').length,
);
const primaryDomainId = computed(
  () => domains.value.find((domain) => domain.isPrimary)?.id ?? null,
);

// Refs / 引用
const addDrawerRef = ref<InstanceType<typeof DomainsAddDrawer>>();
const detailDrawerRef = ref<InstanceType<typeof DomainsDetailDrawer>>();
const dnsGuideModalRef = ref<InstanceType<typeof DomainsDnsGuideModal>>();
const sslDrawerRef = ref<InstanceType<typeof DomainsSslDrawer>>();

function onOpenSsl(domain: TenantDomainInfo) {
  openSslDrawer(domain);
}

// Lifecycle / 生命周期
onMounted(() => {
  loadDomains();
});

// Actions / 操作
async function loadDomains() {
  loading.value = true;
  try {
    const result = await getTenantDomainsApi();
    domains.value = result.items;
  } catch {
  } finally {
    loading.value = false;
  }
}

async function onRefresh() {
  refreshing.value = true;
  try {
    const result = await getTenantDomainsApi();
    domains.value = result.items;
  } finally {
    refreshing.value = false;
  }
}

function onOpenAddDrawer() {
  openAddDrawer();
}

async function onAddSuccess(newDomain: TenantDomainInfo) {
  await loadDomains();
  if (newDomain.verificationStatus === 'pending') {
    onOpenDnsGuide(newDomain);
  }
}

function onOpenDetail(domain: TenantDomainInfo) {
  openDetailDrawer(domain);
}

function openDetailDrawer(domain: TenantDomainInfo) {
  detailDrawerRef.value?.open({
    domainId: domain.id,
  });
}

async function onDetailSuccess() {
  await loadDomains();
}

function onOpenDnsGuide(domain: TenantDomainInfo) {
  openDnsGuideModal(domain);
}

function findDomainById(domainId: number): null | TenantDomainInfo {
  return domains.value.find((domain) => domain.id === domainId) ?? null;
}

function buildDnsGuideData(domain: TenantDomainInfo): DnsGuideData {
  return {
    domain: domain.domain,
    domainId: domain.id,
    verificationInfo: domain.verificationInfo,
    verificationToken: domain.verificationToken,
    cnameTarget: domain.cnameTarget,
  };
}

function openAddDrawer(defaults?: { domain?: string; remark?: string }) {
  addDrawerRef.value?.open(defaults);
}

function openDnsGuideModal(domain: TenantDomainInfo) {
  dnsGuideModalRef.value?.open(buildDnsGuideData(domain));
}

function openSslDrawer(domain: TenantDomainInfo) {
  sslDrawerRef.value?.open({
    domainId: domain.id,
    domain: domain.domain,
    isDefault: domain.domainType === 'default',
  });
}

async function onSetPrimary(domain: TenantDomainInfo) {
  if (domain.isPrimary) return;
  if (domain.verificationStatus !== 'verified') {
    message.warning(t('messages.verifyFirst'));
    return;
  }
  try {
    await setPrimaryDomainApi(domain.id);
    message.success(t('messages.setPrimarySuccess'));
    await loadDomains();
  } catch {}
}

async function onVerifyDomain(domain: TenantDomainInfo) {
  try {
    const result = await verifyTenantDomainApi(domain.id);
    if (result.verificationStatus === 'verified') {
      message.success(t('messages.verifySuccess'));
    } else if (result.verificationStatus === 'failed') {
      message.error(t('messages.verifyFailed'));
    } else {
      message.warning(t('messages.verifyPending'));
    }
    await loadDomains();
  } catch {}
}

async function onDeleteDomain(domain: TenantDomainInfo) {
  if (domain.domainType === 'default') {
    message.warning(t('messages.cannotDeleteDefault'));
    return;
  }
  if (domain.isPrimary) {
    message.warning(t('messages.cannotDeletePrimary'));
    return;
  }
  try {
    await deleteTenantDomainApi(domain.id);
    message.success(t('messages.deleteSuccess'));
    await loadDomains();
  } catch {}
}

function onCopy(text: string) {
  copyToClipboard(text);
  message.success($t('common.copied'));
}

usePageAIContext({
  pageKey: AI_PAGE_KEY,
  resource: '/tenant/domains',
  data: () => ({
    total: domains.value.length,
    pending_count: pendingDomainCount.value,
    primary_domain_id: primaryDomainId.value,
    verified_count: verifiedDomainCount.value,
  }),
});

usePageAIOperations({
  pageKey: AI_PAGE_KEY,
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      action: onRefresh,
      description: 'Reload the domain list',
    }),
    createPrefilledCreatePageOperation({
      name: 'create_domain',
      label: t('add'),
      description:
        'Open the add-domain drawer and optionally prefill domain or remark / 打开新增域名抽屉，并可预填域名或备注',
      params: {
        domain: {
          type: 'string',
          description: 'Domain name to prefill / 预填的域名',
        },
        remark: {
          type: 'string',
          description: 'Remark to prefill / 预填的备注',
        },
      },
      normalizeParams: (params) => ({
        ...(String(params.domain ?? '').trim()
          ? { domain: String(params.domain).trim() }
          : {}),
        ...(String(params.remark ?? '').trim()
          ? { remark: String(params.remark).trim() }
          : {}),
      }),
      openCreate: async (params) => {
        openAddDrawer(params);
      },
    }),
    createOpenRecordPageOperation({
      name: 'open_domain_detail',
      label: t('edit'),
      description:
        'Open the domain detail drawer by domain ID / 按域名 ID 打开域名详情抽屉',
      params: {
        id: {
          type: 'number',
          description: 'Domain ID / 域名 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findDomainById(params.id),
      resolveRecordId: (params) => params.id,
      open: async (domain) => {
        openDetailDrawer(domain);
      },
    }),
    createOpenRecordPageOperation({
      name: 'open_dns_guide',
      label: t('dnsGuide'),
      description:
        'Open the DNS guide modal for a domain by ID / 按域名 ID 打开 DNS 配置引导弹窗',
      params: {
        id: {
          type: 'number',
          description: 'Domain ID / 域名 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findDomainById(params.id),
      resolveRecordId: (params) => params.id,
      open: async (domain) => {
        openDnsGuideModal(domain);
      },
    }),
    createOpenRecordPageOperation({
      name: 'open_ssl_config',
      label: $t('tenant.system.domain.ssl.title'),
      description:
        'Open the SSL settings drawer for a domain by ID / 按域名 ID 打开 SSL 设置抽屉',
      params: {
        id: {
          type: 'number',
          description: 'Domain ID / 域名 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findDomainById(params.id),
      resolveRecordId: (params) => params.id,
      open: async (domain) => {
        openSslDrawer(domain);
      },
    }),
    createRecordActionPageOperation({
      name: 'verify_domain',
      label: t('verify'),
      description:
        'Verify a domain by ID / 按域名 ID 触发域名校验',
      params: {
        id: {
          type: 'number',
          description: 'Domain ID / 域名 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findDomainById(params.id),
      resolveRecordId: (params) => params.id,
      action: async (domain) => {
        await onVerifyDomain(domain);
      },
    }),
    createRecordActionPageOperation({
      name: 'set_primary_domain',
      label: t('setPrimary'),
      description:
        'Set a verified domain as primary by ID / 按域名 ID 设为主域名',
      params: {
        id: {
          type: 'number',
          description: 'Domain ID / 域名 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findDomainById(params.id),
      resolveRecordId: (params) => params.id,
      action: async (domain) => {
        await onSetPrimary(domain);
      },
    }),
  ],
});
</script>

<template>
  <Page auto-content-height>
    <template #extra>
      <Space>
        <Button
          v-access:code="['tenant_domain:create']"
          type="primary"
          @click="onOpenAddDrawer"
        >
          <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
          {{ t('add') }}
        </Button>
        <Button :loading="refreshing" @click="onRefresh">
          <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
          {{ $t('common.refresh') }}
        </Button>
      </Space>
    </template>

    <Spin :spinning="loading">
      <!-- Empty State -->
      <div
        v-if="!loading && domains.length === 0"
        class="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-8"
      >
        <Empty :description="t('noDomains')" />
        <Button type="primary" class="mt-4" @click="onOpenAddDrawer">
          {{ t('add') }}
        </Button>
      </div>

      <!-- Domain List (Grid Layout) -->
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card
          v-for="domain in domains"
          :key="domain.id"
          class="group relative flex h-full flex-col overflow-hidden border-border transition-all hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg"
          :body-style="{
            padding: '24px',
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
          }"
        >
          <!-- Top: Domain Name & Tags -->
          <div class="mb-5">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="mb-3 flex items-center gap-2">
                  <span
                    class="truncate text-xl font-bold text-foreground"
                    :title="domain.domain"
                  >
                    {{ domain.domain }}
                  </span>
                  <Tooltip
                    v-if="domain.isPrimary"
                    :title="$t('common.primary')"
                  >
                    <div
                      class="flex items-center justify-center rounded-full bg-amber-100 p-1 dark:bg-amber-900/30"
                    >
                      <IconifyIcon
                        icon="lucide:star"
                        class="size-3.5 fill-amber-500 text-amber-500"
                      />
                    </div>
                  </Tooltip>
                </div>
                <!-- Tags -->
                <div class="flex flex-wrap gap-2">
                  <Tag
                    v-if="domain.isPrimary"
                    color="blue"
                    class="mr-0 border-none px-2.5 py-0.5 text-xs font-medium"
                  >
                    {{ $t('common.primary') }}
                  </Tag>
                  <Tag
                    :color="getDomainTypeConfig(domain.domainType).color"
                    class="mr-0 border-none px-2.5 py-0.5 text-xs font-medium"
                  >
                    {{ getDomainTypeConfig(domain.domainType).text }}
                  </Tag>

                  <Tag
                    :color="
                      getVerificationStatusConfig(domain.verificationStatus)
                        .color
                    "
                    class="mr-0 px-2.5 py-0.5 text-xs font-medium"
                  >
                    {{
                      getVerificationStatusConfig(domain.verificationStatus)
                        .text
                    }}
                  </Tag>
                </div>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <div class="mb-5 border-t border-dashed border-border/60"></div>

          <!-- Middle: Details -->
          <div class="flex-1 space-y-4 text-sm">
            <!-- CNAME -->
            <div
              v-if="domain.cnameTarget"
              class="group/item flex items-center justify-between gap-4"
            >
              <div class="flex items-center text-muted-foreground">
                <IconifyIcon
                  icon="lucide:globe"
                  class="mr-2 size-4 opacity-70"
                />
                <span>CNAME</span>
              </div>
              <div class="flex min-w-0 items-center gap-2">
                <div
                  class="max-w-[200px] cursor-pointer truncate rounded bg-muted/50 px-2 py-0.5 font-mono text-xs text-foreground transition-colors hover:text-primary"
                  @click="onCopy(domain.cnameTarget)"
                  :title="domain.cnameTarget"
                >
                  {{ domain.cnameTarget }}
                </div>
                <IconifyIcon
                  icon="lucide:copy"
                  class="size-3.5 cursor-pointer text-muted-foreground hover:text-primary"
                  @click="onCopy(domain.cnameTarget!)"
                />
              </div>
            </div>

            <!-- SSL -->
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center text-muted-foreground">
                <IconifyIcon
                  icon="lucide:shield-check"
                  class="mr-2 size-4 opacity-70"
                />
                <span>SSL</span>
              </div>
              <div class="flex items-center gap-2">
                <Badge
                  :status="getSslStatusConfig(domain.sslStatus).status"
                  :text="getSslStatusConfig(domain.sslStatus).text"
                />
                <Button
                  type="link"
                  size="small"
                  class="!p-0"
                  @click="onOpenSsl(domain)"
                >
                  <IconifyIcon icon="lucide:settings" class="size-3" />
                </Button>
              </div>
            </div>

            <!-- Created At -->
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center text-muted-foreground">
                <IconifyIcon
                  icon="lucide:clock"
                  class="mr-2 size-4 opacity-70"
                />
                <span>{{ $t('common.createdAt') }}</span>
              </div>
              <span class="font-mono text-xs text-foreground/80">{{
                formatDate(domain.createdAt)
              }}</span>
            </div>

            <!-- Remark -->
            <div
              v-if="domain.remark"
              class="mt-4 rounded-lg bg-muted/30 p-3 text-xs"
            >
              <div class="flex gap-2">
                <IconifyIcon
                  icon="lucide:quote"
                  class="mt-0.5 size-3 shrink-0 text-muted-foreground/50"
                />
                <p class="line-clamp-2 leading-relaxed text-muted-foreground">
                  {{ domain.remark }}
                </p>
              </div>
            </div>
          </div>

          <!-- Bottom: Actions -->
          <div class="mt-6 flex items-center justify-end gap-3 pt-4">
            <!-- DNS Guide -->
            <Button
              v-if="domain.verificationStatus !== 'verified'"
              size="small"
              class="rounded-md"
              @click="onOpenDnsGuide(domain)"
            >
              {{ t('dnsGuide') }}
            </Button>

            <!-- Verify -->
            <template v-if="domain.verificationStatus === 'pending'">
              <Button
                v-access:code="['tenant_domain:verify']"
                size="small"
                type="primary"
                ghost
                class="rounded-md"
                @click="onVerifyDomain(domain)"
              >
                {{ t('verify') }}
              </Button>
            </template>

            <!-- Set Primary -->
            <template v-else>
              <Tooltip
                v-if="!domain.isPrimary"
                :title="
                  domain.verificationStatus !== 'verified'
                    ? t('messages.verifyFirst')
                    : ''
                "
              >
                <Button
                  v-access:code="['tenant_domain:update']"
                  size="small"
                  class="rounded-md"
                  :disabled="domain.verificationStatus !== 'verified'"
                  @click="onSetPrimary(domain)"
                >
                  <IconifyIcon icon="lucide:star" class="mr-1 size-4" />
                  {{ t('setPrimary') }}
                </Button>
              </Tooltip>
            </template>

            <!-- Edit -->
            <Button
              size="small"
              class="rounded-md"
              @click="onOpenDetail(domain)"
            >
              {{ t('edit') }}
            </Button>

            <!-- Delete -->
            <Popconfirm
              v-if="domain.domainType === 'custom' && !domain.isPrimary"
              :title="
                $t('tenant.system.domain.messages.confirmDelete', {
                  domain: domain.domain,
                })
              "
              @confirm="onDeleteDomain(domain)"
            >
              <Button
                v-access:code="['tenant_domain:delete']"
                size="small"
                danger
                type="text"
                class="!px-2"
              >
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
              </Button>
            </Popconfirm>
          </div>
        </Card>
      </div>
    </Spin>

    <DomainsAddDrawer ref="addDrawerRef" @success="onAddSuccess" />
    <DomainsDetailDrawer ref="detailDrawerRef" @success="onDetailSuccess" />
    <DomainsDnsGuideModal ref="dnsGuideModalRef" @success="loadDomains" />
    <DomainsSslDrawer ref="sslDrawerRef" />
  </Page>
</template>
