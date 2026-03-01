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
 * 将头像值（附件 ID 或旧格式 URL）转为可显示的图片 URL
 *
 * - 纯数字 → 附件 ID → 通过图片处理端点生成 URL
 * - 已是 URL → 直接返回
 * - 空值 → 返回空字符串
 */
export function toAvatarDisplayUrl(val: null | string | undefined): string {
  if (!val) return '';
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id, { preset: 'avatar' });
  }
  return val;
}

/**
 * 根据附件 ID 构建可访问的 URL
 *
 * 始终通过后端 API 端点生成 URL，由后端处理：
 * - 存储驱动路由（local / 各云存储）
 * - 路径 prefix 拼接
 * - 签名 URL / CDN URL 选择
 * - 存储迁移兼容（config mismatch fallback）
 *
 * 后端对云存储返回 302 重定向到 CDN，浏览器自动跟随并缓存。
 *
 * @param attachment 附件对象（支持 camelCase 和 snake_case 格式）
 * @param options 图片处理选项
 */
export function getAttachmentUrl(
  attachment: AttachmentLike,
  options?: ImageProcessOptions,
): string {
  return getProcessedImageUrl(attachment.id, options);
}
