<script lang="ts" setup>
/**
 * SSL 证书管理抽屉 (预留)
 * 
 * 功能规划：
 * - 平台自动签发模式：开启/关闭自动续期，复制证书内容
 * - 自定义证书模式：上传/编辑/删除证书
 * 
 * API 待后端实现：
 * - GET /admin/tenants/{tenant_id}/domains/{domain_id}/ssl - 获取证书详情
 * - POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/upload - 上传证书
 * - DELETE /admin/tenants/{tenant_id}/domains/{domain_id}/ssl - 删除证书
 * - POST /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/auto-renew - 开启自动续期
 * - DELETE /admin/tenants/{tenant_id}/domains/{domain_id}/ssl/auto-renew - 关闭自动续期
 */
import type { SslDetailResponse, SslType } from './domains-types';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Descriptions,
  Divider,
  message,
  Radio,
  RadioGroup,
  Spin,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

/** SSL 抽屉打开数据 */
interface SslDrawerData {
  domainId: number;
  tenantId: number;
  domain: string;
}

// 状态
const drawerData = ref<SslDrawerData | null>(null);
const loading = ref(false);
const sslDetail = ref<SslDetailResponse | null>(null);
const selectedType = ref<SslType>('platform');

// 计算属性
const title = computed(() =>
  drawerData.value
    ? `${$t('admin.tenant.domain.ssl.title')} - ${drawerData.value.domain}`
    : $t('admin.tenant.domain.ssl.title'),
);

const isPlatformMode = computed(() => sslDetail.value?.type === 'platform');
const isCustomMode = computed(() => sslDetail.value?.type === 'custom');
const hasActiveCert = computed(() => sslDetail.value?.status === 'active');

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
    }
  },
  footer: false,
});

/** 加载 SSL 详情 (预留) */
async function loadSslDetail() {
  if (!drawerData.value) return;

  loading.value = true;
  try {
    // TODO: 调用后端 API
    // const result = await admin.getSslDetailApi(
    //   drawerData.value.tenantId,
    //   drawerData.value.domainId,
    // );
    // sslDetail.value = result;

    // 模拟数据 (开发阶段)
    sslDetail.value = {
      status: 'none',
      type: 'platform',
      autoRenew: false,
    };
    selectedType.value = sslDetail.value.type;
  } catch (error) {
    console.error('Failed to load SSL detail:', error);
  } finally {
    loading.value = false;
  }
}

/** 复制证书内容 */
function onCopyCert(content?: string) {
  if (content) {
    copyToClipboard(content);
    message.success($t('admin.tenant.domain.ssl.certificate.copySuccess'));
  }
}

/** 开启自动续期 (预留) */
async function onEnableAutoRenew() {
  message.info($t('shared.common.featureComingSoon'));
  // TODO: 调用后端 API
  // await admin.enableSslAutoRenewApi(drawerData.value.tenantId, drawerData.value.domainId);
}

/** 关闭自动续期 (预留) */
async function onDisableAutoRenew() {
  message.info($t('shared.common.featureComingSoon'));
  // TODO: 调用后端 API
  // await admin.disableSslAutoRenewApi(drawerData.value.tenantId, drawerData.value.domainId);
}

/** 上传证书 (预留) */
async function onUploadCert() {
  message.info($t('shared.common.featureComingSoon'));
  // TODO: 实现证书上传
}

/** 删除证书 (预留) */
async function onDeleteCert() {
  message.info($t('shared.common.featureComingSoon'));
  // TODO: 调用后端 API
  // await admin.deleteSslCertApi(drawerData.value.tenantId, drawerData.value.domainId);
}

