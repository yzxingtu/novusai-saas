/**
 * AI 模块共享工具函数（admin/tenant 通用）
 *
 * 纯逻辑映射，无 i18n 依赖。
 */

/** 作用域颜色映射 */
export function getScopeColor(scope: string): string {
  const map: Record<string, string> = {
    admin: 'blue',
    tenant: 'green',
    global: 'purple',
  };
  return map[scope] || 'default';
}

/** 技能类型颜色映射 */
export function getSkillTypeColor(type: string | undefined): string {
  switch (type) {
    case 'toolkit': return 'volcano';
    case 'knowledge_base': return 'green';
    case 'data_intelligence': return 'blue';
    case 'builtin': return 'default';
    default: return 'default';
  }
}

/** 技能类型图标映射 */
export function getSkillTypeIcon(type: string | undefined): string {
  switch (type) {
    case 'toolkit': return 'lucide:wrench';
    case 'knowledge_base': return 'lucide:book-open';
    case 'data_intelligence': return 'lucide:database';
    case 'builtin': return 'lucide:cpu';
    default: return 'lucide:sparkles';
  }
}
