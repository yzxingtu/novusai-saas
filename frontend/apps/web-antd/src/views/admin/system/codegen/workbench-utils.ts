import type {
  CodegenWorkbenchItem,
  CodegenWorkbenchSummary,
} from '#/api/admin/codegen';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getManifestStatusText } from './data';

export type WorkbenchFilterKey =
  | 'all'
  | 'applied'
  | 'attention'
  | 'draft'
  | 'generated'
  | 'rollback';

export type WorkbenchStat = {
  hint: string;
  icon: string;
  key: Exclude<WorkbenchFilterKey, 'all'>;
  label: string;
  tone: string;
  value: number;
};

export type WorkbenchFocusItem = {
  id: number;
  manifestPresent: boolean;
  message: string;
  name: string;
  resource: string;
  severity: 'error' | 'info' | 'warning';
  status: string;
};

const STATUS_FILTER_KEYS = ['draft', 'generated', 'applied'] as const;

export function isStatusWorkbenchFilter(
  key: WorkbenchFilterKey,
): key is (typeof STATUS_FILTER_KEYS)[number] {
  return STATUS_FILTER_KEYS.includes(
    key as (typeof STATUS_FILTER_KEYS)[number],
  );
}

export function buildWorkbenchItemMessage(item: CodegenWorkbenchItem): string {
  if (item.last_error) return item.last_error;
  if (item.delete_allowed === false && item.delete_reason_message) {
    return item.delete_reason_message;
  }
  if (item.last_generated_at) {
    return [
      getManifestStatusText(Boolean(item.manifest_present)),
      formatRelativeTime(item.last_generated_at) ||
        formatDate(item.last_generated_at) ||
        '—',
    ].join(' · ');
  }
  return $t('admin.system.codegen.workbench.neverGenerated');
}

export function getActionErrorMessage(
  error: unknown,
  fallback: string,
): string {
  const response = (
    error as {
      message?: string;
      response?: {
        data?: {
          detail?: string | { error?: string };
          message?: string;
        };
      };
    }
  )?.response?.data;

  if (typeof response?.message === 'string' && response.message.trim()) {
    return response.message;
  }
  if (typeof response?.detail === 'string' && response.detail.trim()) {
    return response.detail;
  }
  if (
    typeof response?.detail === 'object' &&
    typeof response.detail?.error === 'string' &&
    response.detail.error.trim()
  ) {
    return response.detail.error;
  }
  if (
    typeof (error as { message?: string })?.message === 'string' &&
    (error as { message?: string }).message?.trim()
  ) {
    return (error as { message?: string }).message as string;
  }
  return fallback;
}

export function toWorkbenchFocusItem(
  item: CodegenWorkbenchItem,
): WorkbenchFocusItem {
  let severity: WorkbenchFocusItem['severity'] = 'info';
  if (item.last_error) {
    severity = 'error';
  } else if (item.delete_allowed === false || !item.manifest_present) {
    severity = 'warning';
  }

  return {
    id: item.id,
    name: item.name,
    resource: item.resource,
    status: item.status,
    message: buildWorkbenchItemMessage(item),
    manifestPresent: Boolean(item.manifest_present),
    severity,
  };
}

export function getFocusSeverityIcon(
  severity: WorkbenchFocusItem['severity'],
): string {
  if (severity === 'error') return 'lucide:triangle-alert';
  if (severity === 'warning') return 'lucide:shield-alert';
  return 'lucide:circle-dot';
}

export function getFocusSeverityClasses(
  severity: WorkbenchFocusItem['severity'],
): string {
  if (severity === 'error') {
    return 'border-rose-200 bg-rose-50/80 text-rose-700';
  }
  if (severity === 'warning') {
    return 'border-amber-200 bg-amber-50/80 text-amber-700';
  }
  return 'border-slate-200 bg-slate-50/80 text-slate-700';
}

export function buildWorkbenchStats(
  summary: CodegenWorkbenchSummary | null,
): WorkbenchStat[] {
  const stats = summary?.stats;
  return [
    {
      key: 'draft',
      icon: 'lucide:file-pen-line',
      tone: 'text-slate-700 bg-slate-100',
      value: stats?.draft ?? 0,
      label: $t('admin.system.codegen.workbench.draft'),
      hint: $t('admin.system.codegen.workbench.draftHint'),
    },
    {
      key: 'generated',
      icon: 'lucide:sparkles',
      tone: 'text-sky-700 bg-sky-100',
      value: stats?.generated ?? 0,
      label: $t('admin.system.codegen.workbench.generated'),
      hint: $t('admin.system.codegen.workbench.generatedHint'),
    },
    {
      key: 'applied',
      icon: 'lucide:badge-check',
      tone: 'text-emerald-700 bg-emerald-100',
      value: stats?.applied ?? 0,
      label: $t('admin.system.codegen.workbench.applied'),
      hint: $t('admin.system.codegen.workbench.appliedHint'),
    },
    {
      key: 'rollback',
      icon: 'lucide:undo-2',
      tone: 'text-amber-700 bg-amber-100',
      value: stats?.rollback ?? 0,
      label: $t('admin.system.codegen.workbench.rollbackReady'),
      hint: $t('admin.system.codegen.workbench.rollbackReadyHint'),
    },
    {
      key: 'attention',
      icon: 'lucide:triangle-alert',
      tone: 'text-rose-700 bg-rose-100',
      value: stats?.attention ?? 0,
      label: $t('admin.system.codegen.workbench.attention'),
      hint: $t('admin.system.codegen.workbench.attentionHint'),
    },
  ];
}

export function buildWorkbenchIssues(
  summary: CodegenWorkbenchSummary | null,
): WorkbenchFocusItem[] {
  const items = summary?.sections.attention ?? [];
  return items.map((item) => toWorkbenchFocusItem(item));
}

export function getWorkbenchFilterConfig(
  key: WorkbenchFilterKey,
  stats: WorkbenchStat[],
) {
  if (key === 'all') {
    return {
      label: $t('admin.system.codegen.workbench.recentIssues'),
      hint: $t('admin.system.codegen.workbench.recentIssuesHint'),
      mode: 'default' as const,
    };
  }
  const stat = stats.find((item) => item.key === key);
  return {
    label: stat?.label ?? $t('admin.system.codegen.workbench.recentIssues'),
    hint: stat?.hint ?? $t('admin.system.codegen.workbench.recentIssuesHint'),
    mode: isStatusWorkbenchFilter(key)
      ? ('table' as const)
      : ('panel' as const),
  };
}

export function getActiveWorkbenchItems(
  summary: CodegenWorkbenchSummary | null,
  filter: WorkbenchFilterKey,
): WorkbenchFocusItem[] {
  switch (filter) {
    case 'applied':
    case 'draft':
    case 'generated': {
      return (summary?.sections[filter] ?? []).map((item) =>
        toWorkbenchFocusItem(item),
      );
    }
    case 'attention': {
      return buildWorkbenchIssues(summary);
    }
    case 'rollback': {
      return (summary?.sections.rollback ?? []).map((item) =>
        toWorkbenchFocusItem(item),
      );
    }
    default: {
      return buildWorkbenchIssues(summary);
    }
  }
}
