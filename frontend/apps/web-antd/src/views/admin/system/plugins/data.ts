/**
 * 平台插件管理 - 辅助函数
 */
import { $t } from '#/locales';
import {
  getPluginTypeColor,
  getPluginTypeText as _getPluginTypeText,
  getStatusColor,
  getStatusText as _getStatusText,
} from '#/utils/plugin-helpers';

export { getPluginTypeColor, getStatusColor };

const I18N_PREFIX = 'admin.plugin';

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
  return _getPluginTypeText(type, I18N_PREFIX);
}

/**
 * 获取插件状态文本
 */
export function getStatusText(status: string | undefined): string {
  return _getStatusText(status, I18N_PREFIX);
}
