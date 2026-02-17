/**
 * 租户插件管理 - 辅助函数
 */
import {
  getPluginTypeColor,
  getPluginTypeText as _getPluginTypeText,
} from '#/utils/plugin-helpers';

export { getPluginTypeColor };

const I18N_PREFIX = 'tenant.plugin';

/**
 * 获取插件类型文本
 */
export function getPluginTypeText(type: string | undefined): string {
  return _getPluginTypeText(type, I18N_PREFIX);
}
