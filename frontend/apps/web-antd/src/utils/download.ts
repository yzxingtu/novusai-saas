/**
 * General file download utility
 * 通用文件下载工具
 *
 * Supports downloading multiple file types: xlsx, csv, images, txt, log, etc.
 * 支持多种文件类型下载：xlsx, csv, 图片, txt, log 等
 */

/** File type to MIME type mapping / 文件类型映射 */
const MIME_TYPES: Record<string, string> = {
  // Text types / 文本类型
  txt: 'text/plain',
  log: 'text/plain',
  json: 'application/json',
  csv: 'text/csv',
  xml: 'application/xml',
  html: 'text/html',
  md: 'text/markdown',

  // Spreadsheet types / 表格类型
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  xls: 'application/vnd.ms-excel',

  // Image types / 图片类型
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  svg: 'image/svg+xml',
  webp: 'image/webp',
  bmp: 'image/bmp',
  ico: 'image/x-icon',

  // Document types / 文档类型
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',

  // Archive types / 压缩包
  zip: 'application/zip',
  rar: 'application/x-rar-compressed',
  tar: 'application/x-tar',
  gz: 'application/gzip',

  // Binary / 二进制
  bin: 'application/octet-stream',
};

/** Download configuration / 下载配置 */
export interface DownloadOptions {
  /** Filename (with extension) / 文件名（含扩展名） */
  filename: string;
  /** MIME type (optional, auto-detected from filename) / 文件类型（可选，会根据文件名自动推断） */
  mimeType?: string;
}

/**
 * Get MIME type from filename
 * 从文件名获取 MIME 类型
 */
function getMimeType(filename: string, customMimeType?: string): string {
  if (customMimeType) return customMimeType;

  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return MIME_TYPES[ext] || 'application/octet-stream';
}

/**
 * Download a Blob object
 * 下载 Blob 对象
 *
 * @param blob - Blob object / Blob 对象
 * @param options - Download configuration / 下载配置
 */
export function downloadBlob(blob: Blob, options: DownloadOptions): void {
  const { filename, mimeType } = options;
  const finalMimeType = getMimeType(filename, mimeType);

  // 创建带正确 MIME 类型的 Blob
  const finalBlob =
    blob.type === finalMimeType
      ? blob
      : new Blob([blob], { type: finalMimeType });

  const url = URL.createObjectURL(finalBlob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';

  document.body.append(link);
  link.click();
  link.remove();

  // 释放 URL 对象
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Download text content
 * 下载文本内容
 *
 * @param content - Text content / 文本内容
 * @param options - Download configuration / 下载配置
 */
export function downloadText(content: string, options: DownloadOptions): void {
  const { filename, mimeType } = options;
  const finalMimeType = getMimeType(filename, mimeType);

  const blob = new Blob([content], { type: `${finalMimeType};charset=utf-8` });
  downloadBlob(blob, { filename, mimeType: finalMimeType });
}

/**
 * Download JSON data
 * 下载 JSON 数据
 *
 * @param data - JSON data / JSON 数据
 * @param filename - Filename / 文件名
 * @param pretty - Whether to format (default true) / 是否格式化（默认 true）
 */
export function downloadJson(
  data: unknown,
  filename: string,
  pretty = true,
): void {
  const content = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
  downloadText(content, { filename, mimeType: 'application/json' });
}

/**
 * Download CSV data
 * 下载 CSV 数据
 *
 * @param data - 2D array or object array / 二维数组或对象数组
 * @param filename - Filename / 文件名
 * @param headers - Headers (optional for object array, auto-extracted from first row keys) / 表头（当 data 为对象数组时可选，会自动从第一行取 key）
 */
export function downloadCsv(
  data: Record<string, unknown>[] | unknown[][],
  filename: string,
  headers?: string[],
): void {
  let csvContent = '';

  if (data.length === 0) {
    csvContent = '';
  } else if (Array.isArray(data[0])) {
    // 二维数组
    csvContent = (data as unknown[][])
      .map((row) => row.map((cell) => escapeCsvCell(cell)).join(','))
      .join('\n');
  } else {
    // 对象数组
    const objData = data as Record<string, unknown>[];
    const keys = headers || Object.keys(objData[0] || {});

    // 表头
    csvContent = `${keys.map((key) => escapeCsvCell(key)).join(',')}\n`;

    // 数据行
    csvContent += objData
      .map((row) => keys.map((key) => escapeCsvCell(row[key])).join(','))
      .join('\n');
  }

  // 添加 BOM 以支持 Excel 正确显示中文
  const bom = '\uFEFF';
  downloadText(bom + csvContent, { filename, mimeType: 'text/csv' });
}

/**
 * CSV cell escaping
 * CSV 单元格转义
 */
function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) return '';

  const str = String(value);

  // 如果包含逗号、双引号或换行，需要用双引号包裹并转义内部双引号
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replaceAll('"', '""')}"`;
  }

  return str;
}

