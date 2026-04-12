/**
 * Page AI capability keys, mode normalization, and policy-based operation filtering.
 * 页面 AI 能力键、模式规范化，以及按策略过滤可用操作（含 navigation_only 白名单）。
 */

import type { AIPageMode } from '@vben/types';

import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-types';

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
  | 'submit';

export const NAVIGATION_ONLY_OPERATION_NAMES = new Set([
  'ui_get_snapshot',
  'ui_list_interactables',
  'ui_read_region',
  'ui_read_table',
]);

export interface PageAIPolicyLike {
  disabledCapabilities?: string | string[];
  disabledOperations?: string | string[];
  mode?: AIPageMode;
}

// Disabled capability → concrete operation names to hide / 禁用的能力 → 对应要隐藏的操作名

const CAPABILITY_TO_OPERATION_NAMES: Record<
  Exclude<PageAICapabilityKey, 'context' | 'custom'>,
  string[]
> = {
  content: ['ui_get_snapshot', 'ui_read_region'],
  detail: ['ui_open_surface', 'ui_click'],
  editor: [
    'ui_click',
    'ui_set_field',
    'ui_fill_form',
    'ui_submit_form',
    'ui_get_form_state',
  ],
  form: [
    'ui_get_form_state',
    'ui_set_field',
    'ui_fill_form',
    'ui_submit_form',
  ],
  list_read: ['ui_get_snapshot', 'ui_read_table', 'ui_read_region'],
  pagination: ['ui_click', 'ui_open_surface'],
  search: ['ui_set_field', 'ui_fill_form', 'ui_click'],
  submit: ['ui_submit_form'],
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
  ]);
  return normalizeStringList(values).filter(
    (item): item is PageAICapabilityKey =>
      allowed.has(item as PageAICapabilityKey),
  );
}

export function normalizeOperationNames(values?: string | string[]): string[] {
  return normalizeStringList(values);
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
    if (capability === 'context' || capability === 'custom') {
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

// --- Apply policy to operation descriptors / 将策略应用到操作描述列表 ---

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
