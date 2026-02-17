/**
 * 插件类型/状态辅助函数（admin/tenant 共享）
 */
import { $t } from '#/locales';

/**
 * 获取插件类型颜色（纯逻辑，无 i18n 依赖）
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
 * 获取插件类型文本（通过 i18nPrefix 参数适配 admin/tenant）
 */
export function getPluginTypeText(
  type: string | undefined,
  i18nPrefix: string,
): string {
  if (!type) return '-';
  const key = `${i18nPrefix}.type_options.${type}`;
  const text = $t(key);
  return text === key ? type : text;
}

/**
 * 获取插件状态颜色（纯逻辑，无 i18n 依赖）
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
 * 获取插件状态文本（通过 i18nPrefix 参数适配 admin/tenant）
 */
export function getStatusText(
  status: string | undefined,
  i18nPrefix: string,
): string {
  if (!status) return '-';
  const key = `${i18nPrefix}.status_options.${status}`;
  const text = $t(key);
  return text === key ? status : text;
}
