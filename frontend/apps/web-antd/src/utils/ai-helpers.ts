/**
 * AI 模块共享工具函数（admin/tenant 通用）
 *
 * 纯逻辑映射，无 i18n 依赖。
 * NOTE: getScopeColor/getScopeText 已迁移到 scope-helpers.ts，请勿在此添加 scope 相关函数。
 */

/** 技能类型颜色映射 */
export function getSkillTypeColor(type: string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'default';
    }
    case 'code_execution': {
      return 'purple';
    }
    case 'data_intelligence': {
      return 'blue';
    }
    case 'email': {
      return 'cyan';
    }
    case 'http': {
      return 'orange';
    }
    case 'knowledge_base': {
      return 'green';
    }
    case 'toolkit': {
      return 'volcano';
    }
    default: {
      return 'default';
    }
  }
}

/** 技能类型图标映射 */
export function getSkillTypeIcon(type: string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'lucide:cpu';
    }
    case 'code_execution': {
      return 'lucide:terminal';
    }
    case 'data_intelligence': {
      return 'lucide:database';
    }
    case 'email': {
      return 'lucide:mail';
    }
    case 'http': {
      return 'lucide:globe';
    }
    case 'knowledge_base': {
      return 'lucide:book-open';
    }
    case 'toolkit': {
      return 'lucide:wrench';
    }
    default: {
      return 'lucide:sparkles';
    }
  }
}
