<script lang="ts" setup>
/**
 * 域名详情/编辑抽屉
 * 查看域名详情，仅允许编辑备注
 */
import type { DomainDetailData, TenantDomainInfo } from './domains-types';

import { ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  Form,
  FormItem,
  Input,
  message,
  Spin,
  Tag,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import DomainsDnsGuideModal from './DomainsDnsGuideModal.vue';

// Emits
const emits = defineEmits<{
  success: [];
}>();

// 状态
const detailData = ref<DomainDetailData | null>(null);
const domainDetail = ref<null | TenantDomainInfo>(null);
const loading = ref(false);
const submitting = ref(false);
const editMode = ref(false);
const editRemark = ref('');

// 子组件引用
const dnsGuideModalRef = ref<InstanceType<typeof DomainsDnsGuideModal>>();

// Drawer
const [Drawer, drawerApi] = useVbenDrawer({
  async onOpenChange(isOpen) {
    if (isOpen) {
      const data = drawerApi.getData<DomainDetailData>();
      if (data?.domainId && data?.tenantId) {
        detailData.value = data;
        await loadDetail();
      }
    } else {
      detailData.value = null;
      domainDetail.value = null;
      editMode.value = false;
      editRemark.value = '';
    }
  },
  footer: false,
});

/** 加载域名详情 */
async function loadDetail() {
  if (!detailData.value) return;

  loading.value = true;
  try {
    const result = await admin.getTenantDomainApi(
      detailData.value.tenantId,
      detailData.value.domainId,
    );
    domainDetail.value = result as TenantDomainInfo;
    editRemark.value = result.remark || '';
  } catch {} finally {
    loading.value = false;
  }
}

/** 进入编辑模式 */
function onEnterEdit() {
  editMode.value = true;
  editRemark.value = domainDetail.value?.remark || '';
}

/** 取消编辑 */
function onCancelEdit() {
  editMode.value = false;
  editRemark.value = domainDetail.value?.remark || '';
}

/** 保存备注 */
async function onSaveRemark() {
  if (!detailData.value) return;

  submitting.value = true;
  try {
    await admin.updateTenantDomainApi(
      detailData.value.tenantId,
      detailData.value.domainId,
      { remark: editRemark.value.trim() || null },
    );
    message.success($t('admin.tenant.domain.updateSuccess'));
    editMode.value = false;
    await loadDetail();
    emits('success');
  } catch {} finally {
    submitting.value = false;
  }
}

/** 复制文本 */
// function onCopy(text?: string) {
//   if (text) {
//     copyToClipboard(text);
//     message.success($t('admin.tenant.domain.copySuccess'));
//   }
// }

/** 获取验证状态标签配置 */
function getVerificationTagConfig(status: string) {
  switch (status) {
    case 'failed': {
      return { color: 'error', text: $t('admin.tenant.domain.verifyFailed') };
    }
    case 'verified': {
      return { color: 'success', text: $t('admin.tenant.domain.verified') };
    }
    default: {
      return { color: 'warning', text: $t('admin.tenant.domain.pending') };
    }
  }
}

/** 获取 SSL 状态标签配置 */
function getSslTagConfig(status: string) {
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
    case 'pending': {
      return {
        color: 'processing',
        text: $t('admin.tenant.domain.ssl.status.pending'),
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

/** 打开 DNS 引导 */
function onOpenDnsGuide() {
  if (!domainDetail.value || !detailData.value?.tenantId) return;
  const guideData = {
    domain: domainDetail.value.domain,
    tenantId: detailData.value.tenantId,
    domainId: domainDetail.value.id,
    verificationInfo: domainDetail.value.verificationInfo,
    verificationToken: domainDetail.value.verificationToken,
    cnameTarget: domainDetail.value.cnameTarget,
  };
  dnsGuideModalRef.value?.open(guideData);
}

/** 打开抽屉 */
function open(data: DomainDetailData) {
  drawerApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Drawer :title="$t('admin.tenant.domain.detail')" class="w-[500px]">
    <DomainsDnsGuideModal ref="dnsGuideModalRef" />
    <Spin :spinning="loading">
      <template v-if="domainDetail">
        <!-- 基本信息 -->
        <Descriptions :column="1" bordered size="small" class="mb-4">
          <Descriptions.Item :label="$t('admin.tenant.domain.domain')">
            <div class="flex items-center gap-2">
              <code class="font-mono">{{ domainDetail.domain }}</code>
              <Tag v-if="domainDetail.isPrimary" color="blue">
                {{ $t('admin.tenant.domain.primaryDomain') }}
              </Tag>
            </div>
          </Descriptions.Item>

          <Descriptions.Item :label="$t('admin.tenant.domain.type')">
            <Tag
              :color="
                domainDetail.domainType === 'default' ? 'default' : 'blue'
              "
            >
              {{
                domainDetail.domainType === 'default'
                  ? $t('admin.tenant.domain.defaultDomain')
                  : $t('admin.tenant.domain.customDomain')
              }}
            </Tag>
          </Descriptions.Item>

          <Descriptions.Item
            :label="$t('admin.tenant.domain.verificationStatus')"
          >
            <Tag
              :color="
                getVerificationTagConfig(domainDetail.verificationStatus).color
              "
            >
              {{
                getVerificationTagConfig(domainDetail.verificationStatus).text
              }}
            </Tag>
            <!-- DNS 配置按钮 (待验证才显示) -->
            <Button
              v-if="domainDetail.verificationStatus === 'pending'"
              type="link"
              size="small"
              class="ml-2 !p-0"
              @click="onOpenDnsGuide"
            >
              <IconifyIcon icon="lucide:info" class="mr-1 size-3" />
              {{ $t('admin.tenant.domain.dnsGuide.title') }}
            </Button>
            <span
              v-if="domainDetail.verifiedAt"
              class="ml-2 text-xs text-gray-400"
            >
              {{ formatDate(domainDetail.verifiedAt) }}
            </span>
          </Descriptions.Item>

          <Descriptions.Item label="SSL">
            <Tag :color="getSslTagConfig(domainDetail.sslStatus).color">
              {{ getSslTagConfig(domainDetail.sslStatus).text }}
            </Tag>
            <span
              v-if="domainDetail.sslExpiresAt"
              class="ml-2 text-xs text-gray-400"
            >
              {{ $t('admin.tenant.domain.ssl.info.validTo') }}:
              {{ formatDate(domainDetail.sslExpiresAt) }}
            </span>
          </Descriptions.Item>

          <Descriptions.Item :label="$t('admin.tenant.domain.createdAt')">
            {{ formatDate(domainDetail.createdAt) }}
          </Descriptions.Item>

          <Descriptions.Item :label="$t('admin.tenant.domain.updatedAt')">
            {{ formatDate(domainDetail.updatedAt) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 备注编辑 -->
        <div class="rounded-lg border border-gray-200 p-4">
          <div class="mb-2 flex items-center justify-between">
            <h4 class="text-sm font-medium">
              {{ $t('admin.tenant.domain.remark') }}
            </h4>
            <Button
              v-if="!editMode"
              type="link"
              size="small"
              @click="onEnterEdit"
            >
              <IconifyIcon icon="lucide:edit" class="mr-1 size-3" />
              {{ $t('shared.common.edit') }}
            </Button>
          </div>

          <template v-if="editMode">
            <Form layout="vertical">
              <FormItem class="mb-2">
                <Input.TextArea
                  v-model:value="editRemark"
                  :rows="3"
                  :max-length="500"
                  show-count
                  :placeholder="$t('admin.tenant.domain.remarkPlaceholder')"
                />
              </FormItem>
              <div class="flex gap-2">
                <Button
                  type="primary"
                  size="small"
                  :loading="submitting"
                  @click="onSaveRemark"
                >
                  {{ $t('shared.common.save') }}
                </Button>
                <Button size="small" @click="onCancelEdit">
                  {{ $t('shared.common.cancel') }}
                </Button>
              </div>
            </Form>
          </template>
          <template v-else>
            <p class="text-sm text-gray-500">
              {{ domainDetail.remark || $t('shared.common.notAssigned') }}
            </p>
          </template>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
