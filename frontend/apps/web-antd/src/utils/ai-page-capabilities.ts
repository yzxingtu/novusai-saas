/**
 * Page AI capability keys, mode normalization, and policy-based operation filtering.
 * 页面 AI 能力键、模式规范化，以及按策略过滤可用操作（含 navigation_only 白名单）。
 */

import type { AIPageMode } from '@vben/types';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';

// --- Capability keys & navigation-only allowlist / 能力键与仅导航白名单 ---

export type PageAICapabilityKey =
  | 'content'
  | 'context'
  | 'custom'
  | 'detail'
  | 'editor'
  | 'form'
  | 'list_read'
  | 'pagination'
  | 'search'
  | 'submit'
  | 'table_policy';

export const NAVIGATION_ONLY_OPERATION_NAMES = new Set([
  'capture_screenshot',
  'list_available_menus',
  'navigate_menu',
  'read_current_sections',
  'read_current_view',
]);

export interface PageAIPolicyLike {
  disabledCapabilities?: string | string[];
  disabledOperations?: string | string[];
  mode?: AIPageMode;
}

export interface TablePolicySupportConfig {
  enabled: boolean;
  kind?: 'consumer' | 'management';
  relatedPolicyIds?: number[];
  relatedResources?: string[];
  relatedTables?: string[];
  supportedActions?: string[];
}

// Disabled capability → concrete operation names to hide / 禁用的能力 → 对应要隐藏的操作名

const CAPABILITY_TO_OPERATION_NAMES: Record<
  Exclude<PageAICapabilityKey, 'context' | 'custom' | 'table_policy'>,
  string[]
> = {
  content: ['read_current_sections', 'read_current_view'],
  detail: ['navigate_back', 'refresh_detail'],
  editor: [
    'append_content',
    'clear_formatting',
    'format_text',
    'get_editor_html',
    'get_editor_text',
    'get_selection',
    'insert_content',
    'insert_horizontal_rule',
    'insert_table',
    'manage_link',
    'redo',
    'replace_content',
    'replace_section',
    'select_all',
    'set_heading',
    'set_text_align',
    'toggle_blockquote',
    'toggle_code_block',
    'toggle_list',
    'undo',
    'update_title',
  ],
  form: [
    'create_record',
    'edit_record',
    'fill_form',
    'get_form_options',
    'get_form_state',
    'validate_form',
    'view_recycle_bin',
  ],
  list_read: [
    'export_data',
    'read_row_detail',
    'read_visible_rows',
    'refresh_list',
  ],
  pagination: ['go_to_page', 'next_page', 'prev_page', 'set_page_size'],
  search: ['clear_search', 'search'],
  submit: ['submit_form'],
};

// --- String / number list normalizers / 字符串与数字列表规范化 ---

function normalizeStringList(values?: string | string[]): string[] {
  if (!values) return [];
  if (Array.isArray(values)) {
    return [
      ...new Set(values.map((item) => String(item).trim()).filter(Boolean)),
    ];
  }
  return [
    ...new Set(
      String(values)
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

export function normalizePageAIMode(
  mode: AIPageMode | null | undefined,
  fallback: AIPageMode = 'operate',
): AIPageMode {
  return mode === 'disabled' ||
    mode === 'context_only' ||
    mode === 'navigation_only' ||
    mode === 'operate'
    ? mode
    : fallback;
}

export function normalizeCapabilityKeys(
  values?: string | string[],
): PageAICapabilityKey[] {
  const allowed = new Set<PageAICapabilityKey>([
    'content',
    'context',
    'custom',
    'detail',
    'editor',
    'form',
    'list_read',
    'pagination',
    'search',
    'submit',
    'table_policy',
  ]);
  return normalizeStringList(values).filter(
    (item): item is PageAICapabilityKey =>
      allowed.has(item as PageAICapabilityKey),
  );
}

export function normalizeOperationNames(values?: string | string[]): string[] {
  return normalizeStringList(values);
}

function normalizeNumberList(values?: number[]): number[] {
  if (!Array.isArray(values)) return [];
  const normalized = values.map(Number).filter((item) => Number.isFinite(item));
  return [...new Set(normalized)];
}

// --- Mode & capability queries / 模式与能力查询 ---

export function canExposePageOperations(mode: AIPageMode): boolean {
  return mode === 'operate' || mode === 'navigation_only';
}

export function shouldDisablePageContext(
  disabledCapabilities?: string | string[],
): boolean {
  return normalizeCapabilityKeys(disabledCapabilities).includes('context');
}

export function expandDisabledOperationsFromCapabilities(
  disabledCapabilities?: string | string[],
): string[] {
  const disabled = normalizeCapabilityKeys(disabledCapabilities);
  const operations = new Set<string>();

  for (const capability of disabled) {
    if (
      capability === 'context' ||
      capability === 'custom' ||
      capability === 'table_policy'
    ) {
      continue;
    }
    const mapped = CAPABILITY_TO_OPERATION_NAMES[capability];
    for (const operationName of mapped) {
      operations.add(operationName);
    }
  }

  return [...operations];
}

export function mergeDisabledOperations(input: {
  disabledCapabilities?: string | string[];
  disabledOperations?: string | string[];
  legacyDisabledOperations?: string | string[];
}): string[] {
  const merged = new Set<string>([
    ...expandDisabledOperationsFromCapabilities(input.disabledCapabilities),
    ...normalizeOperationNames(input.disabledOperations),
    ...normalizeOperationNames(input.legacyDisabledOperations),
  ]);
  return [...merged];
}

// --- Apply policy to registered operations / 将策略应用到已注册操作列表 ---

export function filterPageOperationsByPolicy<
  T extends Pick<PageOperation, 'name'>,
>(operations: readonly T[], policy: PageAIPolicyLike): T[] {
  const mode = normalizePageAIMode(policy.mode);
  if (!canExposePageOperations(mode)) {
    return [];
  }

  const disabledNames = new Set(
    mergeDisabledOperations({
      disabledCapabilities: policy.disabledCapabilities,
      disabledOperations: policy.disabledOperations,
    }),
  );

  return operations.filter((operation) => {
    if (disabledNames.has(operation.name)) {
      return false;
    }
    if (mode === 'navigation_only') {
      return NAVIGATION_ONLY_OPERATION_NAMES.has(operation.name);
    }
    return true;
  });
}

// Build optional page_data fragment for table-policy-aware pages / 构建表策略相关的 page_data 片段

export function buildTablePolicySupportData(
  config?: TablePolicySupportConfig,
): Record<string, unknown> | undefined {
  if (!config?.enabled) return undefined;

  const relatedPolicyIds = normalizeNumberList(config.relatedPolicyIds);
  const relatedResources = normalizeOperationNames(config.relatedResources);
  const relatedTables = normalizeOperationNames(config.relatedTables);
  const supportedActions = normalizeOperationNames(config.supportedActions);

  return {
    enabled: true,
    ...(config.kind ? { kind: config.kind } : {}),
    ...(supportedActions.length > 0
      ? { supported_actions: supportedActions }
      : {}),
    ...(relatedTables.length > 0 ? { related_tables: relatedTables } : {}),
    ...(relatedPolicyIds.length > 0
      ? { related_policy_ids: relatedPolicyIds }
      : {}),
    ...(relatedResources.length > 0
      ? { related_resources: relatedResources }
      : {}),
  };
}
