<script lang="ts" setup>
/**
 * 租户域名管理弹窗
 * 管理租户的自定义域名
 */
import type { adminApi } from '#/api';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Form,
  FormItem,
  Input,
  message,
  Popconfirm,
  Spin,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';

type TenantDomainInfo = adminApi.TenantDomainInfo;

// Props
interface ModalData {
  tenantId: number;
  tenantName: string;
  tenantCode: string;
}

// Emits
const emits = defineEmits<{
  success: [];
}>();

// 状态
const domains = ref<TenantDomainInfo[]>([]);
const loading = ref(false);
const submitting = ref(false);
const currentTenant = ref<ModalData | null>(null);

// 表单状态
const newDomain = ref('');
const newRemark = ref('');

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
      const data = modalApi.getData<ModalData>();
      if (data?.tenantId) {
        currentTenant.value = data;
        await loadDomains();
      }
    } else {
      currentTenant.value = null;
      domains.value = [];
      newDomain.value = '';
      newRemark.value = '';
    }
  },
  footer: false,
});

/**
 * 加载域名列表
 */
async function loadDomains() {
  if (!currentTenant.value?.tenantId) return;

  loading.value = true;
  try {
    const result = await admin.getTenantDomainsApi(currentTenant.value.tenantId);
    domains.value = result.items;
  } catch (error) {
    console.error('Failed to load domains:', error);
  } finally {
    loading.value = false;
  }
}

/**
 * 添加域名
 */
async function onAddDomain() {
  if (!currentTenant.value?.tenantId || !newDomain.value.trim()) {
    message.warning($t('admin.tenant.domain.domainRequired'));
    return;
  }

  // 简单的域名格式验证
  const domainPattern = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$/i;
  if (!domainPattern.test(newDomain.value.trim())) {
    message.warning($t('admin.tenant.domain.domainInvalid'));
    return;
  }

  submitting.value = true;
  try {
    await admin.createTenantDomainApi(currentTenant.value.tenantId, {
      domain: newDomain.value.trim(),
      remark: newRemark.value.trim() || undefined,
    });
    message.success($t('admin.tenant.domain.createSuccess'));
    newDomain.value = '';
    newRemark.value = '';
    await loadDomains();
    emits('success');
  } catch (error) {
    console.error('Failed to add domain:', error);
  } finally {
    submitting.value = false;
  }
}

/**
 * 删除域名
 */
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

/**
 * 设置主域名
 */
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

/**
 * 验证域名
 */
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
    message.error($t('admin.tenant.domain.verifyFailed'));
  }
}

/**
 * 获取验证状态标签颜色
 */
function getVerificationColor(status: string): string {
  return status === 'verified' ? 'success' : 'warning';
}

/**
 * 获取 SSL 状态标签颜色
 */
function getSslColor(status: string): string {
  switch (status) {
    case 'active': {
      return 'success';
    }
    case 'pending': {
      return 'processing';
    }
    case 'failed': {
      return 'error';
    }
    default: {
      return 'default';
    }
  }
}

/**
 * 获取 SSL 状态显示文本
 */
function getSslText(status: string): string {
  switch (status) {
    case 'active': {
      return $t('admin.tenant.domain.sslActive');
    }
    case 'pending': {
      return $t('admin.tenant.domain.sslPending');
    }
    case 'failed': {
      return $t('admin.tenant.domain.sslFailed');
    }
    default: {
      return status;
    }
  }
}

/**
 * 表格列定义
 */
const columns = [
  {
    title: $t('admin.tenant.domain.domain'),
    dataIndex: 'domain',
    key: 'domain',
    width: 200,
  },
  {
    title: $t('admin.tenant.domain.type'),
    dataIndex: 'domainType',
    key: 'type',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('admin.tenant.domain.verified'),
    dataIndex: 'verificationStatus',
    key: 'verification',
    width: 100,
    align: 'center' as const,
  },
  {
    title: 'SSL',
    dataIndex: 'sslStatus',
    key: 'ssl',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('admin.common.operation'),
    key: 'action',
    width: 180,
    align: 'center' as const,
  },
];

/**
 * 类型转换 helper（解决 Table bodyCell slot 的 record 类型问题）
 */
function asDomain(record: unknown): TenantDomainInfo {
  return record as TenantDomainInfo;
}

/**
 * 打开弹窗
 */
