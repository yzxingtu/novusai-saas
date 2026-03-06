/**
 * Page Screenshot Composable
 *
 * Captures the current viewport using html2canvas, compresses to JPEG
 * (80% quality, max 1920×1080), and uploads via the chat file upload API.
 * Returns a ChatAttachment ready for injection into chat messages.
 */
import type { ChatAttachment } from '#/components/business/ai-chat-panel/types';

import { ref } from 'vue';

import { message } from 'ant-design-vue';

import { uploadChatFileApi } from '#/api/shared/ai-chat';
import { $t } from '#/locales';

// ============ Constants ============

const MAX_WIDTH = 1920;
const MAX_HEIGHT = 1080;
const JPEG_QUALITY = 0.8;
const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024; // 2MB

// ============ Types ============

export interface ScreenshotOptions {
  /** Upload endpoint URL (e.g. '/admin/attachments/upload' or '/tenant/attachments/upload') */
  uploadUrl: string;
  /** Additional form data fields (e.g. { tenant_id: '0' } for admin) */
  extraData?: Record<string, string>;
  /** Target element to capture. Defaults to document.body */
  target?: HTMLElement;
  /** Exclude elements matching this selector from the screenshot */
  excludeSelectors?: string[];
}

export interface ScreenshotResult {
  attachment: ChatAttachment;
  blob: Blob;
}

// ============ Composable ============

export function usePageScreenshot() {
  const capturing = ref(false);

  /**
   * Capture the current viewport, compress, and upload.
   * Returns a ChatAttachment on success, null on failure.
   */
  async function captureAndUpload(
    options: ScreenshotOptions,
  ): Promise<ScreenshotResult | null> {
    if (capturing.value) return null;
    capturing.value = true;

    try {
      // 1. Dynamic import html2canvas (tree-shake when unused)
      const { default: html2canvas } = await import('html2canvas');

      const target = options.target ?? document.body;

      // 2. Capture with html2canvas
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

      // 3. Resize if exceeds max dimensions
      const resized = resizeCanvas(canvas, MAX_WIDTH, MAX_HEIGHT);

      // 4. Compress to JPEG blob
      let blob = await canvasToBlob(resized, 'image/jpeg', JPEG_QUALITY);

      // 5. If still too large, reduce quality further
      if (blob.size > MAX_FILE_SIZE_BYTES) {
        blob = await canvasToBlob(resized, 'image/jpeg', 0.6);
      }
      if (blob.size > MAX_FILE_SIZE_BYTES) {
        blob = await canvasToBlob(resized, 'image/jpeg', 0.4);
      }

      if (blob.size > MAX_FILE_SIZE_BYTES) {
        message.warning(
          $t('common.globalAiChat.screenshotTooLarge', { max: 2 }),
        );
        return null;
      }

      // 6. Create File object
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `screenshot-${timestamp}.jpg`;
      const file = new File([blob], filename, {
        type: 'image/jpeg',
        lastModified: Date.now(),
      });

      // 7. Upload via chat file API
      const uploadResult = await uploadChatFileApi(
        options.uploadUrl,
        file,
        options.extraData,
      );

      const attachment: ChatAttachment = {
        type: 'image',
        url: uploadResult.url,
        name: filename,
        mime_type: 'image/jpeg',
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
      capturing.value = false;
    }
  }

  return {
    capturing,
    captureAndUpload,
  };
}

// ============ Internal Helpers ============

/**
 * Resize a canvas to fit within max dimensions while preserving aspect ratio.
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
