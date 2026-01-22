<script lang="ts" setup>
/**
 * DNS 配置引导弹窗
 * 分步引导用户配置 DNS 记录，最后发起验证
 */
import type { DnsGuideData } from './domains-types';

import { ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Descriptions,
  message,
  Spin,
  Steps,
  Tag,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

// Emits
const emits = defineEmits<{
  success: [];
}>();

// 状态
const guideData = ref<DnsGuideData | null>(null);
const currentStep = ref(0);
const verifying = ref(false);

// Modal
const [Modal, modalApi] = useVbenModal({
  onOpenChange(isOpen) {
    if (isOpen) {
      const data = modalApi.getData<DnsGuideData>();
      if (data) {
        guideData.value = data;
        currentStep.value = 0;
      }
    } else {
      guideData.value = null;
      currentStep.value = 0;
      verifying.value = false;
    }
  },
  footer: false,
});

/** 复制文本 */
function onCopy(text?: string) {
  if (text) {
    copyToClipboard(text);
    message.success($t('admin.tenant.domain.copySuccess'));
  }
}

/** 下一步 */
function onNext() {
  if (currentStep.value < 2) {
    currentStep.value++;
  }
}

/** 上一步 */
function onPrev() {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
}

/** 发起验证 */
async function onVerify() {
  if (!guideData.value?.tenantId || !guideData.value?.domainId) {
    modalApi.close();
    return;
  }

  verifying.value = true;
  try {
    const result = await admin.verifyTenantDomainApi(
      guideData.value.tenantId,
      guideData.value.domainId,
    );
    if (result.verificationStatus === 'verified') {
      message.success($t('admin.tenant.domain.verifySuccess'));
      emits('success');
      modalApi.close();
    } else {
      message.warning($t('admin.tenant.domain.verifyFailed'));
    }
  } catch (error) {
    console.error('Failed to verify domain:', error);
  } finally {
    verifying.value = false;
  }
}

/** 打开弹窗 */
function open(data: DnsGuideData) {
  modalApi.setData(data).open();
}

defineExpose({ open });
</script>

<template>
  <Modal :title="$t('admin.tenant.domain.dnsGuide.title')" class="w-[600px]">
    <template v-if="guideData">
      <!-- 步骤条 -->
      <Steps :current="currentStep" size="small" class="mb-6">
        <Steps.Step :title="$t('admin.tenant.domain.dnsGuide.step1Title')" />
        <Steps.Step :title="$t('admin.tenant.domain.dnsGuide.step2Title')" />
        <Steps.Step :title="$t('admin.tenant.domain.dnsGuide.step3Title')" />
      </Steps>

      <!-- 步骤内容 -->
      <div class="min-h-[200px]">
        <!-- 步骤 1: TXT 记录 -->
        <template v-if="currentStep === 0">
          <Alert
            :message="$t('admin.tenant.domain.dnsGuide.step1Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.recordType')">
              <Tag color="blue">TXT</Tag>
            </Descriptions.Item>
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.hostRecord')">
              <div class="flex items-center justify-between gap-2">
                <code class="bg-accent text-foreground break-all rounded px-2 py-1 text-xs">
                  {{ guideData.verificationInfo?.host || '_verification' }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(guideData.verificationInfo?.host || '_verification')"
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.recordValue')">
              <div class="flex items-center justify-between gap-2">
                <code class="bg-accent text-foreground break-all rounded px-2 py-1 text-xs">
                  {{ guideData.verificationInfo?.value || guideData.verificationToken || '-' }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(guideData.verificationInfo?.value || guideData.verificationToken || '')"
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
          </Descriptions>
        </template>

        <!-- 步骤 2: CNAME 记录 -->
        <template v-if="currentStep === 1">
          <Alert
            :message="$t('admin.tenant.domain.dnsGuide.step2Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.recordType')">
              <Tag color="green">CNAME</Tag>
            </Descriptions.Item>
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.hostRecord')">
              <div class="flex items-center justify-between gap-2">
                <code class="bg-accent text-foreground break-all rounded px-2 py-1 text-xs">
                  {{ guideData.domain.split('.')[0] }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(guideData.domain.split('.')[0])"
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
            <Descriptions.Item :label="$t('admin.tenant.domain.dnsGuide.recordValue')">
              <div class="flex items-center justify-between gap-2">
                <code class="bg-accent text-foreground break-all rounded px-2 py-1 text-xs">
                  {{ guideData.cnameTarget || 'cname.platform.com' }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(guideData.cnameTarget || 'cname.platform.com')"
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
          </Descriptions>
        </template>

        <!-- 步骤 3: 验证 -->
        <template v-if="currentStep === 2">
          <Alert
            :message="$t('admin.tenant.domain.dnsGuide.step3Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <div class="rounded-lg border p-4">
            <div class="flex flex-col items-center gap-4 py-4">
              <IconifyIcon icon="lucide:shield-check" class="size-16 text-primary" />
              <div class="text-center">
                <p class="text-foreground text-base font-medium">{{ $t('admin.tenant.domain.dnsGuide.step3Title') }}</p>
                <p class="text-muted-foreground mt-1 text-sm">{{ $t('admin.tenant.domain.dnsGuide.verifyHint') }}</p>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 底部按钮 -->
      <Spin :spinning="verifying">
        <div class="mt-6 flex justify-between">
          <Button v-if="currentStep > 0" :disabled="verifying" @click="onPrev">
            <IconifyIcon icon="lucide:arrow-left" class="mr-1 size-4" />
            {{ $t('admin.tenant.domain.dnsGuide.prevStep') }}
          </Button>
          <div v-else />

          <div class="flex gap-2">
            <Button v-if="currentStep < 2" type="primary" @click="onNext">
              {{ $t('admin.tenant.domain.dnsGuide.nextStep') }}
              <IconifyIcon icon="lucide:arrow-right" class="ml-1 size-4" />
            </Button>
            <Button v-else type="primary" :loading="verifying" @click="onVerify">
              <IconifyIcon icon="lucide:check" class="mr-1 size-4" />
              {{ $t('admin.tenant.domain.verifyDomain') }}
            </Button>
          </div>
        </div>
      </Spin>
    </template>
  </Modal>
</template>
