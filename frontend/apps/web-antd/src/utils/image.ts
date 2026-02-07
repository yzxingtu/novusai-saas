/**
 * 图片处理工具函数
 *
 * 文档 ID: 258
 */

import { useAppConfig } from '@vben/hooks';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

function getApiBaseUrl(): string {
  if (apiURL && /^https?:\/\//.test(apiURL)) {
    return apiURL.replace(/\/+$/, '');
  }
  return '';
}

export type ImagePreset =
  | 'avatar'
  | 'banner'
  | 'large'
  | 'medium'
  | 'preview'
  | 'small'
  | 'thumb';

export type ImageMode = 'crop' | 'fill' | 'fit' | 'pad';

export type ImageFormat = 'gif' | 'jpg' | 'png' | 'webp';

export interface ImageProcessOptions {
  /** 预设名称 */
  preset?: ImagePreset;
  /** 目标宽度 */
  width?: number;
  /** 目标高度 */
  height?: number;
  /** 图片质量 (1-100) */
  quality?: number;
  /** 输出格式 */
  format?: ImageFormat;
  /** 缩放模式 */
  mode?: ImageMode;
  /** 私有文件访问令牌 */
  token?: string;
}

/**
 * 生成处理后的图片 URL
 *
 * @param attachmentId 附件 ID
 * @param options 处理选项
 */
export function getProcessedImageUrl(
  attachmentId: number,
  options: ImageProcessOptions = {},
): string {
  const params = new URLSearchParams();

  if (options.preset) params.set('p', options.preset);
  if (options.width) params.set('w', String(options.width));
  if (options.height) params.set('h', String(options.height));
  if (options.quality) params.set('q', String(options.quality));
  if (options.format) params.set('f', options.format);
  if (options.mode) params.set('m', options.mode);
  if (options.token) params.set('token', options.token);

  const query = params.toString();
  const base = getApiBaseUrl();
  return `${base}/api/public/attachments/${attachmentId}/image${query ? `?${query}` : ''}`;
}

interface AttachmentLike {
  id: number;
  driver: string;
  baseUrl?: string;
  base_url?: string;
  path: string;
}

/**
 * 根据附件的存储驱动构建可访问的 URL
 *
 * - local driver: 使用图片处理端点 /api/public/attachments/{id}/image
 * - 远程 driver (s3 等): 使用 base_url + path 拼接完整外部 URL
 *
 * @param attachment 附件对象（支持 camelCase 和 snake_case 格式）
 * @param options 图片处理选项（仅对 local driver 或无 baseUrl 的附件生效）
 */
export function getAttachmentUrl(
  attachment: AttachmentLike,
  options?: ImageProcessOptions,
): string {
  if (attachment.driver === 'local') {
    return getProcessedImageUrl(attachment.id, options);
  }
  const baseUrl = attachment.baseUrl || attachment.base_url || '';
  if (baseUrl) {
    const path = attachment.path.replace(/^\/+/, '');
    return `${baseUrl.replace(/\/+$/, '')}/${path}`;
  }
  return getProcessedImageUrl(attachment.id, options);
}
