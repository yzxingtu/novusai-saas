<script setup lang="ts">
import type { AttachmentDetailSection } from '#/components/business/attachment-detail';
/**
 * 企业端附件详情抽屉
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, message, Spin } from 'ant-design-vue';

import {
  downloadAttachmentApi,
  getAttachmentDetailApi,
} from '#/api/tenant/attachment';
import { AttachmentDetailDescriptions } from '#/components/business/attachment-detail';
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

const sections = computed<AttachmentDetailSection[]>(() => {
  if (!detail.value) return [];
  return [
    {
      title: $t('tenant.system.attachment.basicInfo'),
      fields: [
        {
          label: $t('tenant.system.attachment.name'),
          value: detail.value.name,
        },
        {
          label: $t('tenant.system.attachment.category'),
          value: getCategoryText(detail.value.category),
          kind: 'tag',
          color: getCategoryColor(detail.value.category),
        },
        {
          label: $t('tenant.system.attachment.mimeType'),
          value: detail.value.mimeType,
          kind: 'code',
        },
        {
          label: $t('tenant.system.attachment.size'),
          value: formatFileSize(detail.value.size),
        },
        {
          label: $t('tenant.system.attachment.visibility'),
          value: getVisibilityText(detail.value.visibility),
          kind: 'tag',
          color: getVisibilityColor(detail.value.visibility),
        },
      ],
    },
    {
      title: $t('tenant.system.attachment.timeInfo'),
      fields: [
        {
          label: $t('tenant.system.attachment.uploadedAt'),
          value: formatDate(detail.value.createdAt),
        },
        {
          label: $t('tenant.system.attachment.updatedAt'),
          value: formatDate(detail.value.updatedAt),
        },
      ],
    },
  ];
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
    await downloadAttachmentApi(
      detail.value.id,
      detail.value.name,
      detail.value.mimeType,
    );
    message.success($t('tenant.system.attachment.messages.downloadStarted'));
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  }
}

// Reset detail when drawer closes / 关闭抽屉时重置详情
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
        <AttachmentDetailDescriptions :sections="sections" />
      </template>
    </Spin>
  </Drawer>
</template>
