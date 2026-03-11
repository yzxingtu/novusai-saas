/**
 * Common utility functions
 * 通用工具函数
 */

// ============================================================
// Random code generation / 随机编码生成
// ============================================================

/** Character set excluding easily confused characters / 排除易混淆字符的字符集 */
// ============================================================
// Tree expand state management / 树形展开状态管理
// ============================================================

import type { Ref } from 'vue';

import { ref } from 'vue';

// ============================================================
// Delete confirmation dialog / 删除确认弹窗
// ============================================================
import { message, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

// cspell:disable-next-line
const SAFE_CHARS = {
  /** Lowercase letters (excluding l, o) / 小写字母（排除 l, o） */
  lowercase: 'abcdefghjkmnpqrstuvwxyz', // cspell:disable-line
  /** Uppercase letters (excluding I, L, O) / 大写字母（排除 I, L, O） */
  uppercase: 'ABCDEFGHJKMNPQRSTUVWXYZ', // cspell:disable-line
  /** Numbers (excluding 0, 1) / 数字（排除 0, 1） */
  numbers: '23456789',
};

/** Random code generation options / 随机编码生成选项 */
export interface GenerateCodeOptions {
  /** Code length, default 8 / 编码长度，默认 8 */
  length?: number;
  /** Include uppercase letters, default true / 是否包含大写字母，默认 true */
  uppercase?: boolean;
  /** Include lowercase letters, default true / 是否包含小写字母，默认 true */
  lowercase?: boolean;
  /** Include numbers, default true / 是否包含数字，默认 true */
  numbers?: boolean;
  /** Add separator (-), default false / 是否添加分隔符（-），默认 false */
  separator?: boolean;
  /** Separator interval (characters between separators), default 4 / 分隔符间隔（每隔多少位添加分隔符），默认 4 */
  separatorInterval?: number;
  /** Custom separator character, default '-' / 自定义分隔符，默认 '-' */
  separatorChar?: string;
  /** Prefix / 前缀 */
  prefix?: string;
  /** Suffix / 后缀 */
  suffix?: string;
}

/**
 * Generate random code
 * Excludes easily confused characters: 0, O, o, 1, I, l, L
 * 生成随机编码
 * 排除易混淆字符：0, O, o, 1, I, l, L
 *
 * @param options - Generation options / 生成选项
 * @returns Random code string / 随机编码字符串
 *
 * @example
 * // 默认 8 位混合编码
 * generateCode() // 'A3Km9Xp7'
 *
 * // 指定长度
 * generateCode({ length: 12 }) // 'A3Km9Xp7B2Hn'
 *
 * // 仅小写字母
 * generateCode({ length: 6, uppercase: false, numbers: false }) // 'abcdef'
 *
 * // 带分隔符
 * generateCode({ length: 16, separator: true }) // 'A3Km-9Xp7-B2Hn-4Qrs'
 *
 * // 带前缀
 * generateCode({ length: 8, prefix: 'ORD-' }) // 'ORD-A3Km9Xp7'
 */
export function generateCode(options: GenerateCodeOptions = {}): string {
  const {
    length = 8,
    uppercase = true,
    lowercase = true,
    numbers = true,
    separator = false,
    separatorInterval = 4,
    separatorChar = '-',
    prefix = '',
    suffix = '',
  } = options;

  // 构建字符集
  let charset = '';
  if (lowercase) charset += SAFE_CHARS.lowercase;
  if (uppercase) charset += SAFE_CHARS.uppercase;
  if (numbers) charset += SAFE_CHARS.numbers;

  // 如果没有选择任何字符类型，使用全部
  if (!charset) {
    charset = SAFE_CHARS.lowercase + SAFE_CHARS.uppercase + SAFE_CHARS.numbers;
  }

  // 生成随机字符
  let code = '';
  const charsetLength = charset.length;

  // 使用 crypto API 生成更安全的随机数（如果可用）
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const randomValues = new Uint32Array(length);
    crypto.getRandomValues(randomValues);
    for (let i = 0; i < length; i++) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      code += charset[randomValues[i]! % charsetLength];
    }
  } else {
    // 降级到 Math.random
    for (let i = 0; i < length; i++) {
      code += charset[Math.floor(Math.random() * charsetLength)];
    }
  }

  // 添加分隔符
  if (separator && separatorInterval > 0) {
    const parts: string[] = [];
    for (let i = 0; i < code.length; i += separatorInterval) {
      parts.push(code.slice(i, i + separatorInterval));
    }
    code = parts.join(separatorChar);
  }

  return `${prefix}${code}${suffix}`;
}

