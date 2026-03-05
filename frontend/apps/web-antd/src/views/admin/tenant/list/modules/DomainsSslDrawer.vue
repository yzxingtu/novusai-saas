<script lang="ts" setup>
/**
 * SSL 证书管理抽屉
 *
 * 功能：
 * - 查看证书状态和详情
 * - 平台证书：签发/续期/自动续期开关
 * - 自定义证书：上传/删除
 * - 强制替换（platform 或 custom）
 */
import type { SslCertificateInfo } from '#/api/admin/tenant-domain';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  Divider,
  message,
  Modal,
  Spin,
  Switch,
  Tag,
  Textarea,
} from 'ant-design-vue';

import {
  deleteSslCertApi,
  getSslDetailApi,
  provisionSslApi,
  renewSslApi,
  updateSslAutoRenewApi,
  uploadSslCertApi,
} from '#/api/admin/tenant-domain';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

/** SSL 抽屉打开数据 */
interface SslDrawerData {
  domainId: number;
  tenantId: number;
  domain: string;
}

// 状态
const drawerData = ref<null | SslDrawerData>(null);
const loading = ref(false);
const actionLoading = ref(false);
const sslDetail = ref<null | SslCertificateInfo>(null);
const showUploadForm = ref(false);
const uploadForm = ref({ certificate: '', privateKey: '', chain: '' });

// 计算属性
const title = computed(() =>
  drawerData.value
    ? `${$t('admin.tenant.domain.ssl.title')} - ${drawerData.value.domain}`
    : $t('admin.tenant.domain.ssl.title'),
);

// Drawer
const [Drawer, drawerApi] = useVbenDrawer({
  async onOpenChange(isOpen) {
    if (isOpen) {
      const data = drawerApi.getData<SslDrawerData>();
      if (data) {
        drawerData.value = data;
        await loadSslDetail();
      }
    } else {
      drawerData.value = null;
      sslDetail.value = null;
      showUploadForm.value = false;
    }
  },
  footer: false,
});

/** 加载 SSL 详情 */
async function loadSslDetail() {
  if (!drawerData.value) return;
  loading.value = true;
  try {
    sslDetail.value = await getSslDetailApi(
      drawerData.value.tenantId,
      drawerData.value.domainId,
    );
  } catch {
    sslDetail.value = null;
  } finally {
    loading.value = false;
  }
}

/** 签发平台证书 */
async function onProvision() {
  if (!drawerData.value) return;
  actionLoading.value = true;
  try {
    await provisionSslApi(drawerData.value.tenantId, drawerData.value.domainId);
    message.success($t('admin.tenant.domain.ssl.provisionStarted'));
    await loadSslDetail();
  } catch {
  } finally {
    actionLoading.value = false;
  }
}

/** 续期平台证书 */
async function onRenew() {
  if (!drawerData.value) return;
  actionLoading.value = true;
  try {
    await renewSslApi(drawerData.value.tenantId, drawerData.value.domainId);
    message.success($t('admin.tenant.domain.ssl.renewStarted'));
    await loadSslDetail();
  } catch {
  } finally {
    actionLoading.value = false;
  }
}

/** 切换自动续期 */
async function onToggleAutoRenew(checked: boolean) {
  if (!drawerData.value) return;
  actionLoading.value = true;
  try {
    const result = await updateSslAutoRenewApi(
      drawerData.value.tenantId,
      drawerData.value.domainId,
      checked,
    );
    sslDetail.value = result;
    message.success($t('admin.tenant.domain.ssl.autoRenewUpdated'));
  } catch {
  } finally {
    actionLoading.value = false;
  }
}

