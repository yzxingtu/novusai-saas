/**
 * 租户插件管理 - 辅助函数
 */
import { $t } from '#/locales';

/**
 * 获取插件类型文本
 */
export function getPluginTypeText(type: string | undefined): string {
  if (!type) return '-';
  const key = `tenant.plugin.type_options.${type}`;
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