/**
 * Generate UUID v4 format code
 * Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
 * 生成 UUID v4 格式的编码
 * 格式：xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
 *
 * @returns UUID string / UUID 字符串
 */
export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  // 降级实现
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replaceAll(/[xy]/g, (c) => {
    const r = Math.trunc(Math.random() * 16);
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// ============================================================
// Date/time formatting / 时间格式化
// ============================================================

/** Date format options / 日期格式化选项 */
export interface FormatDateOptions {
  /** Format template, default 'YYYY-MM-DD HH:mm:ss' / 格式模板，默认 'YYYY-MM-DD HH:mm:ss' */
  format?: string;
  /** Null value display, default '-' / 空值显示，默认 '-' */
  fallback?: string;
}

/**
 * Format date/time
 * 格式化日期时间
 *
 * @param date - Date value (Date object, timestamp, ISO string) / 日期值（Date对象、时间戳、ISO字符串）
 * @param options - Format options / 格式化选项
 * @returns Formatted string / 格式化后的字符串
 *
 * Supported format placeholders / 支持的格式占位符：
 * - YYYY: 4-digit year / 四位年份
 * - YY: 2-digit year / 两位年份
 * - MM: 2-digit month (01-12) / 两位月份（01-12）
 * - M: month (1-12) / 月份（1-12）
 * - DD: 2-digit day (01-31) / 两位日期（01-31）
 * - D: day (1-31) / 日期（1-31）
 * - HH: 24h hours (00-23) / 24小时制小时（00-23）
 * - H: 24h hours (0-23) / 24小时制小时（0-23）
 * - hh: 12h hours (01-12) / 12小时制小时（01-12）
 * - h: 12h hours (1-12) / 12小时制小时（1-12）
 * - mm: minutes (00-59) / 分钟（00-59）
 * - m: minutes (0-59) / 分钟（0-59）
 * - ss: seconds (00-59) / 秒（00-59）
 * - s: seconds (0-59) / 秒（0-59）
 * - A: AM/PM
 * - a: am/pm
 *
 * @example
 * formatDate('2026-01-14T10:30:00') // '2026-01-14 10:30:00'
 * formatDate('2026-01-14', { format: 'YYYY年MM月DD日' }) // '2026年01月14日'
 * formatDate(null) // '-'
 */
export function formatDate(
  date: Date | null | number | string | undefined,
  options: FormatDateOptions | string = {},
): string {
  // 支持直接传入格式字符串
  const opts: FormatDateOptions =
    typeof options === 'string' ? { format: options } : options;
  const { format = 'YYYY-MM-DD HH:mm:ss', fallback = '-' } = opts;

  if (!date) return fallback;

  const d = date instanceof Date ? date : new Date(date);

  // 检查日期有效性
  if (Number.isNaN(d.getTime())) return fallback;

  const year = d.getFullYear();
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hours = d.getHours();
  const minutes = d.getMinutes();
  const seconds = d.getSeconds();
  const hours12 = hours % 12 || 12;

  const pad = (n: number): string => n.toString().padStart(2, '0');

  const replacements: Record<string, string> = {
    YYYY: year.toString(),
    YY: year.toString().slice(-2),
    MM: pad(month),
    M: month.toString(),
    DD: pad(day),
    D: day.toString(),
    HH: pad(hours),
    H: hours.toString(),
    hh: pad(hours12),
    h: hours12.toString(),
    mm: pad(minutes),
    m: minutes.toString(),
    ss: pad(seconds),
    s: seconds.toString(),
    A: hours < 12 ? 'AM' : 'PM',
    a: hours < 12 ? 'am' : 'pm',
  };

  // 按长度降序排列 key，确保先替换长的（如 YYYY 优先于 YY）
  const sortedKeys = Object.keys(replacements).toSorted(
    (a, b) => b.length - a.length,
  );

  let result = format;
  for (const key of sortedKeys) {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    result = result.replaceAll(new RegExp(key, 'g'), replacements[key]!);
  }

  return result;
}

/**
 * Format as date only (without time)
 * 格式化为日期（不含时间）
 * @param date - Date value / 日期值
 * @param fallback - Null value display / 空值显示
 */
export function formatDateOnly(
  date: Date | null | number | string | undefined,
  fallback = '-',
): string {
  return formatDate(date, { format: 'YYYY-MM-DD', fallback });
}

/**
 * Format as time only (without date)
 * 格式化为时间（不含日期）
 * @param date - Date value / 日期值
 * @param fallback - Null value display / 空值显示
 */
export function formatTimeOnly(
  date: Date | null | number | string | undefined,
  fallback = '-',
): string {
  return formatDate(date, { format: 'HH:mm:ss', fallback });
}

/**
 * Format as relative time (e.g., just now, 5 minutes ago, yesterday)
 * 格式化为相对时间（如：刚刚、5分钟前、昨天）
 *
 * @param date - Date value / 日期值
 * @param fallback - Null value display / 空值显示
 * @returns Relative time string / 相对时间字符串
 *
 * @example
 * formatRelativeTime(new Date()) // '刚刚'
 * formatRelativeTime(Date.now() - 5 * 60 * 1000) // '5 分钟前'
 * formatRelativeTime('2026-01-13') // '1 天前'
 */
export function formatRelativeTime(
  date: Date | null | number | string | undefined,
  fallback = '-',
): string {
  if (!date) return fallback;

  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return fallback;

  const now = Date.now();
  const diff = now - d.getTime();
  const absDiff = Math.abs(diff);

  const seconds = Math.floor(absDiff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  const suffix = diff > 0 ? '前' : '后';

  if (seconds < 60) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟${suffix}`;
  if (hours < 24) return `${hours} 小时${suffix}`;
  if (days < 30) return `${days} 天${suffix}`;
  if (months < 12) return `${months} 个月${suffix}`;
  return `${years} 年${suffix}`;
}

// ============================================================
// Other common utilities / 其他常用工具
// ============================================================

/**
 * Copy text to clipboard
 * 复制文本到剪贴板
 * @param text - Text to copy / 要复制的文本
 * @returns Whether successful / 是否成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    // 降级方案
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.append(textarea);
    textarea.select();
    const success = document.execCommand('copy');
    textarea.remove();
    return success;
  } catch {
    return false;
  }
}

/**
 * Debounce function
 * 防抖函数
 * @param fn - Function to execute / 要执行的函数
 * @param delay - Delay in milliseconds / 延迟时间（毫秒）
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  let timer: null | ReturnType<typeof setTimeout> = null;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Throttle function
 * 节流函数
 * @param fn - Function to execute / 要执行的函数
 * @param delay - Interval in milliseconds / 间隔时间（毫秒）
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  let last = 0;
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - last >= delay) {
      last = now;
      fn(...args);
    }
  };
}

// ============================================================
// Tree data processing / 树形数据处理
// ============================================================

/** Tree node base interface / 树节点基础接口 */
export interface TreeNodeBase {
  id: number;
  parentId?: null | number;
  sortOrder?: number;
}

/** buildTree configuration options / buildTree 配置选项 */
export interface BuildTreeOptions<T> {
  /** Sort field, default 'sortOrder' / 排序字段，默认 'sortOrder' */
  sortField?: keyof T;
  /** Children field name, default 'children' / 子节点字段名，默认 'children' */
  childrenField?: string;
}

/**
 * Build flat data into tree structure
 * 将扁平数据构建为树形结构
 *
 * @param items - Flat data array / 扁平数据数组
 * @param options - Configuration options / 配置选项
 * @returns Tree structure array / 树形结构数组
 *
 * @example
 * const flat = [
 *   { id: 1, parentId: null, name: 'Root' },
 *   { id: 2, parentId: 1, name: 'Child' },
 * ];
 * const tree = buildTree(flat);
 * // [{ id: 1, parentId: null, name: 'Root', children: [{ id: 2, ... }] }]
 */
export function buildTree<T extends TreeNodeBase>(
  items: T[],
  options: BuildTreeOptions<T> = {},
): (T & { children: (T & { children: any[] })[] })[] {
  const { sortField = 'sortOrder' as keyof T, childrenField = 'children' } =
    options;

  // 使用 Record 类型以支持动态字段名
  type TreeNode = Record<string, any> & T;
  const map = new Map<number, TreeNode>();
  const roots: TreeNode[] = [];

  // 创建所有节点的映射
  for (const item of items) {
    const node: TreeNode = { ...item, [childrenField]: [] };
    map.set(item.id, node);
  }

  // 构建树形结构
  for (const item of items) {
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const node = map.get(item.id)!;
    if (item.parentId && map.has(item.parentId)) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const parent = map.get(item.parentId)!;
      (parent[childrenField] as TreeNode[]).push(node);
    } else {
      roots.push(node);
    }
  }

  // 递归排序
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      const aVal = (a[sortField] as number) ?? 0;
      const bVal = (b[sortField] as number) ?? 0;
      return aVal - bVal;
    });
    for (const node of nodes) {
      sortNodes(node[childrenField] as TreeNode[]);
    }
  };
  sortNodes(roots);

  return roots as (T & { children: (T & { children: any[] })[] })[];
}

/** useTreeExpand return type / useTreeExpand 返回类型 */
export interface TreeExpandReturn {
  /** Set of expanded node IDs / 展开的节点 ID 集合 */
  expandedIds: Ref<Set<number>>;
  /** Toggle expand state of a node / 切换指定节点的展开状态 */
  toggle: (id: number) => void;
  /** Expand all nodes / 展开所有节点 */
  expandAll: () => void;
  /** Collapse all nodes / 折叠所有节点 */
  collapseAll: () => void;
  /** Check if a node is expanded / 判断节点是否展开 */
  isExpanded: (id: number) => boolean;
}

/**
 * Tree expand state management Hook
 * 树形展开状态管理 Hook
 *
 * @param getItems - Function to get all nodes (returns array with id) / 获取所有节点的函数（返回包含 id 的数组）
 * @param defaultExpanded - Whether to expand all by default, default true / 是否默认展开所有，默认 true
 * @returns Expand state management methods / 展开状态管理方法
 *
 * @example
 * const roles = ref<Role[]>([]);
 * const { expandedIds, toggle, expandAll, collapseAll, isExpanded } =
 *   useTreeExpand(() => roles.value);
 */
export function useTreeExpand<T extends { id: number }>(
  getItems: () => T[],
  defaultExpanded = true,
): TreeExpandReturn {
  const expandedIds = ref<Set<number>>(new Set()) as Ref<Set<number>>;

  // 初始化时如果需要默认展开
  if (defaultExpanded) {
    const items = getItems();
    if (items.length > 0) {
      expandedIds.value = new Set(items.map((item) => item.id));
    }
  }

  function toggle(id: number) {
    const newSet = new Set(expandedIds.value);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    expandedIds.value = newSet;
  }

  function expandAll() {
    expandedIds.value = new Set(getItems().map((item) => item.id));
  }

  function collapseAll() {
    expandedIds.value = new Set();
  }

  function isExpanded(id: number) {
    return expandedIds.value.has(id);
  }

  return {
    expandedIds,
    toggle,
    expandAll,
    collapseAll,
    isExpanded,
  };
}

/** confirmDelete configuration options / confirmDelete 配置选项 */
export interface ConfirmDeleteOptions<T> {
  /** Data row to delete / 要删除的数据行 */
  row: T;
  /** Field for display name / 显示名称的字段 */
  nameField: keyof T;
  /** Name title (for prompt), e.g. 'role name' / 名称标题（用于提示），如 '角色名' */
  nameTitle?: string;
  /** Delete API function / 删除 API 函数 */
  deleteApi: (id: number) => Promise<unknown>;
  /** Field to get ID, default 'id' / 获取 ID 的字段，默认 'id' */
  idField?: keyof T;
  /** Callback after successful deletion / 删除成功后的回调 */
  onSuccess?: () => void;
  /** i18n prefix for custom messages / i18n 前缀，用于自定义文案 */
  i18nPrefix?: string;
}

/**
 * Generic delete confirmation dialog
 * 通用删除确认弹窗
 *
 * @param options - Configuration options / 配置选项
 *
 * @example
 * confirmDelete({
 *   row: roleData,
 *   nameField: 'name',
 *   nameTitle: '角色名',
 *   deleteApi: (id) => deleteRoleApi(id),
 *   onSuccess: () => loadData(),
 * });
 */
export function confirmDelete<T extends Record<string, any>>(
  options: ConfirmDeleteOptions<T>,
): void {
  const {
    row,
    nameField,
    nameTitle = '',
    deleteApi,
    idField = 'id' as keyof T,
    onSuccess,
    i18nPrefix,
  } = options;

  const name = String(row[nameField] || '');
  const id = row[idField] as number;

  // 支持自定义 i18n 或使用通用文案
  const titleKey = i18nPrefix
    ? `${i18nPrefix}.messages.deleteTitle`
    : 'shared.common.deleteTitle';
  const confirmKey = i18nPrefix
    ? `${i18nPrefix}.messages.deleteConfirm`
    : 'shared.common.deleteConfirm';
  const deletingKey = i18nPrefix
    ? `${i18nPrefix}.messages.deleting`
    : 'shared.common.deleting';
  const successKey = i18nPrefix
    ? `${i18nPrefix}.messages.deleteSuccess`
    : 'shared.common.deleteSuccess';

  Modal.confirm({
    content: $t(confirmKey, { name, nameTitle }),
    okButtonProps: { danger: true },
    okText: $t('common.delete'),
    onOk: async () => {
      const hideLoading = message.loading({
        content: $t(deletingKey, { name }),
        duration: 0,
        key: 'delete_item',
      });
      try {
        await deleteApi(id);
        message.success({
          content: $t(successKey),
          key: 'delete_item',
        });
        onSuccess?.();
      } catch {
        hideLoading();
      }
    },
    title: $t(titleKey),
    type: 'warning',
  });
}

// ============================================================
// Level color configuration / 层级颜色配置
// ============================================================

/** Level color type / 层级颜色类型 */
export interface LevelColor {
  /** Left decoration bar color / 左侧装饰条颜色 */
  bar: string;
  /** Badge color / 徽章颜色 */
  badge: string;
}

/**
 * Default level color configuration
 * Uses different opacity variants of theme color to follow theme switching
 * 默认层级颜色配置
 * 使用主题色的不同透明度变体，确保跟随主题切换
 */
export const DEFAULT_LEVEL_COLORS: LevelColor[] = [
  { bar: 'bg-primary', badge: 'bg-primary/10 text-primary' },
  { bar: 'bg-primary/80', badge: 'bg-primary/8 text-primary/90' },
  { bar: 'bg-primary/60', badge: 'bg-primary/6 text-primary/80' },
  { bar: 'bg-primary/40', badge: 'bg-muted text-muted-foreground' },
];

/**
 * Get level color
 * 获取层级颜色
 *
 * @param level - Level (starting from 0) / 层级（从 0 开始）
 * @param colors - Custom color config, defaults to DEFAULT_LEVEL_COLORS / 自定义颜色配置，默认使用 DEFAULT_LEVEL_COLORS
 * @returns Color config for the level / 对应层级的颜色配置
 *
 * @example
 * getLevelColor(0) // { bar: 'bg-primary', badge: 'bg-primary/10 text-primary' }
 * getLevelColor(5) // 超出范围时返回最后一个颜色
 */
export function getLevelColor(
  level: number,
  colors: LevelColor[] = DEFAULT_LEVEL_COLORS,
): LevelColor {
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  return colors[Math.min(level, colors.length - 1)]!;
}
