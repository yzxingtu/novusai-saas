<script setup lang="ts">
/**
 * 图片上传组件
 *
 * v-model 绑定附件 ID（字符串），显示时自动转为图片 URL。
 * 自动根据 URL 检测 admin/tenant 端，调用对应的上传 API。
 * 兼容旧值：如果 modelValue 是 URL 路径则直接显示。
 */
import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, message, Spin, Upload } from 'ant-design-vue';

import { uploadAttachmentApi as adminUploadApi } from '#/api/admin/attachment';
import { smartUploadFile as tenantUploadApi } from '#/api/tenant/attachment';
import { $t as t } from '#/locales';
import { getProcessedImageUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** 允许的文件类型 */
    accept?: string;
    /** API 端类型，默认从 URL 自动检测 */
    endpoint?: 'admin' | 'tenant';
    /** 当前值：附件 ID（字符串）或旧格式 URL */
    modelValue?: string;
  }>(),
  {
    accept: 'image/*',
    endpoint: undefined,
    modelValue: '',
  },
);

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const uploading = ref(false);

const resolvedEndpoint = computed(() => {
  if (props.endpoint) return props.endpoint;
  return window.location.pathname.startsWith('/admin') ? 'admin' : 'tenant';
});

/**
 * 将 modelValue（附件 ID 或旧 URL）转为可显示的图片 URL
 */
function toDisplayUrl(val: string | undefined): string {
  if (!val) return '';
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id, { preset: 'medium' });
  }
  return val;
}

async function handleCustomRequest(options: {
  file: Blob | File | string;
  onError?: (err: Error) => void;
  onProgress?: (e: { percent: number }) => void;
  onSuccess?: (body: unknown) => void;
}) {
  const { file, onSuccess, onError, onProgress } = options;
  uploading.value = true;
  try {
    const uploadFile = file as File;
    let attachmentId: number | undefined;

    if (resolvedEndpoint.value === 'admin') {
      const result = await adminUploadApi(
        { file: uploadFile, tenant_id: 0, visibility: 'private' },
        (progress) => onProgress?.({ percent: progress.percent }),
      );
      attachmentId = result.attachment?.id;
    } else {
      const result = await tenantUploadApi(
        { file: uploadFile, visibility: 'private' },
        (progress) => onProgress?.({ percent: progress.percent }),
      );
      attachmentId = result.attachment?.id;
    }

    if (attachmentId) {
      emit('update:modelValue', String(attachmentId));
    }
    onSuccess?.({});
  } catch (error) {
    message.error(t('shared.common.uploadFailed'));
    onError?.(error instanceof Error ? error : new Error(String(error)));
  } finally {
    uploading.value = false;
  }
}

function handleRemove() {
  emit('update:modelValue', '');
}
</script>

<template>
  <div class="flex items-start gap-3">
    <!-- 已上传预览 -->
    <div
      v-if="modelValue"
      class="group relative size-[120px] overflow-hidden rounded-lg border border-border"
    >
      <img
        :src="toDisplayUrl(modelValue)"
        :alt="t('shared.common.preview')"
        class="size-full cursor-pointer object-contain"
      />
      <div
        class="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      >
        <Button
          type="text"
          size="small"
          class="!size-8 !min-w-0 !rounded-full !bg-white/20 !text-white hover:!bg-white/40"
          @click="handleRemove"
        >
          <IconifyIcon icon="lucide:trash-2" class="text-sm" />
        </Button>
      </div>
    </div>

    <!-- 上传按钮 -->
    <Spin :spinning="uploading" size="small">
      <Upload
        :custom-request="handleCustomRequest"
        :show-upload-list="false"
        :accept="accept"
      >
        <Button>
          <template #icon>
            <IconifyIcon icon="lucide:image-plus" />
          </template>
          {{
            modelValue ? t('shared.common.change') : t('shared.common.upload')
          }}
        </Button>
      </Upload>
    </Spin>
  </div>
</template>
