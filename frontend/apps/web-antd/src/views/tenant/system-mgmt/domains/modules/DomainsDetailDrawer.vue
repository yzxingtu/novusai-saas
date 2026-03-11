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
  Input,
  message,
  Spin,
  Tag,
} from 'ant-design-vue';

import { getTenantDomainApi, updateTenantDomainApi } from '#/api/tenant/domain';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import DomainsDnsGuideModal from './DomainsDnsGuideModal.vue';

// Emits
const emits = defineEmits<{
  success: [];
}>();

// State / 状态
const detailData = ref<DomainDetailData | null>(null);
const domainDetail = ref<null | TenantDomainInfo>(null);
const loading = ref(false);
const submitting = ref(false);
const editMode = ref(false);
const editRemark = ref('');

// Child component refs / 子组件引用
const dnsGuideModalRef = ref<InstanceType<typeof DomainsDnsGuideModal>>();

// Drawer
const [Drawer, drawerApi] = useVbenDrawer({
  async onOpenChange(isOpen) {
    if (isOpen) {
      const data = drawerApi.getData<DomainDetailData>();
      if (data?.domainId) {
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
    const result = await getTenantDomainApi(detailData.value.domainId);
    domainDetail.value = result as TenantDomainInfo;
    editRemark.value = result.remark || '';
  } catch {
  } finally {
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
    await updateTenantDomainApi(detailData.value.domainId, {
      remark: editRemark.value.trim() || undefined,
    });
    message.success($t('common.saveSuccess'));
    editMode.value = false;
    await loadDetail();
    emits('success');
  } catch {
  } finally {
    submitting.value = false;
  }
}

/** 获取验证状态标签配置 */
function getVerificationTagConfig(status: string) {
  switch (status) {
    case 'failed': {
      return {
        color: 'error',
        text: $t('tenant.system.domain.verification.failed'),
      };
    }
    case 'verified': {
      return {
        color: 'success',
        text: $t('tenant.system.domain.verification.verified'),
      };
    }
    default: {
      return {
        color: 'warning',
        text: $t('tenant.system.domain.verification.pending'),
      };
    }
  }
}

/** 获取 SSL 状态标签配置 */
function getSslTagConfig(status: string) {
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

/** 打开 DNS 引导 */
function onOpenDnsGuide() {
  if (!domainDetail.value) return;
  const guideData = {
    domain: domainDetail.value.domain,
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
  <Drawer :title="$t('tenant.system.domain.edit')" class="w-[500px]">
    <DomainsDnsGuideModal ref="dnsGuideModalRef" />
    <Spin :spinning="loading">
      <template v-if="domainDetail">
        <!-- 基本信息 -->
        <Descriptions :column="1" bordered size="small" class="mb-4">
          <Descriptions.Item :label="$t('tenant.system.domain.domain')">
            <div class="flex items-center gap-2">
              <code class="font-mono">{{ domainDetail.domain }}</code>
              <Tag v-if="domainDetail.isPrimary" color="blue">
                {{ $t('common.primary') }}
              </Tag>
            </div>
          </Descriptions.Item>

          <Descriptions.Item :label="$t('tenant.system.domain.typeLabel')">
            <Tag
              :color="
                domainDetail.domainType === 'default' ? 'default' : 'blue'
              "
            >
              {{
                domainDetail.domainType === 'default'
                  ? $t('tenant.system.domain.type.default')
                  : $t('tenant.system.domain.type.custom')
              }}
            </Tag>
          </Descriptions.Item>

          <Descriptions.Item
            :label="$t('tenant.system.domain.verificationStatus')"
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
              {{ $t('tenant.system.domain.dnsGuide') }}
            </Button>
            <span
              v-if="domainDetail.verifiedAt"
              class="ml-2 text-xs text-muted-foreground"
            >
              {{ formatDate(domainDetail.verifiedAt) }}
            </span>
          </Descriptions.Item>

          <Descriptions.Item :label="$t('tenant.system.domain.sslStatus')">
            <Tag :color="getSslTagConfig(domainDetail.sslStatus).color">
              {{ getSslTagConfig(domainDetail.sslStatus).text }}
            </Tag>
            <span
              v-if="domainDetail.sslExpiresAt"
              class="ml-2 text-xs text-muted-foreground"
            >
              {{ $t('tenant.system.domain.ssl.expiresAt') }}:
              {{ formatDate(domainDetail.sslExpiresAt) }}
            </span>
          </Descriptions.Item>

          <Descriptions.Item :label="$t('common.createdAt')">
            {{ formatDate(domainDetail.createdAt) }}
          </Descriptions.Item>

          <Descriptions.Item :label="$t('common.updatedAt')">
            {{ formatDate(domainDetail.updatedAt) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 备注编辑 -->
        <div class="rounded-lg border border-border p-4">
          <div class="mb-2 flex items-center justify-between">
            <h4 class="text-sm font-medium">
              {{ $t('tenant.system.domain.remark') }}
            </h4>
            <Button
              v-if="!editMode"
              type="link"
              size="small"
              @click="onEnterEdit"
            >
              <IconifyIcon icon="lucide:edit" class="mr-1 size-3" />
              {{ $t('common.edit') }}
            </Button>
          </div>

          <template v-if="editMode">
            <div class="mb-3">
              <Input.TextArea
                v-model:value="editRemark"
                :rows="3"
                :max-length="500"
                show-count
                :placeholder="
                  $t('tenant.system.domain.placeholder.inputRemark')
                "
              />
            </div>
            <div class="flex gap-2">
              <Button
                type="primary"
                size="small"
                :loading="submitting"
                @click="onSaveRemark"
              >
                {{ $t('common.save') }}
              </Button>
              <Button size="small" @click="onCancelEdit">
                {{ $t('common.cancel') }}
              </Button>
            </div>
          </template>
          <template v-else>
            <p class="text-sm text-muted-foreground">
              {{ domainDetail.remark || $t('common.notSet') }}
            </p>
          </template>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