/**
 * Download Base64 encoded file
 * 下载 Base64 编码的文件
 *
 * @param base64 - Base64 encoded string (with or without data URL prefix) / Base64 编码字符串（可带或不带 data URL 前缀）
 * @param options - Download configuration / 下载配置
 */
export function downloadBase64(base64: string, options: DownloadOptions): void {
  // 移除 data URL 前缀（如果有）
  const base64Data = base64.includes(',')
    ? (base64.split(',')[1] ?? base64)
    : base64;

  const { filename, mimeType } = options;
  const finalMimeType = getMimeType(filename, mimeType);

  // 解码 Base64
  const binaryString = atob(base64Data);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.codePointAt(i) ?? 0;
  }

  const blob = new Blob([bytes], { type: finalMimeType });
  downloadBlob(blob, { filename, mimeType: finalMimeType });
}

/**
 * Download ArrayBuffer
 * 下载 ArrayBuffer
 *
 * @param buffer - ArrayBuffer data / ArrayBuffer 数据
 * @param options - Download configuration / 下载配置
 */
export function downloadArrayBuffer(
  buffer: ArrayBuffer,
  options: DownloadOptions,
): void {
  const { filename, mimeType } = options;
  const finalMimeType = getMimeType(filename, mimeType);

  const blob = new Blob([buffer], { type: finalMimeType });
  downloadBlob(blob, { filename, mimeType: finalMimeType });
}

/**
 * Universal download function
 * 通用下载函数
 *
 * Automatically selects download method based on data type.
 * 根据数据类型自动选择下载方法
 *
 * @param data - Data (supports string, Blob, ArrayBuffer, Base64, object/array) / 数据（支持 string, Blob, ArrayBuffer, Base64, 对象/数组）
 * @param options - Download configuration / 下载配置
 */
export function download(
  data: ArrayBuffer | Blob | Record<string, unknown>[] | string | unknown[][],
  options: DownloadOptions,
): void {
  const { filename } = options;
  const ext = filename.split('.').pop()?.toLowerCase();

  if (data instanceof Blob) {
    downloadBlob(data, options);
  } else if (data instanceof ArrayBuffer) {
    downloadArrayBuffer(data, options);
  } else if (typeof data === 'string') {
    // 检查是否为 Base64
    if (
      data.startsWith('data:') ||
      /^[A-Z0-9+/=]+$/i.test(data.slice(0, 100))
    ) {
      downloadBase64(data, options);
    } else {
      downloadText(data, options);
    }
  } else if (Array.isArray(data)) {
    // 数组数据
    if (ext === 'csv') {
      downloadCsv(data, filename);
    } else if (ext === 'json') {
      downloadJson(data, filename);
    } else {
      // 默认转为 JSON
      downloadJson(data, filename);
    }
  } else {
    // 其他对象转为 JSON
    downloadJson(data, filename);
  }
}
