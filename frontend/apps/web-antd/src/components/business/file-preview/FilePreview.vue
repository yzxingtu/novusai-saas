<script setup lang="ts">
/**
 * 文件预览组件
 */
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Image, message, Spin } from 'ant-design-vue';

import { getAttachmentPreviewUrlApi } from '#/api/tenant/attachment';
import { $t } from '#/locales';
import { getProcessedImageUrl } from '#/utils/image';

defineOptions({ name: 'FilePreview' });

const props = defineProps<{
  /** 附件信息 */
  file?: AttachmentInfo | null;
}>();

const loading = ref(false);
const previewUrl = ref<string>('');
const isImage = computed(() => props.file?.category === 'image');
const isVideo = computed(() => props.file?.category === 'video');
const isAudio = computed(() => props.file?.category === 'audio');
const isPdf = computed(() => props.file?.mimeType === 'application/pdf');

// 弹窗
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

  // 图片使用公共处理接口
  if (isImage.value) {
    previewUrl.value = getProcessedImageUrl(props.file.id, {
      preset: 'preview',
    });
    return;
  }

  // 其他文件获取临时预览链接
  loading.value = true;
  try {
    const result = await getAttachmentPreviewUrlApi(props.file.id);
    previewUrl.value = result.url;
  } catch {
    message.error($t('shared.filePreview.loadFailed'));
  } finally {
    loading.value = false;
  }
}

function handleDownload() {
  if (!previewUrl.value) return;
  const link = document.createElement('a');
  link.href = previewUrl.value;
  link.download = props.file?.name || 'download';
  link.target = '_blank';
  document.body.append(link);
  link.click();
  link.remove();
}

defineExpose({
  open: () => modalApi.open(),
  close: () => modalApi.close(),
});
</script>

<template>
  <Modal class="file-preview-modal">
    <div class="file-preview">
      <Spin :spinning="loading">
        <!-- 图片预览 -->
        <div v-if="isImage" class="file-preview__content">
          <Image :src="previewUrl" :alt="file?.name" />
        </div>

        <!-- 视频预览 -->
        <div v-else-if="isVideo" class="file-preview__content">
          <video
            controls
            :src="previewUrl"
            class="max-h-[600px] w-full"
          ></video>
        </div>

        <!-- 音频预览 -->
        <div v-else-if="isAudio" class="file-preview__content">
          <audio controls :src="previewUrl" class="w-full"></audio>
        </div>

        <!-- PDF 预览 (iframe) -->
        <div v-else-if="isPdf" class="file-preview__content h-[600px]">
          <iframe :src="previewUrl" class="h-full w-full border-0"></iframe>
        </div>

        <!-- 不支持预览 -->
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
