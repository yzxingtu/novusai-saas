/**
 * AI 模块共享工具函数（admin/tenant 通用）
 *
 * 纯逻辑映射，无 i18n 依赖。
 * NOTE: getScopeColor/getScopeText 已迁移到 scope-helpers.ts，请勿在此添加 scope 相关函数。
 */

/** 技能类型颜色映射 */
export function getSkillTypeColor(type: string | undefined): string {
  switch (type) {
    case 'toolkit': return 'volcano';
    case 'knowledge_base': return 'green';
    case 'data_intelligence': return 'blue';
    case 'builtin': return 'default';
    case 'http': return 'orange';
    case 'email': return 'cyan';
    case 'code_execution': return 'purple';
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
    case 'http': return 'lucide:globe';
    case 'email': return 'lucide:mail';
    case 'code_execution': return 'lucide:terminal';
    default: return 'lucide:sparkles';
  }
}
