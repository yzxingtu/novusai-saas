<script setup lang="ts">
/**
 * File Preview Component / 文件预览组件
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref, watch } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Image, message, Spin } from 'ant-design-vue';

import { downloadAttachmentApi as downloadAdminAttachmentApi } from '#/api/admin/attachment';
import { getAttachmentPreviewUrlApi as getAdminAttachmentPreviewUrlApi } from '#/api/admin/attachment';
import { downloadAttachmentApi as downloadTenantAttachmentApi } from '#/api/tenant/attachment';
import { getAttachmentPreviewUrlApi as getTenantAttachmentPreviewUrlApi } from '#/api/tenant/attachment';
import { downloadAttachmentApi as downloadUserAttachmentApi } from '#/api/user/attachment';
import { getAttachmentPreviewUrlApi as getUserAttachmentPreviewUrlApi } from '#/api/user/attachment';
import { $t } from '#/locales';
import { getAttachmentUrl } from '#/utils/image';

defineOptions({ name: 'FilePreview' });

const props = defineProps<{
  /** Attachment endpoint type, defaults to admin/tenant/user auto-detection / 附件端点类型，默认自动识别 admin/tenant/user */
  endpoint?: 'admin' | 'tenant' | 'user';
  /** Attachment info / 附件信息 */
  file?: AttachmentInfo | null;
}>();

const loading = ref(false);
const previewUrl = ref<string>('');
const resolvedEndpoint = computed(() => {
  if (props.endpoint) {
    return props.endpoint;
  }
  if (window.location.pathname.startsWith('/admin')) {
    return 'admin';
  }
  if (window.location.pathname.startsWith('/tenant')) {
    return 'tenant';
  }
  return 'user';
});
const isImage = computed(() => props.file?.category === 'image');
const isVideo = computed(() => props.file?.category === 'video');
const isAudio = computed(() => props.file?.category === 'audio');
const isPdf = computed(() => props.file?.mimeType === 'application/pdf');

// Modal / 弹窗
const [Modal, modalApi] = useVbenModal({
  title: $t('shared.filePreview.title'),
  footer: false,
  onOpenChange: (isOpen) => {
    if (isOpen && props.file) {
      loadPreviewUrl();
    }
  },
});

async function loadPreviewUrl() {
  if (!props.file) return;

  // Images must reuse signed previewUrl when present, otherwise private images lose access token
  // 图片预览必须优先复用带签名的 previewUrl，否则私有图片会丢失访问 token
  if (isImage.value) {
    previewUrl.value = getAttachmentUrl(props.file, {
      preset: 'preview',
    });
    return;
  }

  // Other files get temporary preview link / 其他文件获取临时预览链接
  if (props.file.previewUrl) {
    previewUrl.value = props.file.previewUrl;
    return;
  }

  loading.value = true;
  try {
    const previewApi =
      resolvedEndpoint.value === 'admin'
        ? getAdminAttachmentPreviewUrlApi
        : resolvedEndpoint.value === 'tenant'
          ? getTenantAttachmentPreviewUrlApi
          : getUserAttachmentPreviewUrlApi;
    const result = await previewApi(props.file.id);
    previewUrl.value = result.url;
  } catch {
    message.error($t('shared.filePreview.loadFailed'));
  } finally {
    loading.value = false;
  }
}

async function handleDownload() {
  if (!props.file) return;
  try {
    const downloadApi =
      resolvedEndpoint.value === 'admin'
        ? downloadAdminAttachmentApi
        : resolvedEndpoint.value === 'tenant'
          ? downloadTenantAttachmentApi
          : downloadUserAttachmentApi;
    await downloadApi(props.file.id, props.file.name, props.file.mimeType);
  } catch {
    message.error($t('common.http.downloadFailed'));
  }
}

watch(
  () => props.file?.id,
  () => {
    previewUrl.value = '';
  },
);

defineExpose({
  open: () => modalApi.open(),
  close: () => modalApi.close(),
});
</script>

<template>
  <Modal class="file-preview-modal">
    <div class="file-preview">
      <Spin :spinning="loading">
        <!-- Image preview / 图片预览 -->
        <div v-if="isImage" class="file-preview__content">
          <Image :src="previewUrl" :alt="file?.name" />
        </div>

        <!-- Video preview / 视频预览 -->
        <div v-else-if="isVideo" class="file-preview__content">
          <video
            controls
            :src="previewUrl"
            class="max-h-[600px] w-full"
          ></video>
        </div>

        <!-- Audio preview / 音频预览 -->
        <div v-else-if="isAudio" class="file-preview__content">
          <audio controls :src="previewUrl" class="w-full"></audio>
        </div>

        <!-- PDF preview (iframe) / PDF 预览 (iframe) -->
        <div v-else-if="isPdf" class="file-preview__content h-[600px]">
          <iframe :src="previewUrl" class="h-full w-full border-0"></iframe>
        </div>

        <!-- Preview not supported / 不支持预览 -->
        <div v-else class="file-preview__empty">
          <IconifyIcon
            icon="lucide:file-question"
            class="mb-4 size-16 text-muted-foreground"
          />
          <p class="mb-4 text-lg text-muted-foreground">
            {{ $t('shared.filePreview.notSupported') }}
          </p>
          <Button type="primary" @click="handleDownload">
            <template #icon>
              <IconifyIcon icon="lucide:download" />
            </template>
            {{ $t('shared.filePreview.download') }}
          </Button>
        </div>
      </Spin>
    </div>
  </Modal>
</template>

<style scoped>
.file-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.file-preview__content {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.file-preview__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
}
</style>

<style>
.file-preview-modal .vben-modal-content {
  width: 1000px;
  max-width: 95vw;
}
</style>
