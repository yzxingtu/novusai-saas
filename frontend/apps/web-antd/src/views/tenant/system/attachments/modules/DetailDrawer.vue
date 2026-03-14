<script setup lang="ts">
/**
 * 企业端附件详情抽屉
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  DescriptionsItem,
  message,
  Spin,
  Tag,
} from 'ant-design-vue';

import {
  getAttachmentDetailApi,
  getAttachmentDownloadUrlApi,
} from '#/api/tenant/attachment';
import { FilePreview } from '#/components/business/file-preview';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  formatFileSize,
  getCategoryColor,
  getCategoryText,
  getVisibilityColor,
  getVisibilityText,
} from '../data';

defineOptions({ name: 'TenantAttachmentDetailDrawer' });

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number }>();
      if (data?.id) {
        await loadDetail(data.id);
      }
    }
  },
});

const loading = ref(false);
const detail = ref<AttachmentInfo | null>(null);
const previewRef = ref<InstanceType<typeof FilePreview> | null>(null);

const title = computed(() => {
  return detail.value?.name || $t('tenant.system.attachment.detail');
});

async function loadDetail(id: number) {
  loading.value = true;
  try {
    detail.value = await getAttachmentDetailApi(id);
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  } finally {
    loading.value = false;
  }
}

function onPreview() {
  if (!detail.value) return;
  previewRef.value?.open();
}

async function onDownload() {
  if (!detail.value) return;
  try {
    const result = await getAttachmentDownloadUrlApi(detail.value.id);
    const link = document.createElement('a');
    link.href = result.url;
    link.download = detail.value.name;
    link.target = '_blank';
    document.body.append(link);
    link.click();
    link.remove();
    message.success($t('tenant.system.attachment.messages.downloadStarted'));
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  }
}

// Reset detail when drawer closes
watch(
  () => drawerApi.getData(),
  () => {
    detail.value = null;
  },
);
</script>

<template>
  <Drawer :title="title" class="w-[520px]">
    <FilePreview ref="previewRef" :file="detail" />
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 操作按钮 -->
        <div class="mb-4 flex gap-2">
          <Button type="primary" @click="onPreview">
            <template #icon>
              <IconifyIcon icon="lucide:eye" />
            </template>
            {{ $t('tenant.system.attachment.actions.preview') }}
          </Button>
          <Button @click="onDownload">
            <template #icon>
              <IconifyIcon icon="lucide:download" />
            </template>
            {{ $t('tenant.system.attachment.actions.download') }}
          </Button>
        </div>

        <!-- 基本信息 -->
        <Descriptions
          :title="$t('tenant.system.attachment.basicInfo')"
          :column="1"
          bordered
          size="small"
        >
          <DescriptionsItem :label="$t('tenant.system.attachment.name')">
            {{ detail.name }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.attachment.category')">
            <Tag :color="getCategoryColor(detail.category)">
              {{ getCategoryText(detail.category) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.attachment.mimeType')">
            <code class="rounded bg-accent px-1 py-0.5 text-xs">
              {{ detail.mimeType }}
            </code>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.attachment.size')">
            {{ formatFileSize(detail.size) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.attachment.visibility')">
            <Tag :color="getVisibilityColor(detail.visibility)">
              {{ getVisibilityText(detail.visibility) }}
            </Tag>
          </DescriptionsItem>
        </Descriptions>

        <!-- 时间信息 -->
        <Descriptions
          :title="$t('tenant.system.attachment.timeInfo')"
          :column="1"
          bordered
          size="small"
          class="mt-4"
        >
          <DescriptionsItem :label="$t('tenant.system.attachment.uploadedAt')">
            {{ formatDate(detail.createdAt) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.attachment.updatedAt')">
            {{ formatDate(detail.updatedAt) }}
          </DescriptionsItem>
        </Descriptions>
      </template>
    </Spin>
  </Drawer>
</template>
