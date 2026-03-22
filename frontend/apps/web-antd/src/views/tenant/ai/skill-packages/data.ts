/**
 * Skill package view helpers (tenant)
 * 技能包页面辅助函数（企业端）
 */
import { $t } from '#/locales';

export function getPackageRoleColor(roleKey: null | string | undefined): string {
  switch (roleKey) {
    case 'platform_system': {
      return 'gold';
    }
    case 'plugin_managed': {
      return 'geekblue';
    }
    case 'tenant_owned': {
      return 'green';
    }
    case 'platform_catalog': {
      return 'purple';
    }
    default: {
      return 'default';
    }
  }
}

export function getPackageRoleText(roleKey: null | string | undefined): string {
  const key = roleKey || 'platform_catalog';
  return $t(`tenant.ai.skillPackage.roleOptions.${key}`);
}

export function getRuntimeBindingModeColor(
  mode: null | string | undefined,
): string {
  switch (mode) {
    case 'direct_agent_skill_grant': {
      return 'cyan';
    }
    default: {
      return 'default';
    }
  }
}

export function getRuntimeBindingModeText(
  mode: null | string | undefined,
): string {
  const key = mode || 'direct_agent_skill_grant';
  return $t(`tenant.ai.skillPackage.runtimeBindingOptions.${key}`);
}

export function getSourceSummaryText(
  summary: null | string | undefined,
  sourcePlugin?: null | string,
): string {
  if (!summary) {
    return $t('tenant.ai.skillPackage.sourceSummaryOptions.platform_catalog');
  }

  if (summary.startsWith('plugin:')) {
    return $t('tenant.ai.skillPackage.sourceSummaryValue.plugin', {
      plugin: sourcePlugin || summary.replace(/^plugin:/, ''),
    });
  }

  if (summary.startsWith('tenant:')) {
    return $t('tenant.ai.skillPackage.sourceSummaryValue.tenant', {
      tenantId: summary.replace(/^tenant:/, ''),
    });
  }

  return $t(`tenant.ai.skillPackage.sourceSummaryOptions.${summary.replace(':', '_')}`);
}

export function getSkillTypeText(type: null | string | undefined): string {
  if (!type) {
    return '-';
  }
  return $t(`tenant.ai.skill.type_options.${type}`);
}