/** 获取 SSL 状态标签配置 */
function getSslStatusConfig(status?: string) {
  switch (status) {
    case 'active': {
      return { color: 'success', text: $t('admin.tenant.domain.ssl.status.active') };
    }
    case 'expired': {
      return { color: 'error', text: $t('admin.tenant.domain.ssl.status.expired') };
    }
    case 'pending': {
      return { color: 'processing', text: $t('admin.tenant.domain.ssl.status.pending') };
    }
    default: {
      return { color: 'default', text: $t('admin.tenant.domain.ssl.status.none') };
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
      <!-- API 未就绪提示 -->
      <Alert
        message="功能开发中"
        description="SSL 证书管理功能正在开发中，API 接口待后端实现。"
        type="warning"
        show-icon
        class="mb-4"
      />

      <template v-if="sslDetail">
        <!-- 当前证书状态 -->
        <div class="mb-4">
          <h4 class="mb-3 text-sm font-medium">{{ $t('admin.tenant.domain.ssl.currentStatus') }}</h4>
          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item :label="$t('shared.common.status')">
              <Tag :color="getSslStatusConfig(sslDetail.status).color">
                {{ getSslStatusConfig(sslDetail.status).text }}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item :label="$t('admin.tenant.domain.ssl.type.label')">
              {{ sslDetail.type === 'platform' ? $t('admin.tenant.domain.ssl.type.platform') : $t('admin.tenant.domain.ssl.type.custom') }}
            </Descriptions.Item>
            <Descriptions.Item v-if="sslDetail.issuer" :label="$t('admin.tenant.domain.ssl.info.issuer')">
              {{ sslDetail.issuer }}
            </Descriptions.Item>
            <Descriptions.Item v-if="sslDetail.validFrom" :label="$t('admin.tenant.domain.ssl.info.validFrom')">
              {{ sslDetail.validFrom }}
            </Descriptions.Item>
            <Descriptions.Item v-if="sslDetail.validTo" :label="$t('admin.tenant.domain.ssl.info.validTo')">
              {{ sslDetail.validTo }}
            </Descriptions.Item>
            <Descriptions.Item v-if="isPlatformMode" :label="$t('admin.tenant.domain.ssl.autoRenew.label')">
              <Tag :color="sslDetail.autoRenew ? 'success' : 'default'">
                {{ sslDetail.autoRenew ? $t('admin.tenant.domain.ssl.autoRenew.enabled') : $t('admin.tenant.domain.ssl.autoRenew.disabled') }}
              </Tag>
              <span v-if="sslDetail.nextRenewAt" class="ml-2 text-xs text-gray-400">
                {{ $t('admin.tenant.domain.ssl.autoRenew.nextRenew') }}: {{ sslDetail.nextRenewAt }}
              </span>
            </Descriptions.Item>
          </Descriptions>
        </div>

        <!-- 证书内容 (平台签发模式可复制) -->
        <template v-if="isPlatformMode && hasActiveCert">
          <div class="mb-4">
            <h4 class="mb-3 text-sm font-medium">{{ $t('admin.tenant.domain.ssl.certificate.label') }}</h4>
            <div class="flex flex-col gap-3">
              <!-- 公钥证书 -->
              <div class="rounded border border-gray-200 p-3">
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-sm font-medium">{{ $t('admin.tenant.domain.ssl.certificate.publicKey') }}</span>
                  <Button
                    type="link"
                    size="small"
                    :disabled="!sslDetail.certificate"
                    @click="onCopyCert(sslDetail.certificate)"
                  >
                    <IconifyIcon icon="lucide:copy" class="mr-1 size-3" />
                    {{ $t('admin.tenant.domain.ssl.certificate.copy') }}
                  </Button>
                </div>
                <code class="block max-h-24 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-50 p-2 text-xs">
                  {{ sslDetail.certificate || '证书内容将在 API 就绪后显示' }}
                </code>
              </div>

              <!-- 私钥 -->
              <div class="rounded border border-gray-200 p-3">
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-sm font-medium">{{ $t('admin.tenant.domain.ssl.certificate.privateKey') }}</span>
                  <Button
                    type="link"
                    size="small"
                    :disabled="!sslDetail.privateKey"
                    @click="onCopyCert(sslDetail.privateKey)"
                  >
                    <IconifyIcon icon="lucide:copy" class="mr-1 size-3" />
                    {{ $t('admin.tenant.domain.ssl.certificate.copy') }}
                  </Button>
                </div>
                <code class="block max-h-24 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-50 p-2 text-xs">
                  {{ sslDetail.privateKey || '私钥内容将在 API 就绪后显示' }}
                </code>
              </div>

              <!-- 证书链 -->
              <div v-if="sslDetail.certificateChain" class="rounded border border-gray-200 p-3">
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-sm font-medium">{{ $t('admin.tenant.domain.ssl.certificate.chain') }}</span>
                  <Button
                    type="link"
                    size="small"
                    @click="onCopyCert(sslDetail.certificateChain)"
                  >
                    <IconifyIcon icon="lucide:copy" class="mr-1 size-3" />
                    {{ $t('admin.tenant.domain.ssl.certificate.copy') }}
                  </Button>
                </div>
                <code class="block max-h-24 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-50 p-2 text-xs">
                  {{ sslDetail.certificateChain }}
                </code>
              </div>
            </div>
          </div>
        </template>

        <!-- 自定义证书管理 -->
        <template v-if="isCustomMode && hasActiveCert">
          <div class="mb-4">
            <h4 class="mb-3 text-sm font-medium">{{ $t('admin.tenant.domain.ssl.certManage') }}</h4>
            <div class="flex gap-2">
              <Button @click="onUploadCert">
                <IconifyIcon icon="lucide:upload" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.ssl.actions.edit') }}
              </Button>
              <Button danger @click="onDeleteCert">
                <IconifyIcon icon="lucide:trash-2" class="mr-1 size-4" />
                {{ $t('admin.tenant.domain.ssl.actions.delete') }}
              </Button>
            </div>
            <p class="mt-2 text-xs text-gray-400">
              {{ $t('admin.tenant.domain.ssl.deleteHint') }}
            </p>
          </div>
        </template>

        <Divider />

        <!-- 证书来源选择 -->
        <div>
          <h4 class="mb-3 text-sm font-medium">{{ $t('admin.tenant.domain.ssl.sourceSelect') }}</h4>
          <RadioGroup v-model:value="selectedType" class="w-full">
            <div class="flex flex-col gap-3">
              <!-- 平台自动签发 -->
              <div
                class="cursor-pointer rounded-lg border p-4 transition-all"
                :class="selectedType === 'platform' ? 'border-primary bg-primary/5' : 'border-gray-200'"
                @click="selectedType = 'platform'"
              >
                <Radio value="platform" class="w-full">
                  <div class="ml-2">
                    <div class="flex items-center gap-2">
                      <span class="font-medium">{{ $t('admin.tenant.domain.ssl.type.platform') }}</span>
                      <Tag v-if="sslDetail.type === 'platform'" color="blue">{{ $t('shared.common.current') }}</Tag>
                    </div>
                    <p class="mt-1 text-xs text-gray-500">{{ $t('admin.tenant.domain.ssl.platformHint') }}</p>
                    <div v-if="selectedType === 'platform'" class="mt-3 flex gap-2">
                      <Button
                        v-if="!sslDetail.autoRenew"
                        type="primary"
                        size="small"
                        @click.stop="onEnableAutoRenew"
                      >
                        {{ $t('admin.tenant.domain.ssl.autoRenew.enable') }}
                      </Button>
                      <Button
                        v-else
                        size="small"
                        @click.stop="onDisableAutoRenew"
                      >
                        {{ $t('admin.tenant.domain.ssl.autoRenew.disable') }}
                      </Button>
                    </div>
                  </div>
                </Radio>
              </div>

              <!-- 自定义证书 -->
              <div
                class="cursor-pointer rounded-lg border p-4 transition-all"
                :class="selectedType === 'custom' ? 'border-primary bg-primary/5' : 'border-gray-200'"
                @click="selectedType = 'custom'"
              >
                <Radio value="custom" class="w-full">
                  <div class="ml-2">
                    <div class="flex items-center gap-2">
                      <span class="font-medium">{{ $t('admin.tenant.domain.ssl.type.custom') }}</span>
                      <Tag v-if="sslDetail.type === 'custom'" color="blue">{{ $t('shared.common.current') }}</Tag>
                    </div>
                    <p class="mt-1 text-xs text-gray-500">{{ $t('admin.tenant.domain.ssl.uploadHint') }}</p>
                    <div v-if="selectedType === 'custom'" class="mt-3">
                      <Button size="small" @click.stop="onUploadCert">
                        <IconifyIcon icon="lucide:upload" class="mr-1 size-3" />
                        {{ sslDetail.type === 'custom' ? $t('admin.tenant.domain.ssl.actions.reupload') : $t('admin.tenant.domain.ssl.actions.upload') }}
                      </Button>
                    </div>
                  </div>
                </Radio>
              </div>
            </div>
          </RadioGroup>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
