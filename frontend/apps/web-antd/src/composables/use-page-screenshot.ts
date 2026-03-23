/**
 * Page Screenshot Composable / 页面截屏 Composable
 *
 * Captures the current viewport using html2canvas, compresses to JPEG
 * (80% quality, max 1920×1080), and uploads via the standard attachment smart-upload API.
 * Returns a ChatAttachment ready for injection into chat messages.
 */
import type { ChatAttachment } from '#/components/business/ai-chat-panel/types';

import { ref } from 'vue';

import { message } from 'ant-design-vue';

import {
  buildChatAttachmentFromUpload,
  uploadChatFileApi,
} from '#/api/shared/ai-chat';
import { resolveEndpointByPath } from '#/constants/endpoints';
import { $t } from '#/locales';
import { EndpointType } from '#/types/endpoint';

// ============ Constants / 常量 ============

const MAX_WIDTH = 1920;
const MAX_HEIGHT = 1080;
const JPEG_QUALITY = 0.8;
const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024; // 2MB
const globalCapturing = ref(false);

export const DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS = [
  '[data-ai-panel]',
  '.ant-message',
  '.ant-modal-root',
  '.ant-notification',
] as const;

// ============ Types / 类型 ============

export interface ScreenshotOptions {
  /** Upload endpoint URL (e.g. '/admin/attachments/upload' or '/tenant/attachments/upload') / 上传接口 URL */
  uploadUrl: string;
  /** Additional form data fields (e.g. { tenant_id: '0' } for admin) / 额外表单字段 */
  extraData?: Record<string, string>;
  /** Target element to capture. Defaults to document.body / 截屏目标元素 */
  target?: HTMLElement;
  /** Exclude elements matching this selector from the screenshot / 截屏排除选择器 */
  excludeSelectors?: string[];
}

export interface ScreenshotResult {
  attachment: ChatAttachment;
  blob: Blob;
}

export interface ScreenshotUploadTarget {
  extraData?: Record<string, string>;
  uploadUrl: string;
}

export function resolveScreenshotUploadTarget(
  pathname = window.location.pathname,
  hostname = window.location.hostname,
): ScreenshotUploadTarget {
  const endpoint = resolveEndpointByPath(pathname, hostname);

  switch (endpoint) {
    case EndpointType.ADMIN: {
      return {
        uploadUrl: '/admin/attachments/upload',
        extraData: { tenant_id: '0' },
      };
    }
    case EndpointType.TENANT: {
      return {
        uploadUrl: '/tenant/attachments/upload',
      };
    }
    case EndpointType.USER:
    default: {
      return {
        uploadUrl: '/api/user/attachments/upload',
      };
    }
  }
}

export async function capturePageScreenshot(
  options: ScreenshotOptions,
): Promise<ScreenshotResult | null> {
  if (globalCapturing.value) return null;
  globalCapturing.value = true;

  try {
    // 1. Dynamic import html2canvas (tree-shake when unused) / 动态导入 html2canvas（未使用时可被摇树优化）
    const { default: html2canvas } = await import('html2canvas');

    const target = options.target ?? document.body;

    // 2. Capture with html2canvas / 使用 html2canvas 采集当前视口
    const canvas = await html2canvas(target, {
      useCORS: true,
      allowTaint: false,
      scale: Math.min(window.devicePixelRatio, 2),
      width: window.innerWidth,
      height: window.innerHeight,
      x: window.scrollX,
      y: window.scrollY,
      ignoreElements: (element: Element) => {
        if (!options.excludeSelectors?.length) return false;
        return options.excludeSelectors.some((sel) => element.matches(sel));
      },
      logging: false,
    });

    // 3. Resize if exceeds max dimensions / 超过最大尺寸时按比例缩放
    const resized = resizeCanvas(canvas, MAX_WIDTH, MAX_HEIGHT);

    // 4. Compress to JPEG blob / 压缩为 JPEG Blob
    let blob = await canvasToBlob(resized, 'image/jpeg', JPEG_QUALITY);

    // 5. If still too large, reduce quality further / 若仍过大则继续降低质量
    if (blob.size > MAX_FILE_SIZE_BYTES) {
      blob = await canvasToBlob(resized, 'image/jpeg', 0.6);
    }
    if (blob.size > MAX_FILE_SIZE_BYTES) {
      blob = await canvasToBlob(resized, 'image/jpeg', 0.4);
    }

    if (blob.size > MAX_FILE_SIZE_BYTES) {
      message.warning($t('common.globalAiChat.screenshotTooLarge', { max: 2 }));
      return null;
    }

    // 6. Create File object / 构造上传用 File 对象
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `screenshot-${timestamp}.jpg`;
    const file = new File([blob], filename, {
      type: 'image/jpeg',
      lastModified: Date.now(),
    });

    // 7. Upload via endpoint-aware attachment API / 通过端别感知的附件上传接口上传
    const uploadResult = await uploadChatFileApi(
      options.uploadUrl,
      file,
      options.extraData,
    );

    const attachment: ChatAttachment = {
      ...buildChatAttachmentFromUpload(file, uploadResult),
      preview: URL.createObjectURL(blob),
    };

    return { attachment, blob };
  } catch (error: unknown) {
    const errorMsg =
      error instanceof Error
        ? error.message
        : $t('common.globalAiChat.screenshotFailed');
    message.error(errorMsg);
    return null;
  } finally {
    globalCapturing.value = false;
  }
}

// ============ Composable / 组合式 API ============

export function usePageScreenshot() {
  async function captureAndUpload(
    options: ScreenshotOptions,
  ): Promise<ScreenshotResult | null> {
    return capturePageScreenshot(options);
  }

  return {
    capturing: globalCapturing,
    captureAndUpload,
  };
}

// ============ Internal Helpers / 内部辅助函数 ============

/**
 * Resize a canvas to fit within max dimensions while preserving aspect ratio.
 * 在保持宽高比的前提下，将 canvas 缩放到最大尺寸内。
 */
function resizeCanvas(
  source: HTMLCanvasElement,
  maxWidth: number,
  maxHeight: number,
): HTMLCanvasElement {
  let { width, height } = source;

  if (width <= maxWidth && height <= maxHeight) {
    return source;
  }

  const ratio = Math.min(maxWidth / width, maxHeight / height);
  width = Math.round(width * ratio);
  height = Math.round(height * ratio);

  const resized = document.createElement('canvas');
  resized.width = width;
  resized.height = height;
  const ctx = resized.getContext('2d');
  if (!ctx) return source;

  ctx.drawImage(source, 0, 0, width, height);
  return resized;
}

/**
 * Convert canvas to Blob with specified format and quality.
 * 按指定格式和质量将 canvas 转为 Blob。
 */
function canvasToBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error('Canvas toBlob returned null'));
        }
      },
      type,
      quality,
    );
  });
}
