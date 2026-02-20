<script setup lang="ts">
import { Button, Upload } from 'ant-design-vue';

import { $t as t } from '#/locales';
import { requestClient } from '#/utils/request';

interface UploadResponseData {
  url?: string;
  path?: string;
  attachment?: { path?: string };
}

interface UploadRequestOption {
  file: Blob | File | string;
  onSuccess?: (body: UploadResponseData) => void;
  onError?: (err: Error) => void;
  onProgress?: (e: { percent: number }) => void;
}

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    uploadUrl?: string;
  }>(),
  {
    uploadUrl: '/admin/attachments/upload',
  },
);

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

async function handleCustomRequest(options: UploadRequestOption) {
  const { file, onSuccess, onError, onProgress } = options;
  try {
    const data = await requestClient.upload<UploadResponseData>(
      props.uploadUrl,
      { file: file as File },
      {},
      (progress) => onProgress && onProgress({ percent: progress.percent }),
    );
    const url = data?.url || data?.path || '';
    emit('update:modelValue', url);
    onSuccess?.(data);
  } catch (error) {
    onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}
</script>

<template>
  <div class="image-upload">
    <div v-if="modelValue" class="preview">
      <img :src="modelValue" alt="preview" />
      <div class="actions">
        <Button size="small" @click="emit('update:modelValue', '')">
          {{ t('shared.common.delete') }}
        </Button>
      </div>
    </div>
    <Upload
      v-else
      :custom-request="handleCustomRequest"
      :show-upload-list="false"
      accept="image/*"
    >
      <Button type="dashed">{{ t('shared.common.upload') }}</Button>
    </Upload>
  </div>
</template>

<style scoped>
.image-upload .preview {
  position: relative;
  width: 160px;
  height: 160px;
  overflow: hidden;
  border: 1px solid var(--ant-color-border);
  border-radius: 6px;
}

.image-upload .preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.image-upload .preview .actions {
  position: absolute;
  right: 8px;
  bottom: 8px;
}
</style>
