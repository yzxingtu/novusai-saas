/**
 * 插件管理 — 列定义、搜索、辅助函数
 */
import type { VxeTableGridOptions } from '#/adapter/vxe-table';

import { searchInput } from '#/adapter/form';
import { $t } from '#/locales';

/** 状态颜色映射 */
export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    installed: 'blue',
    enabled: 'success',
    disabled: 'default',
    error: 'error',
  };
  return map[status] || 'default';
}

/** 状态文本 */
export function getStatusText(status: string): string {
  return $t(`admin.plugin.status_options.${status}`) || status;
}

/** 作用域文本 */
export function getScopeText(scope: string): string {
  return $t(`admin.plugin.scope_options.${scope}`) || scope;
}

/** 信任等级颜色 */
export function getTierColor(tier: string): string {
  const map: Record<string, string> = {
    official: 'purple',
    verified: 'blue',
    community: 'default',
  };
  return map[tier] || 'default';
}

/** 信任等级文本 */
export function getTierText(tier: string): string {
  return $t(`admin.plugin.tier_options.${tier}`) || tier;
}

/** 从 manifest.extensions 派生插件类型 */
export function derivePluginType(manifest: Record<string, unknown> | null | undefined): string {
  if (!manifest) return 'basic';
  const ext = (manifest.extensions || {}) as Record<string, unknown>;
  const types: string[] = [];
  if (ext.skills && (ext.skills as unknown[]).length > 0) types.push('skill');
  if (ext.hooks && (ext.hooks as unknown[]).length > 0) types.push('hook');
  if (ext.api) types.push('api');
  if (ext.webhooks && (ext.webhooks as unknown[]).length > 0) types.push('webhook');
  if (ext.events && (ext.events as unknown[]).length > 0) types.push('event');
  if (types.length === 0) return 'basic';
  if (types.length > 1) return 'composite';
  return types[0] || 'basic';
}

/** 插件类型颜色 */
export function getTypeColor(type: string): string {
  const map: Record<string, string> = {
    skill: 'purple',
    hook: 'cyan',
    api: 'blue',
    webhook: 'orange',
    event: 'geekblue',
    composite: 'volcano',
    basic: 'default',
  };
  return map[type] || 'default';
}

/** 插件类型图标 */
export function getTypeIcon(type: string): string {
  const map: Record<string, string> = {
    skill: 'lucide:brain',
    hook: 'lucide:anchor',
    api: 'lucide:plug',
    webhook: 'lucide:webhook',
    event: 'lucide:radio',
    composite: 'lucide:layers',
    basic: 'lucide:puzzle',
  };
  return map[type] || 'lucide:puzzle';
}

/** 插件类型文本 */
export function getTypeText(type: string): string {
  return $t(`admin.plugin.type_options.${type}`) || type;
}

/** 插件类型列表（用于筛选） */
export const PLUGIN_TYPES = [
  'skill', 'hook', 'api', 'webhook', 'event', 'composite', 'basic',
] as const;

/** 列定义 */
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    { field: 'display_name', title: $t('admin.plugin.displayName'), minWidth: 200 },
    { field: 'version', title: $t('admin.plugin.versionLabel'), width: 100 },
    { field: 'scope', title: $t('admin.plugin.scope'), width: 140 },
    { field: 'status', title: $t('admin.plugin.status'), width: 100 },
    { field: 'tier', title: $t('admin.plugin.tier'), width: 100 },
    { field: 'install_source', title: $t('admin.plugin.installSource'), width: 120 },
    { field: 'installed_at', title: $t('admin.plugin.installedAt'), width: 160 },
    { field: 'action', title: '', width: 200, fixed: 'right' },
  ];
}

/** 搜索 Schema */
export function useGridFormSchema() {
  return [
    searchInput('display_name', $t('admin.plugin.placeholder.searchName')),
  ];
}