/** 上传自定义证书 */
async function onUpload() {
  if (!drawerData.value) return;
  if (!uploadForm.value.certificate || !uploadForm.value.privateKey) {
    message.warning($t('admin.tenant.domain.ssl.uploadRequired'));
    return;
  }
  actionLoading.value = true;
  try {
    await uploadSslCertApi(
      drawerData.value.tenantId,
      drawerData.value.domainId,
      {
        certificate: uploadForm.value.certificate,
        private_key: uploadForm.value.privateKey,
        certificate_chain: uploadForm.value.chain || undefined,
      },
    );
    message.success($t('admin.tenant.domain.ssl.uploadSuccess'));
    showUploadForm.value = false;
    uploadForm.value = { certificate: '', privateKey: '', chain: '' };
    await loadSslDetail();
  } catch {
  } finally {
    actionLoading.value = false;
  }
}

/** 删除证书 */
async function onDelete() {
  if (!drawerData.value) return;
  Modal.confirm({
    title: $t('admin.tenant.domain.ssl.actions.delete'),
    content: $t('admin.tenant.domain.ssl.deleteConfirm'),
    okType: 'danger',
    async onOk() {
      actionLoading.value = true;
      try {
        await deleteSslCertApi(
          drawerData.value!.tenantId,
          drawerData.value!.domainId,
        );
        message.success($t('admin.tenant.domain.ssl.deleteSuccess'));
        sslDetail.value = null;
        await loadSslDetail();
      } catch {
      } finally {
        actionLoading.value = false;
      }
    },
  });
}

/** 获取 SSL 状态标签配置 */
function getSslStatusConfig(status?: string) {
  switch (status) {
    case 'active': {
      return {
        color: 'success',
        text: $t('admin.tenant.domain.ssl.status.active'),
      };
    }
    case 'expired': {
      return {
        color: 'error',
        text: $t('admin.tenant.domain.ssl.status.expired'),
      };
    }
    case 'failed': {
      return {
        color: 'error',
        text: $t('admin.tenant.domain.ssl.status.failed'),
      };
    }
    case 'pending': {
      return {
        color: 'processing',
        text: $t('admin.tenant.domain.ssl.status.pending'),
      };
    }
    case 'provisioning': {
      return {
        color: 'processing',
        text: $t('admin.tenant.domain.ssl.status.provisioning'),
      };
    }
    case 'revoked': {
      return {
        color: 'warning',
        text: $t('admin.tenant.domain.ssl.status.revoked'),
      };
    }
    default: {
      return {
        color: 'default',
        text: $t('admin.tenant.domain.ssl.status.none'),
      };
    }
  }
}

