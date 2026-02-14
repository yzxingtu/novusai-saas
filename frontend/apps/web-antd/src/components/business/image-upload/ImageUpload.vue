<script setup lang="ts">
import { Button, Upload } from 'ant-design-vue';

import { $t as t } from '#/locales';
import { requestClient } from '#/utils/request';

interface UploadRequestOption {
  file: Blob | File | string;
  onSuccess?: (body: any, xhr?: XMLHttpRequest) => void;
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
    const data = await requestClient.upload(
      props.uploadUrl,
      { file: file as File },
      {},
      (progress) => onProgress && onProgress({ percent: progress.percent }),
    );
    // 约定后端返回 url
    const url = (data && (data.url || data.path || data.src)) as string;
    emit('update:modelValue', url);
    onSuccess && onSuccess(data as any, {} as any);
  } catch (error) {
    onError && onError(error as any);
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
