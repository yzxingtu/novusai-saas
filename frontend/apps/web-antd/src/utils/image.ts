/**
 * Image processing utility functions
 * 图片处理工具函数
 *
 * Document ID: 258 / 文档 ID: 258
 */

import { getAppApiUrl } from './api-url';

function getApiBaseUrl(): string {
  const apiURL = getAppApiUrl();
  if (apiURL && /^https?:\/\//.test(apiURL)) {
    return apiURL.replace(/\/+$/, '');
  }
  return '';
}

/**
 * Normalize API-relative asset URLs to absolute backend URLs in dev/proxied setups.
 * 将 API 相对资源地址归一化为后端绝对地址，避免前端 dev server 误接收图片请求。
 */
export function toAbsoluteApiUrl(url: null | string | undefined): string {
  if (typeof url !== 'string') {
    return '';
  }

  const normalized = url.trim();
  if (!normalized) {
    return '';
  }

  if (
    /^(?:blob:|data:|https?:\/\/)/i.test(normalized) ||
    normalized.startsWith('mailto:') ||
    normalized.startsWith('tel:')
  ) {
    return normalized;
  }

  if (normalized.startsWith('//')) {
    const protocol =
      typeof window === 'undefined' ? 'http:' : window.location.protocol;
    return `${protocol}${normalized}`;
  }

  const base = getApiBaseUrl();
  if (normalized.startsWith('/')) {
    return base ? `${base}${normalized}` : normalized;
  }

  return base ? `${base}/${normalized.replace(/^\.?\//, '')}` : normalized;
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
  /** Preset name / 预设名称 */
  preset?: ImagePreset;
  /** Target width / 目标宽度 */
  width?: number;
  /** Target height / 目标高度 */
  height?: number;
  /** Image quality (1-100) / 图片质量 (1-100) */
  quality?: number;
  /** Output format / 输出格式 */
  format?: ImageFormat;
  /** Scale mode / 缩放模式 */
  mode?: ImageMode;
  /** Private file access token / 私有文件访问令牌 */
  token?: string;
  /** HMAC signature expiry timestamp / HMAC 签名过期时间戳 */
  exp?: number | string;
  /** HMAC signature / HMAC 签名 */
  sign?: string;
}

export type AttachmentImageValue = null | number | string | undefined;

/**
 * Generate processed image URL
 * 生成处理后的图片 URL
 *
 * @param attachmentId - Attachment ID / 附件 ID
 * @param options - Processing options / 处理选项
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
  if (options.exp) params.set('exp', String(options.exp));
  if (options.sign) params.set('sign', options.sign);

  const query = params.toString();
  const base = getApiBaseUrl();
  return `${base}/api/public/attachments/${attachmentId}/image${query ? `?${query}` : ''}`;
}

function normalizeAttachmentIdString(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '';
  }

  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0 ? String(value) : '';
  }

  if (typeof value !== 'string') {
    return '';
  }

  const normalized = value.trim();
  if (!/^[1-9]\d*$/.test(normalized)) {
    return '';
  }
  return normalized;
}

/**
 * Parse a positive attachment ID from unknown input
 * 从未知输入中解析正整数附件 ID
 */
export function parseAttachmentId(value: unknown): null | number {
  const normalized = normalizeAttachmentIdString(value);
  if (!normalized) {
    return null;
  }
  return Number(normalized);
}

/**
 * Normalize image form values before writeback.
 * 写入前归一化图片表单值。
 */
export function toCanonicalAttachmentImageValue(value: unknown): string {
  return normalizeAttachmentIdString(value);
}

/**
 * Resolve a canonical attachment image value to a displayable URL.
 * 将规范附件图片值解析为可显示 URL。
 */
export function toAttachmentImageUrl(
  value: AttachmentImageValue,
  options: ImageProcessOptions = {},
): string {
  const attachmentId = parseAttachmentId(value);
  if (attachmentId) {
    return getProcessedImageUrl(attachmentId, options);
  }
  return '';
}

interface AttachmentLike {
  id: number;
  previewUrl?: null | string;
  preview_url?: null | string;
}

/**
 * Convert canonical avatar attachment ID to display URL.
 * 将规范头像附件 ID 转为展示 URL。
 *
 * - Number → attachment ID → generate URL via image processing endpoint
 * - Empty value → return empty string
 * - 纯数字 → 附件 ID → 通过图片处理端点生成 URL
 * - 空值 → 返回空字符串
 */
export function toAvatarDisplayUrl(val: null | string | undefined): string {
  return toAttachmentImageUrl(val, { preset: 'avatar' });
}

/**
 * Build accessible URL from attachment ID
 * 根据附件 ID 构建可访问的 URL
 *
 * Always generates URL via backend API endpoint, which handles:
 * - Storage driver routing (local / cloud storage)
 * - Path prefix concatenation
 * - Signed URL / CDN URL selection
 * 始终通过后端 API 端点生成 URL，由后端处理：
 * - 存储驱动路由（local / 各云存储）
 * - 路径 prefix 拼接
 * - 签名 URL / CDN URL 选择
 *
 * Backend returns 302 redirect to CDN for cloud storage; browser follows and caches.
 * 后端对云存储返回 302 重定向到 CDN，浏览器自动跟随并缓存。
 *
 * @param attachment - Attachment object (supports camelCase and snake_case) / 附件对象（支持 camelCase 和 snake_case 格式）
 * @param options - Image processing options / 图片处理选项
 */
export function getAttachmentUrl(
  attachment: AttachmentLike,
  options?: ImageProcessOptions,
): string {
  const signed = attachment.previewUrl || attachment.preview_url;
  if (signed) {
    const url = toAbsoluteApiUrl(signed);
    const extra = new URLSearchParams();
    if (options?.preset) extra.set('p', options.preset);
    if (options?.width) extra.set('w', String(options.width));
    if (options?.height) extra.set('h', String(options.height));
    if (options?.quality) extra.set('q', String(options.quality));
    if (options?.format) extra.set('f', options.format);
    if (options?.mode) extra.set('m', options.mode);
    const extraStr = extra.toString();
    if (extraStr) {
      return url.includes('?') ? `${url}&${extraStr}` : `${url}?${extraStr}`;
    }
    return url;
  }
  return getProcessedImageUrl(attachment.id, options);
}
