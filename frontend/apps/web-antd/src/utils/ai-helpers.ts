/**
 * AI module shared utility functions (common for admin/tenant)
 * AI 模块共享工具函数（admin/tenant 通用）
 *
 * Pure logic mapping, no i18n dependency.
 * Provides color and icon mapping for skill types.
 * Scope-related utilities have been moved to scope-helpers.ts.
 * 纯逻辑映射，无 i18n 依赖。
 * 提供技能类型的颜色和图标映射。
 * scope 相关工具已迁移到 scope-helpers.ts
 *
 * NOTE: getScopeColor/getScopeText moved to scope-helpers.ts, do not add scope functions here.
 * 注意：getScopeColor/getScopeText 已迁移到 scope-helpers.ts，请勿在此添加 scope 相关函数。
 */

/**
 * Get the color corresponding to a skill type
 * 获取技能类型对应的颜色
 */
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

/**
 * Get the icon corresponding to a skill type
 * 获取技能类型对应的图标
 */
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