/** 打开抽屉 */
function open(data: SslDrawerData) {
  drawerApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Drawer :title="title" class="w-[550px]">
    <Spin :spinning="loading">
      <template v-if="sslDetail">
        <!-- 证书详情 -->
        <div class="mb-4">
          <h4 class="mb-3 text-sm font-medium">
            {{ $t('admin.tenant.domain.ssl.currentStatus') }}
          </h4>
          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item :label="$t('shared.common.status')">
              <Tag :color="getSslStatusConfig(sslDetail.status).color">
                {{ getSslStatusConfig(sslDetail.status).text }}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('admin.tenant.domain.ssl.type.label')"
            >
              {{
                sslDetail.certType === 'platform'
                  ? $t('admin.tenant.domain.ssl.type.platform')
                  : $t('admin.tenant.domain.ssl.type.custom')
              }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.issuer"
              :label="$t('admin.tenant.domain.ssl.info.issuer')"
            >
              {{ sslDetail.issuer }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.issuedAt"
              :label="$t('admin.tenant.domain.ssl.info.validFrom')"
            >
              {{ formatDate(sslDetail.issuedAt) }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.expiresAt"
              :label="$t('admin.tenant.domain.ssl.info.validTo')"
            >
              {{ formatDate(sslDetail.expiresAt) }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.certType === 'platform'"
              :label="$t('admin.tenant.domain.ssl.autoRenew.label')"
            >
              <Switch
                :checked="sslDetail.autoRenew"
                :loading="actionLoading"
                size="small"
                @change="
                  (val: boolean | string | number) => onToggleAutoRenew(!!val)
                "
              />
              <span class="ml-2 text-xs text-muted-foreground">
                {{
                  sslDetail.autoRenew
                    ? $t('admin.tenant.domain.ssl.autoRenew.enabled')
                    : $t('admin.tenant.domain.ssl.autoRenew.disabled')
                }}
              </span>
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.renewalError"
              :label="$t('admin.tenant.domain.ssl.renewalError')"
            >
              <span class="text-xs text-destructive">{{
                sslDetail.renewalError
              }}</span>
            </Descriptions.Item>
          </Descriptions>
        </div>

        <!-- 操作按钮 -->
        <div class="mb-4 flex flex-wrap gap-2">
          <Button
            v-if="sslDetail.certType === 'platform'"
            type="primary"
            size="small"
            :loading="actionLoading"
            @click="onRenew"
          >
            <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-3" />
            {{ $t('admin.tenant.domain.ssl.actions.renew') }}
          </Button>
          <Button
            v-if="!sslDetail || sslDetail.status !== 'active'"
            type="primary"
            size="small"
            :loading="actionLoading"
            @click="onProvision"
          >
            <IconifyIcon icon="lucide:shield-check" class="mr-1 size-3" />
            {{ $t('admin.tenant.domain.ssl.actions.provision') }}
          </Button>
          <Button size="small" @click="showUploadForm = !showUploadForm">
            <IconifyIcon icon="lucide:upload" class="mr-1 size-3" />
            {{ $t('admin.tenant.domain.ssl.actions.upload') }}
          </Button>
          <Button
            danger
            size="small"
            :loading="actionLoading"
            @click="onDelete"
          >
            <IconifyIcon icon="lucide:trash-2" class="mr-1 size-3" />
            {{ $t('admin.tenant.domain.ssl.actions.delete') }}
          </Button>
        </div>
      </template>

      <!-- 无证书状态 -->
      <template v-else>
        <div
          class="flex flex-col items-center justify-center py-12 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:shield-off" class="mb-3 size-12" />
          <p class="mb-4 text-sm">
            {{ $t('admin.tenant.domain.ssl.status.none') }}
          </p>
          <div class="flex gap-2">
            <Button
              type="primary"
              size="small"
              :loading="actionLoading"
              @click="onProvision"
            >
              <IconifyIcon icon="lucide:shield-check" class="mr-1 size-3" />
              {{ $t('admin.tenant.domain.ssl.actions.provision') }}
            </Button>
            <Button size="small" @click="showUploadForm = !showUploadForm">
              <IconifyIcon icon="lucide:upload" class="mr-1 size-3" />
              {{ $t('admin.tenant.domain.ssl.actions.upload') }}
            </Button>
          </div>
        </div>
      </template>

      <!-- 上传自定义证书表单 -->
      <template v-if="showUploadForm">
        <Divider />
        <div>
          <h4 class="mb-3 text-sm font-medium">
            {{ $t('admin.tenant.domain.ssl.actions.upload') }}
          </h4>
          <div class="flex flex-col gap-3">
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('admin.tenant.domain.ssl.certificate.publicKey') }}
              </label>
              <Textarea
                v-model:value="uploadForm.certificate"
                :rows="4"
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('admin.tenant.domain.ssl.certificate.privateKey') }}
              </label>
              <Textarea
                v-model:value="uploadForm.privateKey"
                :rows="4"
                placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('admin.tenant.domain.ssl.certificate.chain') }}
                <span class="text-muted-foreground"
                  >({{ $t('shared.common.optional') }})</span
                >
              </label>
              <Textarea
                v-model:value="uploadForm.chain"
                :rows="3"
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              />
            </div>
            <div class="flex gap-2">
              <Button
                type="primary"
                size="small"
                :loading="actionLoading"
                @click="onUpload"
              >
                {{ $t('shared.common.confirm') }}
              </Button>
              <Button size="small" @click="showUploadForm = false">
                {{ $t('shared.common.cancel') }}
              </Button>
            </div>
          </div>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
