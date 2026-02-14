/**
 * 平台插件管理 - 辅助函数
 */
import { $t } from '#/locales';

/**
 * 插件类型选项
 */
export function getPluginTypeOptions() {
  return [
    { label: $t('admin.plugin.type_options.adapter'), value: 'adapter' },
    { label: $t('admin.plugin.type_options.tool'), value: 'tool' },
    { label: $t('admin.plugin.type_options.hook'), value: 'hook' },
    { label: $t('admin.plugin.type_options.api'), value: 'api' },
    { label: $t('admin.plugin.type_options.skill'), value: 'skill' },
    { label: $t('admin.plugin.type_options.composite'), value: 'composite' },
  ];
}

/**
 * 插件状态选项
 */
export function getStatusOptions() {
  return [
    { label: $t('admin.plugin.status_options.installed'), value: 'installed' },
    { label: $t('admin.plugin.status_options.enabled'), value: 'enabled' },
    { label: $t('admin.plugin.status_options.disabled'), value: 'disabled' },
    { label: $t('admin.plugin.status_options.error'), value: 'error' },
  ];
}

/**
 * 获取插件类型文本
 */
export function getPluginTypeText(type: string | undefined): string {
  if (!type) return '-';
  const key = `admin.plugin.type_options.${type}`;
  const text = $t(key);
  return text === key ? type : text;
}

/**
 * 获取插件类型颜色
 */
export function getPluginTypeColor(type: string | undefined): string {
  switch (type) {
    case 'adapter': return 'blue';
    case 'tool': return 'green';
    case 'hook': return 'orange';
    case 'api': return 'purple';
    case 'skill': return 'magenta';
    case 'composite': return 'cyan';
    default: return 'default';
  }
}

/**
 * 获取插件状态颜色
 */
export function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'enabled': return 'success';
    case 'installed':
    case 'disabled': return 'default';
    case 'error': return 'error';
    default: return 'default';
  }
}

/**
 * 获取插件状态文本
 */
export function getStatusText(status: string | undefined): string {
  if (!status) return '-';
  const key = `admin.plugin.status_options.${status}`;
  const text = $t(key);
  return text === key ? status : text;
}
