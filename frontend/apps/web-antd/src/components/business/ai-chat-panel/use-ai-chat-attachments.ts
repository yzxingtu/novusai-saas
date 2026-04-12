import type { ComputedRef } from 'vue';

import type { ChatAttachment } from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';

import { ref, unref } from 'vue';

import {
  buildChatAttachmentFromUpload,
  uploadChatFileApi,
} from '#/api/shared/ai-chat';
import { CHAT_ACCEPT_ATTRIBUTE } from '#/constants/upload';
import { showRequestError } from '#/utils/error-helpers';

interface ValidateChatFileOptions {
  currentImageCount: number;
  maxImageCount: number;
  maxImageSizeMb: number;
  supportsVision: boolean;
}

interface UseAIChatAttachmentsDeps {
  maxImageCount: ComputedRef<number>;
  maxImageSizeMb: ComputedRef<number>;
  options: UseAIChatOptions;
  revokePreviewUrls: (attachments: ChatAttachment[]) => void;
  supportsVision: ComputedRef<boolean>;
  validateChatFile: (
    file: File,
    options: ValidateChatFileOptions,
  ) => { valid: boolean };
}

export function useAIChatAttachments(deps: UseAIChatAttachmentsDeps) {
  const {
    maxImageCount,
    maxImageSizeMb,
    options,
    revokePreviewUrls,
    supportsVision,
    validateChatFile,
  } = deps;

  const pendingAttachments = ref<ChatAttachment[]>([]);
  const uploading = ref(false);
  const fileInput = ref<HTMLInputElement | null>(null);
  /** Pre-built accept attribute for file input / 文件选择 accept 属性 */
  const chatAcceptAttribute = CHAT_ACCEPT_ATTRIBUTE;

  /**
   * Validate a file before upload (images + non-images) / 上传前校验文件（图片与非图片）
   * Uses the unified useFileUpload composable.
   */
  function validateUpload(file: File): boolean {
    const currentImageCount = pendingAttachments.value.filter(
      (a) => a.type === 'image',
    ).length;
    const result = validateChatFile(file, {
      supportsVision: supportsVision.value,
      maxImageCount: maxImageCount.value,
      currentImageCount,
      maxImageSizeMb: maxImageSizeMb.value,
    });
    return result.valid;
  }

  /**
   * Compress an image file using Canvas API / 使用 Canvas API 压缩图片
   * Returns the original file if compression is not possible or not needed.
   */
  async function compressImage(
    file: File,
    maxDimension = 2048,
    quality = 0.85,
  ): Promise<File> {
    return new Promise((resolve) => {
      const img = new Image();
      img.addEventListener('load', () => {
        URL.revokeObjectURL(img.src);
        let { width, height } = img;
        if (
          width <= maxDimension &&
          height <= maxDimension &&
          file.size < 1024 * 1024
        ) {
          resolve(file);
          return;
        }
        if (width > maxDimension || height > maxDimension) {
          const ratio = Math.min(maxDimension / width, maxDimension / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(file);
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (blob) => {
            if (!blob || blob.size >= file.size) {
              resolve(file);
              return;
            }
            resolve(
              new File([blob], file.name, {
                type: 'image/jpeg',
                lastModified: Date.now(),
              }),
            );
          },
          'image/jpeg',
          quality,
        );
      });
      img.addEventListener('error', () => {
        URL.revokeObjectURL(img.src);
        resolve(file);
      });
      img.src = URL.createObjectURL(file);
    });
  }

  /**
   * Determine extra upload form data based on API prefix / 根据 API 前缀确定上传表单额外字段
   * Admin endpoint needs tenant_id=0 for platform attachments.
   */
  function getUploadExtraData(): Record<string, string> | undefined {
    const prefix = unref(options.apiPrefix) as string;
    if (prefix.includes('/admin')) {
      return { tenant_id: '0' };
    }
    return undefined;
  }

  async function uploadFile(file: File): Promise<ChatAttachment | null> {
    uploading.value = true;
    try {
      const isImage = file.type.startsWith('image/');
      const fileToUpload = isImage ? await compressImage(file) : file;
      const data = await uploadChatFileApi(
        unref(options.uploadUrl) as string,
        fileToUpload,
        getUploadExtraData(),
      );
      const uploadedAttachment = buildChatAttachmentFromUpload(
        fileToUpload,
        data,
      );
      return {
        ...uploadedAttachment,
        preview: isImage ? URL.createObjectURL(fileToUpload) : undefined,
      };
    } catch (error: unknown) {
      showRequestError(error, 'common.uploadValidation.uploadFailed');
      return null;
    } finally {
      uploading.value = false;
    }
  }

  async function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.length) return;
    for (const file of input.files) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
    input.value = '';
  }

  async function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageFiles: File[] = [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length === 0) return;

    e.preventDefault();

    for (const file of imageFiles) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const file of files) {
      if (!validateUpload(file)) continue;
      const att = await uploadFile(file);
      if (att) pendingAttachments.value.push(att);
    }
  }

  function removePendingAttachment(idx: number) {
    const att = pendingAttachments.value[idx];
    if (att?.preview) URL.revokeObjectURL(att.preview);
    pendingAttachments.value.splice(idx, 1);
  }

  /** Clear pending attachments and revoke all preview URLs / 清空待上传附件并撤销预览 URL */
  function clearPendingAttachments() {
    revokePreviewUrls(pendingAttachments.value);
    pendingAttachments.value = [];
  }

  return {
    chatAcceptAttribute,
    clearPendingAttachments,
    fileInput,
    handleDragOver,
    handleDrop,
    handleFileSelect,
    handlePaste,
    pendingAttachments,
    removePendingAttachment,
    uploadFile,
    uploading,
    validateUpload,
  };
}
