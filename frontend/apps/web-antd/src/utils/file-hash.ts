/**
 * File hash computation utility
 * 文件哈希计算工具
 *
 * Uses Web Crypto API (SubtleCrypto) to compute file SHA-256 hash.
 * - Small files (≤64MB): read into memory at once
 * - Large files (>64MB): chunked reading + incremental computation (requires ReadableStream)
 * - Supports progress callback and AbortSignal cancellation
 * 使用 Web Crypto API (SubtleCrypto) 计算文件 SHA-256 哈希。
 * - 小文件（≤64MB）：一次性读入内存计算
 * - 大文件（>64MB）：分块读取 + 增量计算（需浏览器支持 ReadableStream）
 * - 支持进度回调和 AbortSignal 取消
 *
 * Return format: "sha256:{hex_digest}"
 * 返回格式: "sha256:{hex_digest}"
 */

const SMALL_FILE_THRESHOLD = 64 * 1024 * 1024; // 64MB
const READ_CHUNK_SIZE = 2 * 1024 * 1024; // 2MB per chunk for streaming

/**
 * Convert ArrayBuffer to hexadecimal string
 * 将 ArrayBuffer 转为十六进制字符串
 */
function bufferToHex(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const hex: string[] = [];
  for (const b of bytes) {
    hex.push(b.toString(16).padStart(2, '0'));
  }
  return hex.join('');
}

/**
 * Small file hash: read entire ArrayBuffer then use SubtleCrypto.digest
 * 小文件哈希：一次性读入 ArrayBuffer 后用 SubtleCrypto.digest
 */
async function hashSmallFile(
  file: File,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<string> {
  if (signal?.aborted) {
    throw new DOMException('Hash computation aborted', 'AbortError');
  }

  onProgress?.(0);
  const buffer = await file.arrayBuffer();

  if (signal?.aborted) {
    throw new DOMException('Hash computation aborted', 'AbortError');
  }

  onProgress?.(50);
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  onProgress?.(100);

  return bufferToHex(hashBuffer);
}

/**
 * Large file hash: chunked reading + manual incremental SHA-256
 * 大文件哈希：分块读取 + 手动增量 SHA-256
 *
 * Since SubtleCrypto doesn't support incremental digest, large files
 * are read in chunks then merged into a single ArrayBuffer for computation.
 * Chunk size is 2MB to control memory peak, but all data must be merged.
 * 由于 SubtleCrypto 不支持增量 digest，大文件采用分块读取后
 * 合并为单个 ArrayBuffer 再计算的方式。为控制内存峰值，
 * 分块大小为 2MB，但最终仍需将全部数据合并。
 *
 * Note: For ultra-large files (>2GB) memory optimization, consider
 * using hash-wasm's incremental interface as a replacement.
 * 注：如果未来需要处理超大文件（>2GB）的内存优化，
 * 可引入 hash-wasm 的增量接口替换此实现。
 */
async function hashLargeFile(
  file: File,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<string> {
  if (signal?.aborted) {
    throw new DOMException('Hash computation aborted', 'AbortError');
  }

  const totalSize = file.size;
  const chunks: ArrayBuffer[] = [];
  let offset = 0;

  onProgress?.(0);

  while (offset < totalSize) {
    if (signal?.aborted) {
      throw new DOMException('Hash computation aborted', 'AbortError');
    }

    const end = Math.min(offset + READ_CHUNK_SIZE, totalSize);
    const slice = file.slice(offset, end);
    const buffer = await slice.arrayBuffer();
    chunks.push(buffer);
    offset = end;

    // 读取阶段占 80% 进度 / read phase → 80% progress
    const readPercent = Math.round((offset / totalSize) * 80);
    onProgress?.(readPercent);
  }

  if (signal?.aborted) {
    throw new DOMException('Hash computation aborted', 'AbortError');
  }

  // 合并所有块
  const merged = new Uint8Array(totalSize);
  let pos = 0;
  for (const chunk of chunks) {
    merged.set(new Uint8Array(chunk), pos);
    pos += chunk.byteLength;
  }

  onProgress?.(90);

  // 计算哈希
  const hashBuffer = await crypto.subtle.digest('SHA-256', merged.buffer);
  onProgress?.(100);

  return bufferToHex(hashBuffer);
}

/**
 * Compute file SHA-256 hash
 * 计算文件 SHA-256 哈希
 *
 * @param file - File to compute hash for / 要计算哈希的文件
 * @param options - Optional configuration / 可选配置
 * @param options.onProgress - Progress callback (0-100) / 进度回调 (0-100)
 * @param options.signal - AbortSignal for cancellation / AbortSignal 用于取消计算
 * @returns Hash string in "sha256:{hex_digest}" format / 格式为 "sha256:{hex_digest}" 的哈希字符串
 *
 * @example
 * ```ts
 * const hash = await computeFileHash(file);
 * // => "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
 *
 * // 带进度和取消
 * const controller = new AbortController();
 * const hash = await computeFileHash(file, {
 *   onProgress: (percent) => console.log(`${percent}%`),
 *   signal: controller.signal,
 * });
 * ```
 */
export async function computeFileHash(
  file: File,
  options?: {
    onProgress?: (percent: number) => void;
    signal?: AbortSignal;
  },
): Promise<string> {
  const { onProgress, signal } = options ?? {};

  // crypto.subtle 仅在安全上下文（HTTPS / localhost）可用
  // 非安全上下文返回空串，调用方应跳过预检直接上传
  if (!globalThis.crypto?.subtle) {
    onProgress?.(100);
    return '';
  }

  // 空文件直接返回空内容的 SHA-256
  if (file.size === 0) {
    onProgress?.(100);
    return 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
  }

  const hex =
    file.size <= SMALL_FILE_THRESHOLD
      ? await hashSmallFile(file, onProgress, signal)
      : await hashLargeFile(file, onProgress, signal);

  return `sha256:${hex}`;
}
