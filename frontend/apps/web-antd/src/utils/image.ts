/**
 * 图片处理工具函数
 *
 * 文档 ID: 258
 */

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
  return `/api/public/attachments/${attachmentId}/image${query ? `?${query}` : ''}`;
}
