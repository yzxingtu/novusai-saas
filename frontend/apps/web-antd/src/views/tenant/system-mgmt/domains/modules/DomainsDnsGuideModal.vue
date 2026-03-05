<script lang="ts" setup>
/**
 * DNS 配置引导弹窗
 * 分步引导用户配置 DNS 记录，最后发起验证
 * 完全仿照管理端实现
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

import { verifyTenantDomainApi } from '#/api/tenant/domain';
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
    message.success($t('common.copied'));
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
  if (!guideData.value?.domainId) {
    modalApi.close();
    return;
  }

  verifying.value = true;
  try {
    const result = await verifyTenantDomainApi(guideData.value.domainId);
    if (result.verificationStatus === 'verified') {
      message.success($t('tenant.system.domain.messages.verifySuccess'));
      emits('success');
      modalApi.close();
    } else {
      message.warning($t('tenant.system.domain.messages.verifyFailed'));
    }
  } catch {
  } finally {
    verifying.value = false;
  }
}

/** 打开弹窗 */
function open(data: DnsGuideData) {
  modalApi.setData(data).open();
}

defineExpose({ open });

/**
 * 获取 DNS 主机记录
 * 规范判断：
 * - 二级域名（如 example.com）返回 @
 * - 三级及以上域名（如 www.example.com）返回第一部分
 */
function getDnsHostRecord(domain: string): string {
  const parts = domain.split('.');
  if (parts.length >= 3) {
    // 三级及以上域名，返回子域名部分
    return parts[0] || '';
  }
  // 二级域名，返回 @
  return '@';
}
</script>

<template>
  <Modal :title="$t('tenant.system.domain.dns.title')" class="w-[600px]">
    <template v-if="guideData">
      <!-- 步骤条 -->
      <Steps :current="currentStep" size="small" class="mb-6">
        <Steps.Step :title="$t('tenant.system.domain.dns.step1Title')" />
        <Steps.Step :title="$t('tenant.system.domain.dns.step2Title')" />
        <Steps.Step :title="$t('tenant.system.domain.dns.step3Title')" />
      </Steps>

      <!-- 步骤内容 -->
      <div class="min-h-[200px]">
        <!-- 步骤 1: TXT 记录 -->
        <template v-if="currentStep === 0">
          <Alert
            :message="$t('tenant.system.domain.dns.step1Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.recordType')"
            >
              <Tag color="blue">TXT</Tag>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.hostRecord')"
            >
              <div class="flex items-center justify-between gap-2">
                <code
                  class="break-all rounded bg-accent px-2 py-1 text-xs text-foreground"
                >
                  {{ guideData.verificationInfo?.host || '_verification' }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="
                    onCopy(guideData.verificationInfo?.host || '_verification')
                  "
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.recordValue')"
            >
              <div class="flex items-center justify-between gap-2">
                <code
                  class="break-all rounded bg-accent px-2 py-1 text-xs text-foreground"
                >
                  {{
                    guideData.verificationInfo?.value ||
                    guideData.verificationToken ||
                    '-'
                  }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="
                    onCopy(
                      guideData.verificationInfo?.value ||
                        guideData.verificationToken ||
                        '',
                    )
                  "
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
            :message="$t('tenant.system.domain.dns.step2Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <Descriptions :column="1" bordered size="small">
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.recordType')"
            >
              <Tag color="green">CNAME</Tag>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.hostRecord')"
            >
              <div class="flex items-center justify-between gap-2">
                <code
                  class="break-all rounded bg-accent px-2 py-1 text-xs text-foreground"
                >
                  {{ getDnsHostRecord(guideData.domain) }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(getDnsHostRecord(guideData.domain))"
                >
                  <IconifyIcon icon="lucide:copy" class="size-4" />
                </Button>
              </div>
            </Descriptions.Item>
            <Descriptions.Item
              :label="$t('tenant.system.domain.dns.recordValue')"
            >
              <div class="flex items-center justify-between gap-2">
                <code
                  class="break-all rounded bg-accent px-2 py-1 text-xs text-foreground"
                >
                  {{ guideData.cnameTarget || '-' }}
                </code>
                <Button
                  type="link"
                  size="small"
                  @click="onCopy(guideData.cnameTarget || '-')"
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
            :message="$t('tenant.system.domain.dns.step3Desc')"
            type="info"
            show-icon
            class="mb-4"
          />

          <div class="rounded-lg border p-4">
            <div class="flex flex-col items-center gap-4 py-4">
              <IconifyIcon
                icon="lucide:shield-check"
                class="size-16 text-primary"
              />
              <div class="text-center">
                <p class="text-base font-medium text-foreground">
                  {{ $t('tenant.system.domain.dns.step3Title') }}
                </p>
                <p class="mt-1 text-sm text-muted-foreground">
                  {{ $t('tenant.system.domain.dns.verifyHint') }}
                </p>
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
            {{ $t('common.prevStep') }}
          </Button>
          <div v-else></div>

          <div class="flex gap-2">
            <Button v-if="currentStep < 2" type="primary" @click="onNext">
              {{ $t('common.nextStep') }}
              <IconifyIcon icon="lucide:arrow-right" class="ml-1 size-4" />
            </Button>
            <Button
              v-else
              type="primary"
              :loading="verifying"
              @click="onVerify"
            >
              <IconifyIcon icon="lucide:check" class="mr-1 size-4" />
              {{ $t('tenant.system.domain.verify') }}
            </Button>
          </div>
        </div>
      </Spin>
    </template>
  </Modal>
</template>
