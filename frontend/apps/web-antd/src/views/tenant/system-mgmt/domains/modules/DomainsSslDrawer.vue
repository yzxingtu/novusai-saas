<script lang="ts" setup>
/**
 * 租户端 SSL 证书管理抽屉
 *
 * 功能：
 * - 查看证书状态和详情
 * - 平台证书：签发/续期/自动续期开关
 * - 自定义证书：上传（需套餐 allow_custom_ssl）/删除
 */
import type { SslCertificateInfo } from '#/api/tenant/domain';

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
  deleteTenantSslCertApi,
  getTenantSslDetailApi,
  provisionTenantSslApi,
  renewTenantSslApi,
  updateTenantSslAutoRenewApi,
  uploadTenantSslCertApi,
} from '#/api/tenant/domain';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

/** SSL 抽屉打开数据 */
interface SslDrawerData {
  domainId: number;
  domain: string;
  isDefault?: boolean;
}

/** 是否为默认域名（平台通配符 SSL 覆盖） */
const isDefaultDomain = computed(() => drawerData.value?.isDefault ?? false);

// 状态
const drawerData = ref<null | SslDrawerData>(null);
const loading = ref(false);
const actionLoading = ref(false);
const sslDetail = ref<null | SslCertificateInfo>(null);
const showUploadForm = ref(false);
const uploadForm = ref({ certificate: '', chain: '', privateKey: '' });

// 计算属性
const title = computed(() =>
  drawerData.value
    ? `${$t('tenant.system.domain.ssl.title')} - ${drawerData.value.domain}`
    : $t('tenant.system.domain.ssl.title'),
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
    sslDetail.value = await getTenantSslDetailApi(drawerData.value.domainId);
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
    await provisionTenantSslApi(drawerData.value.domainId);
    message.success($t('tenant.system.domain.ssl.provisionStarted'));
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
    await renewTenantSslApi(drawerData.value.domainId);
    message.success($t('tenant.system.domain.ssl.renewStarted'));
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
    const result = await updateTenantSslAutoRenewApi(
      drawerData.value.domainId,
      checked,
    );
    sslDetail.value = result;
    message.success($t('tenant.system.domain.ssl.autoRenewUpdated'));
  } catch {
  } finally {
    actionLoading.value = false;
  }
}

