/**
 * Unified file upload composable / 统一文件上传 Composable
 *
 * Provides pre-validation (extension + size) and upload execution
 * with i18n error messages. Consumed by AI Chat, ImageUpload, etc.
 */
import { message } from 'ant-design-vue';

import {
  CHAT_MAX_FILE_SIZE_MB,
  isExtensionAllowed,
  PLATFORM_ALLOWED_EXTENSIONS,
  PLATFORM_DENIED_EXTENSIONS,
  PLATFORM_MAX_FILE_SIZE_MB,
} from '#/constants/upload';
import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

// ============ Types ============

export interface FileValidationRules {
  /** Allowed extensions (lowercase, no dot). Defaults to PLATFORM_ALLOWED_EXTENSIONS / 允许的扩展名 */
  allowedExtensions?: Set<string>;
  /** Denied extensions (lowercase, no dot). Defaults to PLATFORM_DENIED_EXTENSIONS / 禁止的扩展名 */
  deniedExtensions?: Set<string>;
  /** Max file size in MB. Defaults to PLATFORM_MAX_FILE_SIZE_MB / 最大文件大小(MB) */
  maxSizeMb?: number;
  /** Whether the current model supports vision (for image validation) / 当前模型是否支持视觉 */
  supportsVision?: boolean;
}

export interface FileValidationResult {
  valid: boolean;
  /** i18n-resolved error message (only when valid=false) / 国际化错误信息 */
  errorMessage?: string;
}

export interface UploadOptions {
  /** Additional form data fields to send with the upload / 额外表单字段 */
  extraData?: Record<string, string>;
  /** Upload progress callback / 上传进度回调 */
  onProgress?: (progress: { percent: number }) => void;
}

export interface UploadResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

// ============ Composable ============

export function useFileUpload() {
  /**
   * Validate a file before upload (extension + size) / 上传前校验文件（扩展名与大小）
   * Shows a warning message and returns { valid: false } on failure.
   */
  function validateFile(
    file: File,
    rules: FileValidationRules = {},
  ): FileValidationResult {
    const {
      allowedExtensions = PLATFORM_ALLOWED_EXTENSIONS,
      deniedExtensions = PLATFORM_DENIED_EXTENSIONS,
      maxSizeMb = PLATFORM_MAX_FILE_SIZE_MB,
    } = rules;

    // 1. Extension check
    if (!isExtensionAllowed(file.name, allowedExtensions, deniedExtensions)) {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      const msg = $t('common.uploadValidation.extensionNotAllowed', {
        extension: ext,
      });
      message.warning(msg);
      return { valid: false, errorMessage: msg };
    }

    // 2. Size check
    if (maxSizeMb > 0) {
      const fileSizeMb = file.size / (1024 * 1024);
      if (fileSizeMb > maxSizeMb) {
        const msg = $t('common.uploadValidation.fileTooLarge', {
          max: maxSizeMb,
        });
        message.warning(msg);
        return { valid: false, errorMessage: msg };
      }
    }

    return { valid: true };
  }

  /**
   * Validate a file for AI Chat context (stricter size limit) / AI 对话场景文件校验（更严大小限制）
   * Also checks vision/audio/video support for image/audio/video files.
   */
  function validateChatFile(
    file: File,
    options: {
      currentImageCount?: number;
      maxImageCount?: number;
      maxImageSizeMb?: number;
      supportsVision?: boolean;
      supportsAudio?: boolean;
      supportsVideo?: boolean;
    } = {},
  ): FileValidationResult {
    const {
      supportsVision = true,
      supportsAudio = false,
      supportsVideo = false,
      maxImageCount = 5,
      currentImageCount = 0,
      maxImageSizeMb,
    } = options;

    const isImage = file.type.startsWith('image/');
    const isAudio = file.type.startsWith('audio/');
    const isVideo = file.type.startsWith('video/');

    // Image-specific validation
    if (isImage) {
      if (!supportsVision) {
        const msg = $t('common.globalAiChat.imageNotSupported');
        message.warning(msg);
        return { valid: false, errorMessage: msg };
      }
      if (currentImageCount >= maxImageCount) {
        const msg = $t('common.globalAiChat.imageLimitExceeded', {
          max: maxImageCount,
        });
        message.warning(msg);
        return { valid: false, errorMessage: msg };
      }
      // Image-specific size check
      if (maxImageSizeMb && maxImageSizeMb > 0) {
        const fileSizeMb = file.size / (1024 * 1024);
        if (fileSizeMb > maxImageSizeMb) {
          const msg = $t('common.globalAiChat.imageSizeExceeded', {
            max: maxImageSizeMb,
          });
          message.warning(msg);
          return { valid: false, errorMessage: msg };
        }
      }
    }

    // Audio: require model support
    if (isAudio && !supportsAudio) {
      const msg = $t('common.globalAiChat.audioNotSupported');
      message.warning(msg);
      return { valid: false, errorMessage: msg };
    }

    // Video: require model support
    if (isVideo && !supportsVideo) {
      const msg = $t('common.globalAiChat.videoNotSupported');
      message.warning(msg);
      return { valid: false, errorMessage: msg };
    }

    // General validation (extension + size)
    return validateFile(file, {
      maxSizeMb: CHAT_MAX_FILE_SIZE_MB,
    });
  }

  /**
   * Upload a file to the specified URL / 向指定 URL 上传文件
   * Shows error message on failure.
   *
   * @returns UploadResult with success flag and response data
   */
  async function uploadFile<T = unknown>(
    url: string,
    file: File,
    options: UploadOptions = {},
  ): Promise<UploadResult<T>> {
    const { extraData, onProgress } = options;
    try {
      const uploadData: Record<string, Blob | File | string> = { file };
      if (extraData) {
        for (const [key, value] of Object.entries(extraData)) {
          uploadData[key] = value;
        }
      }
      const data = await requestClient.upload<T>(
        url,
        uploadData as { [key: string]: Blob | File | string; file: File },
        {},
        onProgress
          ? (progressEvent) => {
              const percent = progressEvent.total
                ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
                : 0;
              onProgress({ percent });
            }
          : undefined,
      );
      return { success: true, data };
    } catch (error: unknown) {
      const errorMsg =
        error instanceof Error
          ? error.message
          : $t('common.uploadValidation.uploadFailed');
      message.error(errorMsg);
      return { success: false, error: errorMsg };
    }
  }

  /**
   * Revoke all preview URLs from an array of attachments to prevent memory leaks / 撤销附件预览 URL 防止内存泄漏
   */
  function revokePreviewUrls(attachments: Array<{ preview?: string }>): void {
    for (const att of attachments) {
      if (att.preview) {
        URL.revokeObjectURL(att.preview);
      }
    }
  }

  return {
    validateFile,
    validateChatFile,
    uploadFile,
    revokePreviewUrls,
  };
}

export type { FileValidationRules as ValidationRules };