function open(data: ModalData) {
  modalApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Modal :title="title" :loading="loading" class="w-[800px]">
    <div class="min-h-[400px]">
      <Spin :spinning="loading">
        <!-- 添加域名表单 -->
        <div class="mb-4 rounded-lg border border-dashed border-gray-300 p-4">
          <h4 class="mb-3 text-sm font-medium">
            {{ $t('admin.tenant.domain.addDomain') }}
          </h4>
          <Form layout="inline" class="flex flex-wrap gap-2">
            <FormItem class="mb-0 flex-1">
              <Input
                v-model:value="newDomain"
                :placeholder="$t('admin.tenant.domain.domainPlaceholder')"
                @press-enter="onAddDomain"
              />
            </FormItem>
            <FormItem class="mb-0 w-48">
              <Input
                v-model:value="newRemark"
                :placeholder="$t('admin.tenant.domain.remarkPlaceholder')"
              />
            </FormItem>
            <FormItem class="mb-0">
              <Button
                type="primary"
                :loading="submitting"
                @click="onAddDomain"
              >
                {{ $t('admin.tenant.domain.addDomain') }}
              </Button>
            </FormItem>
          </Form>
        </div>

        <!-- 域名列表 -->
        <Table
          :columns="columns"
          :data-source="domains"
          :pagination="false"
          :loading="loading"
          row-key="id"
          size="small"
        >
          <!-- 域名列 -->
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'domain'">
              <div class="flex items-center gap-2">
                <span class="font-mono">{{ record.domain }}</span>
                <Tag v-if="record.isPrimary" color="blue" class="!mr-0">
                  {{ $t('admin.tenant.domain.primaryDomain') }}
                </Tag>
              </div>
            </template>

            <!-- 类型列 -->
            <template v-else-if="column.key === 'type'">
              <Tag :color="record.domainType === 'default' ? 'default' : 'blue'">
                {{
                  record.domainType === 'default'
                    ? $t('admin.tenant.domain.defaultDomain')
                    : $t('admin.tenant.domain.customDomain')
                }}
              </Tag>
            </template>

            <!-- 验证状态列 -->
            <template v-else-if="column.key === 'verification'">
              <Tag :color="getVerificationColor(record.verificationStatus)">
                {{
                  record.verificationStatus === 'verified'
                    ? $t('admin.tenant.domain.verified')
                    : $t('admin.tenant.domain.pending')
                }}
              </Tag>
            </template>

            <!-- SSL 状态列 -->
            <template v-else-if="column.key === 'ssl'">
              <Tag :color="getSslColor(record.sslStatus)">
                {{ getSslText(record.sslStatus) }}
              </Tag>
            </template>

            <!-- 操作列 -->
            <template v-else-if="column.key === 'action'">
              <div class="flex items-center justify-center gap-1">
                <!-- 设为主域名 -->
                <Tooltip
                  v-if="!asDomain(record).isPrimary && asDomain(record).verificationStatus === 'verified'"
                  :title="$t('admin.tenant.domain.setPrimary')"
                >
                  <Button
                    type="link"
                    size="small"
                    @click="onSetPrimary(asDomain(record))"
                  >
                    <IconifyIcon icon="lucide:star" class="size-4" />
                  </Button>
                </Tooltip>

                <!-- 验证域名 -->
                <Tooltip
                  v-if="asDomain(record).verificationStatus === 'pending'"
                  :title="$t('admin.tenant.domain.verifyDomain')"
                >
                  <Button
                    type="link"
                    size="small"
                    @click="onVerifyDomain(asDomain(record))"
                  >
                    <IconifyIcon icon="lucide:check-circle" class="size-4" />
                  </Button>
                </Tooltip>

                <!-- 删除域名（仅自定义域名且非主域名可删除） -->
                <Popconfirm
                  v-if="asDomain(record).domainType === 'custom' && !asDomain(record).isPrimary"
                  :title="$t('admin.tenant.domain.confirmDelete', { domain: asDomain(record).domain })"
                  @confirm="onDeleteDomain(asDomain(record))"
                >
                  <Button type="link" size="small" danger>
                    <IconifyIcon icon="lucide:trash-2" class="size-4" />
                  </Button>
                </Popconfirm>
              </div>
            </template>
          </template>
        </Table>

        <!-- DNS 验证提示 -->
        <Alert
          v-if="domains.some((d) => d.verificationStatus === 'pending' && d.domainType === 'custom')"
          type="info"
          show-icon
          class="mt-4"
        >
          <template #message>
            <div class="text-sm">
              <p class="mb-1">{{ $t('admin.tenant.domain.dnsHint') }}</p>
              <code class="rounded bg-gray-100 px-2 py-1 text-xs">
                {{ currentTenant?.tenantCode }}.your-platform.com
              </code>
            </div>
          </template>
        </Alert>

        <!-- 空状态 -->
        <div
          v-if="!loading && domains.length === 0"
          class="flex flex-col items-center justify-center py-10 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:globe" class="mb-2 size-12 opacity-50" />
          <span>{{ $t('admin.tenant.domain.noDomains') }}</span>
        </div>
      </Spin>
    </div>
  </Modal>
</template>