/** 上传自定义证书 */
async function onUpload() {
  if (!drawerData.value) return;
  if (!uploadForm.value.certificate || !uploadForm.value.privateKey) {
    message.warning($t('tenant.system.domain.ssl.uploadRequired'));
    return;
  }
  actionLoading.value = true;
  try {
    await uploadTenantSslCertApi(drawerData.value.domainId, {
      certificate: uploadForm.value.certificate,
      certificate_chain: uploadForm.value.chain || undefined,
      private_key: uploadForm.value.privateKey,
    });
    message.success($t('tenant.system.domain.ssl.uploadSuccess'));
    showUploadForm.value = false;
    uploadForm.value = { certificate: '', chain: '', privateKey: '' };
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
    title: $t('tenant.system.domain.ssl.deleteTitle'),
    content: $t('tenant.system.domain.ssl.deleteConfirm'),
    okType: 'danger',
    async onOk() {
      actionLoading.value = true;
      try {
        await deleteTenantSslCertApi(drawerData.value!.domainId);
        message.success($t('tenant.system.domain.ssl.deleteSuccess'));
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
      return { color: 'success', text: $t('tenant.system.domain.ssl.active') };
    }
    case 'expired': {
      return { color: 'error', text: $t('tenant.system.domain.ssl.expired') };
    }
    case 'failed': {
      return { color: 'error', text: $t('tenant.system.domain.ssl.failed') };
    }
    case 'pending': {
      return {
        color: 'processing',
        text: $t('tenant.system.domain.ssl.pending'),
      };
    }
    case 'provisioning': {
      return {
        color: 'processing',
        text: $t('tenant.system.domain.ssl.provisioning'),
      };
    }
    default: {
      return { color: 'default', text: $t('tenant.system.domain.ssl.none') };
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
            {{ $t('tenant.system.domain.sslStatus') }}
          </h4>
          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item :label="$t('common.status')">
              <Tag :color="getSslStatusConfig(sslDetail.status).color">
                {{ getSslStatusConfig(sslDetail.status).text }}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('tenant.system.domain.ssl.typeLabel')"
            >
              {{
                sslDetail.certType === 'platform'
                  ? $t('tenant.system.domain.ssl.typePlatform')
                  : $t('tenant.system.domain.ssl.typeCustom')
              }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.issuer"
              :label="$t('tenant.system.domain.ssl.issuer')"
            >
              {{ sslDetail.issuer }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.issuedAt"
              :label="$t('tenant.system.domain.ssl.issuedAt')"
            >
              {{ formatDate(sslDetail.issuedAt) }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.expiresAt"
              :label="$t('tenant.system.domain.ssl.expiresAt')"
            >
              {{ formatDate(sslDetail.expiresAt) }}
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.certType === 'platform'"
              :label="$t('tenant.system.domain.ssl.autoRenewLabel')"
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
                    ? $t('tenant.system.domain.ssl.autoRenewEnabled')
                    : $t('tenant.system.domain.ssl.autoRenewDisabled')
                }}
              </span>
            </Descriptions.Item>
            <Descriptions.Item
              v-if="sslDetail.renewalError"
              :label="$t('tenant.system.domain.ssl.renewalError')"
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
            v-if="
              sslDetail.certType === 'platform' && sslDetail.status === 'active'
            "
            type="primary"
            size="small"
            :loading="actionLoading"
            @click="onRenew"
          >
            <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-3" />
            {{ $t('tenant.system.domain.ssl.renew') }}
          </Button>
          <Button
            v-if="!sslDetail || sslDetail.status !== 'active'"
            type="primary"
            size="small"
            :loading="actionLoading"
            @click="onProvision"
          >
            <IconifyIcon icon="lucide:shield-check" class="mr-1 size-3" />
            {{ $t('tenant.system.domain.ssl.provision') }}
          </Button>
          <Button size="small" @click="showUploadForm = !showUploadForm">
            <IconifyIcon icon="lucide:upload" class="mr-1 size-3" />
            {{ $t('tenant.system.domain.ssl.upload') }}
          </Button>
          <Button
            danger
            size="small"
            :loading="actionLoading"
            @click="onDelete"
          >
            <IconifyIcon icon="lucide:trash-2" class="mr-1 size-3" />
            {{ $t('tenant.system.domain.ssl.deleteCert') }}
          </Button>
        </div>
      </template>

      <!-- 默认域名：平台通配符 SSL 覆盖 -->
      <template v-else-if="isDefaultDomain">
        <div
          class="flex flex-col items-center justify-center py-12 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:shield-check" class="mb-3 size-12 text-success" />
          <p class="mb-2 text-sm font-medium text-foreground">
            {{ $t('tenant.system.domain.ssl.platformWildcard') }}
          </p>
          <p class="text-xs">
            {{ $t('tenant.system.domain.ssl.platformWildcardDesc') }}
          </p>
        </div>
      </template>

      <!-- 无证书状态 -->
      <template v-else>
        <div
          class="flex flex-col items-center justify-center py-12 text-muted-foreground"
        >
          <IconifyIcon icon="lucide:shield-off" class="mb-3 size-12" />
          <p class="mb-4 text-sm">{{ $t('tenant.system.domain.ssl.none') }}</p>
          <div class="flex gap-2">
            <Button
              type="primary"
              size="small"
              :loading="actionLoading"
              @click="onProvision"
            >
              <IconifyIcon icon="lucide:shield-check" class="mr-1 size-3" />
              {{ $t('tenant.system.domain.ssl.provision') }}
            </Button>
            <Button size="small" @click="showUploadForm = !showUploadForm">
              <IconifyIcon icon="lucide:upload" class="mr-1 size-3" />
              {{ $t('tenant.system.domain.ssl.upload') }}
            </Button>
          </div>
        </div>
      </template>

      <!-- 上传自定义证书表单 -->
      <template v-if="showUploadForm">
        <Divider />
        <div>
          <h4 class="mb-3 text-sm font-medium">
            {{ $t('tenant.system.domain.ssl.upload') }}
          </h4>
          <div class="flex flex-col gap-3">
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('tenant.system.domain.ssl.certLabel') }}
              </label>
              <Textarea
                v-model:value="uploadForm.certificate"
                :rows="4"
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('tenant.system.domain.ssl.keyLabel') }}
              </label>
              <Textarea
                v-model:value="uploadForm.privateKey"
                :rows="4"
                placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium">
                {{ $t('tenant.system.domain.ssl.chainLabel') }}
                <span class="text-muted-foreground"
                  >({{ $t('common.optional') }})</span
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
                {{ $t('common.confirm') }}
              </Button>
              <Button size="small" @click="showUploadForm = false">
                {{ $t('common.cancel') }}
              </Button>
            </div>
          </div>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
