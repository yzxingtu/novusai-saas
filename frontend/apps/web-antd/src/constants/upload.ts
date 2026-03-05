/**
 * Upload rule constants
 *
 * Aligned with backend platform storage configuration defaults:
 * - platform_storage_allowed_extensions
 * - platform_storage_denied_extensions
 * - platform_storage_max_file_size_mb
 *
 * These serve as frontend pre-validation defaults.
 * The runtime rules can be overridden via GET /attachments/upload-rules API.
 */

// ============ Extension Sets ============

/** Image file extensions */
export const IMAGE_EXTENSIONS = new Set([
  'bmp',
  'gif',
  'ico',
  'jpeg',
  'jpg',
  'png',
  'svg',
  'webp',
]);

/** Document file extensions */
export const DOCUMENT_EXTENSIONS = new Set([
  'csv',
  'doc',
  'docx',
  'json',
  'pdf',
  'ppt',
  'pptx',
  'txt',
  'xls',
  'xlsx',
  'xml',
]);

/** Video file extensions */
export const VIDEO_EXTENSIONS = new Set(['avi', 'mkv', 'mov', 'mp4', 'webm']);

/** Audio file extensions */
export const AUDIO_EXTENSIONS = new Set(['aac', 'flac', 'm4a', 'mp3', 'wav']);

/** Archive file extensions */
export const ARCHIVE_EXTENSIONS = new Set(['7z', 'gz', 'rar', 'tar', 'zip']);

// ============ Platform Default Rules ============

/**
 * Default allowed extensions (synced with backend platform_storage_allowed_extensions)
 */
export const PLATFORM_ALLOWED_EXTENSIONS = new Set([
  ...ARCHIVE_EXTENSIONS,
  ...AUDIO_EXTENSIONS,
  ...DOCUMENT_EXTENSIONS,
  ...IMAGE_EXTENSIONS,
  ...VIDEO_EXTENSIONS,
]);

/**
 * Default denied extensions (synced with backend platform_storage_denied_extensions)
 */
export const PLATFORM_DENIED_EXTENSIONS = new Set([
  'asp',
  'aspx',
  'bat',
  'cgi',
  'cmd',
  'dll',
  'exe',
  'htaccess',
  'jsp',
  'php',
  'pl',
  'py',
  'rb',
  'sh',
  'so',
]);

/** Default max file size in MB (synced with backend platform_storage_max_file_size_mb) */
export const PLATFORM_MAX_FILE_SIZE_MB = 100;

// ============ AI Chat Specific ============

/**
 * AI Chat accepted extensions for the file picker `accept` attribute.
 * A subset of PLATFORM_ALLOWED_EXTENSIONS commonly used in chat.
 */
export const CHAT_ACCEPTED_EXTENSIONS = [
  ...[...IMAGE_EXTENSIONS].map((ext) => `.${ext}`),
  ...[...DOCUMENT_EXTENSIONS].map((ext) => `.${ext}`),
  ...[...VIDEO_EXTENSIONS].map((ext) => `.${ext}`),
  ...[...AUDIO_EXTENSIONS].map((ext) => `.${ext}`),
  ...[...ARCHIVE_EXTENSIONS].map((ext) => `.${ext}`),
];

/** AI Chat max file size in MB (more conservative than platform default) */
export const CHAT_MAX_FILE_SIZE_MB = 10;

/**
 * Build an HTML `accept` attribute value from the accepted extensions.
 */
export function buildAcceptAttribute(extensions: string[]): string {
  return extensions.join(',');
}

/** Pre-built accept attribute string for AI Chat file input */
export const CHAT_ACCEPT_ATTRIBUTE = buildAcceptAttribute(
  CHAT_ACCEPTED_EXTENSIONS,
);

// ============ Validation Helpers ============

/**
 * Check if a filename has an allowed extension.
 *
 * @param filename - File name or path
 * @param allowed - Set of allowed extensions (lowercase, no dot)
 * @param denied - Set of denied extensions (lowercase, no dot)
 * @returns true if extension is allowed
 */
export function isExtensionAllowed(
  filename: string,
  allowed: Set<string> = PLATFORM_ALLOWED_EXTENSIONS,
  denied: Set<string> = PLATFORM_DENIED_EXTENSIONS,
): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (!ext) return false;
  if (denied.has(ext)) return false;
  if (allowed.size === 0) return true;
  return allowed.has(ext);
}

/**
 * Check if a file is an image based on its extension or MIME type.
 */
export function isImageFile(file: File): boolean {
  if (file.type.startsWith('image/')) return true;
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  return IMAGE_EXTENSIONS.has(ext);
}

/**
 * Get the extension category for a given file extension.
 */
export function getExtensionCategory(
  ext: string,
): 'archive' | 'audio' | 'document' | 'image' | 'other' | 'video' {
  const lower = ext.toLowerCase().replace(/^\./, '');
  if (IMAGE_EXTENSIONS.has(lower)) return 'image';
  if (DOCUMENT_EXTENSIONS.has(lower)) return 'document';
  if (VIDEO_EXTENSIONS.has(lower)) return 'video';
  if (AUDIO_EXTENSIONS.has(lower)) return 'audio';
  if (ARCHIVE_EXTENSIONS.has(lower)) return 'archive';
  return 'other';
}
