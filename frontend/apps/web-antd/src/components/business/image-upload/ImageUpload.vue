<script setup lang="ts">
/**
 * Image Upload Component
 * 图片上传组件
 *
 * v-model binds attachment ID (string), automatically converts to image URL for display.
 * v-model 绑定附件 ID（字符串），显示时自动转为图片 URL。
 * Auto-detects admin/tenant endpoint from URL, calls corresponding upload API.
 * 自动根据 URL 检测 admin/tenant 端，调用对应的上传 API。
 */
import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, message, Spin, Upload } from 'ant-design-vue';

import { smartUploadFile as adminUploadApi } from '#/api/admin/attachment';
import { smartUploadFile as tenantUploadApi } from '#/api/tenant/attachment';
import { smartUploadFile as userUploadApi } from '#/api/user/attachment';
import { $t as t } from '#/locales';
import { toAttachmentImageUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** Allowed file types / 允许的文件类型 */
    accept?: string;
    /** API endpoint type, defaults to auto-detect from URL / API 端类型，默认从 URL 自动检测 */
    endpoint?: 'admin' | 'tenant' | 'user';
    /** Current value: canonical attachment ID / 当前值：规范附件 ID */
    modelValue?: string;
    /** File visibility: 'public' for display images (avatars/logos), 'private' for sensitive files / 文件可见性：展示图片用 public，敏感文件用 private */
    visibility?: 'private' | 'public';
  }>(),
  {
    accept: 'image/*',
    endpoint: undefined,
    modelValue: '',
    visibility: 'public',
  },
);

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const uploading = ref(false);

const resolvedEndpoint = computed(() => {
  if (props.endpoint) return props.endpoint;
  const path = window.location.pathname;
  if (path.startsWith('/admin')) return 'admin';
  if (path.startsWith('/tenant')) return 'tenant';
  return 'user';
});

const previewUrl = computed(() =>
  toAttachmentImageUrl(props.modelValue, { preset: 'medium' }),
);

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
        { file: uploadFile, tenant_id: 0, visibility: props.visibility },
        (progress) => onProgress?.({ percent: progress.percent }),
      );
      attachmentId = result.attachment?.id;
    } else if (resolvedEndpoint.value === 'user') {
      const result = await userUploadApi(
        { file: uploadFile, visibility: props.visibility },
        (progress) => onProgress?.({ percent: progress.percent }),
      );
      attachmentId = result.attachment?.id;
    } else {
      const result = await tenantUploadApi(
        { file: uploadFile, visibility: props.visibility },
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
    <!-- Uploaded preview / 已上传预览 -->
    <div
      v-if="previewUrl"
      class="group relative size-[120px] overflow-hidden rounded-lg border border-border"
    >
      <img
        :src="previewUrl"
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

    <!-- Upload button / 上传按钮 -->
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
            previewUrl ? t('shared.common.change') : t('shared.common.upload')
          }}
        </Button>
      </Upload>
    </Spin>
  </div>
</template>
