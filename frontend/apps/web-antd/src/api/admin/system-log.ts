/**
 * System log API / 系统日志 API
 * Backend: /admin/system-logs/*
 */
import type { ApiRequestOptions } from '#/utils/request';

import { downloadBlob } from '#/utils/download';
import { requestClient } from '#/utils/request';

export type SystemLogSearchScope = 'category' | 'current_file';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Log statistics (backend raw format) / 日志统计信息（后端原始格式） */
export interface SystemLogStatsRaw {
  total_files: number;
  total_size: number;
}

/** Log statistics (frontend format) / 日志统计信息（前端格式） */
export interface SystemLogStats {
  totalFiles: number;
  totalSize: number;
  totalSizeFormatted: string;
}

/** Log category info (backend raw format) / 日志分类信息（后端原始格式） */
export interface SystemLogCategoryRaw {
  code: string;
  name: string;
  description?: string;
  file_count: number;
  total_size: number;
}

/** Log category info (frontend format) / 日志分类信息（前端格式） */
export interface SystemLogCategory {
  code: string;
  name: string;
  description?: string;
  fileCount: number;
  totalSize: number;
  totalSizeFormatted: string;
}

/** Log file info (backend raw format) / 日志文件信息（后端原始格式） */
export interface SystemLogFileRaw {
  name: string;
  category: string;
  size: number;
  modified_at: string;
  is_current?: boolean;
}

/** Log file info (frontend format) / 日志文件信息（前端格式） */
export interface SystemLogFile {
  filename: string;
  category: string;
  size: number;
  sizeFormatted: string;
  modifiedAt: string;
  isCurrent?: boolean;
}

/** Log line item (backend raw format) / 日志行项目（后端原始格式） */
export interface SystemLogContentItemRaw {
  file_name: string;
  line_number: number;
  content: string;
}

/** Log line item (frontend format) / 日志行项目（前端格式） */
export interface SystemLogContentItem {
  content: string;
  fileName: string;
  lineNumber: number;
}

/** Log file content response (backend raw format) / 日志文件内容响应（后端原始格式） */
export interface SystemLogContentRaw {
  filename: string;
  category: string;
  scope: SystemLogSearchScope;
  lines: string[];
  items: SystemLogContentItemRaw[];
  total_lines: number;
  total_entries: number;
  searched_files: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Log file content response (frontend format) / 日志文件内容响应（前端格式） */
export interface SystemLogContent {
  filename: string;
  category: string;
  scope: SystemLogSearchScope;
  lines: string[];
  items: SystemLogContentItem[];
  totalLines: number;
  totalEntries: number;
  searchedFiles: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface GetSystemLogContentParams {
  end_date?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
  reverse?: boolean;
  scope?: SystemLogSearchScope;
  start_date?: string;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Format file size / 格式化文件大小 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
}

function transformStats(raw: SystemLogStatsRaw): SystemLogStats {
  return {
    totalFiles: raw.total_files,
    totalSize: raw.total_size,
    totalSizeFormatted: formatFileSize(raw.total_size),
  };
}

function transformCategory(raw: SystemLogCategoryRaw): SystemLogCategory {
  return {
    code: raw.code,
    name: raw.name,
    description: raw.description,
    fileCount: raw.file_count,
    totalSize: raw.total_size,
    totalSizeFormatted: formatFileSize(raw.total_size),
  };
}

function transformFile(raw: SystemLogFileRaw): SystemLogFile {
  return {
    filename: raw.name,
    category: raw.category,
    size: raw.size,
    sizeFormatted: formatFileSize(raw.size),
    modifiedAt: raw.modified_at,
    isCurrent: raw.is_current,
  };
}

function transformContentItem(
  raw: SystemLogContentItemRaw,
): SystemLogContentItem {
  return {
    content: raw.content,
    fileName: raw.file_name,
    lineNumber: raw.line_number,
  };
}

function transformContent(raw: SystemLogContentRaw): SystemLogContent {
  return {
    filename: raw.filename,
    category: raw.category,
    scope: raw.scope,
    lines: raw.lines,
    items: raw.items.map((item) => transformContentItem(item)),
    totalLines: raw.total_lines,
    totalEntries: raw.total_entries,
    searchedFiles: raw.searched_files,
    page: raw.page,
    pageSize: raw.page_size,
    hasMore: raw.has_more,
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/admin/system-logs';

/**
 * Get system log statistics / 获取系统日志统计
 * GET /admin/system-logs/stats
 */
export async function getSystemLogStatsApi(
  options?: ApiRequestOptions,
): Promise<SystemLogStats> {
  const raw = await requestClient.get<SystemLogStatsRaw>(
    `${API_PREFIX}/stats`,
    options,
  );
  return transformStats(raw);
}

/**
 * Get log category list / 获取日志分类列表
 * GET /admin/system-logs/categories
 */
export async function getSystemLogCategoriesApi(
  options?: ApiRequestOptions,
): Promise<SystemLogCategory[]> {
  const raw = await requestClient.get<SystemLogCategoryRaw[]>(
    `${API_PREFIX}/categories`,
    options,
  );
  return raw.map((item) => transformCategory(item));
}

/**
 * Get log file list / 获取日志文件列表
 * GET /admin/system-logs/files
 */
export async function getSystemLogFilesApi(
  params?: { category?: string },
  options?: ApiRequestOptions,
): Promise<SystemLogFile[]> {
  const raw = await requestClient.get<SystemLogFileRaw[]>(
    `${API_PREFIX}/files`,
    { params, ...options },
  );
  return raw.map((item) => transformFile(item));
}

/**
 * Get log file content / 获取日志文件内容
 * GET /admin/system-logs/files/{filename}/content
 */
export async function getSystemLogContentApi(
  filename: string,
  params?: GetSystemLogContentParams,
  options?: ApiRequestOptions,
): Promise<SystemLogContent> {
  const raw = await requestClient.get<SystemLogContentRaw>(
    `${API_PREFIX}/files/${encodeURIComponent(filename)}/content`,
    { params, ...options },
  );
  return transformContent(raw);
}

/**
 * Download log file / 下载日志文件
 * GET /admin/system-logs/files/{filename}/download
 */
export async function downloadSystemLogFileApi(
  filename: string,
  options?: ApiRequestOptions,
): Promise<void> {
  const blob = await requestClient.download<Blob>(
    `${API_PREFIX}/files/${encodeURIComponent(filename)}/download`,
    options,
  );
  downloadBlob(blob, { filename });
}

/**
 * Delete log file / 删除日志文件
 * DELETE /admin/system-logs/files/{filename}
 */
export async function deleteSystemLogFileApi(
  filename: string,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(
    `${API_PREFIX}/files/${encodeURIComponent(filename)}`,
    options,
  );
}
