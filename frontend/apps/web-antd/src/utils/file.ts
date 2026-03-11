/**
 * File processing utility functions
 * 文件处理工具函数
 */

/**
 * Format file size to human-readable string
 * 格式化文件大小
 *
 * @param bytes - File size in bytes / 文件大小（字节）
 */
export function formatFileSize(bytes: number): string {
  if (!bytes || Number.isNaN(bytes) || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${units[i]}`;
}

/**
 * Get file icon based on filename or MIME type
 * 根据文件名或 MIME 类型获取文件图标
 *
 * @param filename - File name / 文件名
 * @param mimeType - MIME type / MIME 类型
 */
export function getFileIcon(
  filename: string,
  mimeType?: null | string,
): string {
  // 1. 优先根据 MIME 类型判断
  if (mimeType) {
    if (mimeType.startsWith('image/')) return 'lucide:image';
    if (mimeType.startsWith('video/')) return 'lucide:video';
    if (mimeType.startsWith('audio/')) return 'lucide:music';
    if (mimeType === 'application/pdf') return 'lucide:file-text';
    if (
      mimeType.includes('spreadsheet') ||
      mimeType.includes('excel') ||
      mimeType.includes('csv')
    ) {
      return 'lucide:file-spreadsheet';
    }
    if (mimeType.includes('word') || mimeType.includes('document')) {
      return 'lucide:file-text';
    }
    if (
      mimeType.includes('zip') ||
      mimeType.includes('compressed') ||
      mimeType.includes('tar') ||
      mimeType.includes('7z')
    ) {
      return 'lucide:archive';
    }
  }

  // 2. 根据文件后缀判断
  const ext = filename.split('.').pop()?.toLowerCase();
  if (!ext) return 'lucide:file';

  switch (ext) {
    // 压缩包
    case '7z':
    case 'bz2':
    case 'gz':
    case 'rar':
    case 'tar':
    case 'zip': {
      return 'lucide:archive';
    }
    // 音频
    case 'aac':
    case 'flac':
    case 'm4a':
    case 'mp3':
    case 'wav': {
      return 'lucide:music';
    }
    // 视频
    case 'avi':
    case 'mkv':
    case 'mov':
    case 'mp4':
    case 'ogg':
    case 'webm':
    case 'wmv': {
      return 'lucide:video';
    }
    // 代码
    case 'bat':
    case 'c':
    case 'cpp':
    case 'css':
    case 'go':
    case 'h':
    case 'html':
    case 'java':
    case 'js':
    case 'json':
    case 'jsx':
    case 'less':
    case 'py':
    case 'scss':
    case 'sh':
    case 'sql':
    case 'ts':
    case 'tsx':
    case 'vue':
    case 'xml':
    case 'yaml':
    case 'yml': {
      return 'lucide:file-code';
    }
    // 图片
    case 'bmp':
    case 'gif':
    case 'ico':
    case 'jpeg':
    case 'jpg':
    case 'png':
    case 'svg':
    case 'webp': {
      return 'lucide:image';
    }
    // 表格
    case 'csv':
    case 'tsv':
    case 'xls':
    case 'xlsx': {
      return 'lucide:file-spreadsheet';
    }
    case 'doc':
    case 'docx':
    case 'md':
    case 'rtf':
    case 'txt': {
      return 'lucide:file-text';
    }
    // 文档
    case 'pdf': {
      return 'lucide:file-text';
    }
    // 幻灯片
    case 'ppt':
    case 'pptx': {
      return 'lucide:presentation';
    }
    // 其他
    default: {
      return 'lucide:file';
    }
  }
}
