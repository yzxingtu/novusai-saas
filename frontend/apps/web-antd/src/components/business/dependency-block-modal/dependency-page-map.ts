import { router } from '#/router';

type DependencyScope = 'admin' | 'tenant';

const dependencyPageMap: Record<
  string,
  Partial<Record<DependencyScope, string>>
> = {
  ai_model: {
    admin: '/admin/ai/models',
    tenant: '/tenant/ai/models',
  },
  ai_provider: {
    admin: '/admin/ai/providers',
  },
  provider_api_key: {
    admin: '/admin/ai/api-keys',
  },
  agent: {
    admin: '/admin/ai/agents',
    tenant: '/tenant/ai/agents',
  },
  agent_access: {
    admin: '/admin/ai/agents',
    tenant: '/tenant/ai/agents',
  },
  agent_conversation: {
    admin: '/admin/ai/conversations',
    tenant: '/tenant/ai/conversations',
  },
  agent_version: {
    admin: '/admin/ai/agents',
    tenant: '/tenant/ai/agents',
  },
  knowledge_base: {
    admin: '/admin/ai/knowledge-bases',
    tenant: '/tenant/ai/knowledge-bases',
  },
  knowledge_document: {
    admin: '/admin/ai/knowledge-bases',
    tenant: '/tenant/ai/knowledge-bases',
  },
  skill_package: {
    admin: '/admin/ai/skill-packages',
  },
  skill: {
    admin: '/admin/ai/skill-packages',
  },
  tenant_quota: {
    admin: '/admin/ai/quotas',
    tenant: '/tenant/ai/quotas',
  },
  tenant_rate_limit: {
    admin: '/admin/ai/quotas',
    tenant: '/tenant/ai/quotas',
  },
  system_agent_assignment: {
    admin: '/admin/ai/agent-assignments',
  },
  tenant_plugin: {
    admin: '/admin/plugins',
  },
  codegen_config_version: {
    admin: '/admin/system/codegen',
  },
  tenant_plan: {
    admin: '/admin/tenant/plans',
  },
  tenant_domain: {
    tenant: '/tenant/system-mgmt/domains',
  },
};

function resolveScope(): DependencyScope {
  const currentPath = String(router.currentRoute.value?.path || '').trim();
  return currentPath.startsWith('/tenant') ? 'tenant' : 'admin';
}

export function resolveDependencyPagePath(type: string): null | string {
  const normalizedType = String(type || '').trim();
  if (!normalizedType) {
    return null;
  }
  const scopedPath = dependencyPageMap[normalizedType]?.[resolveScope()];
  if (scopedPath) {
    return scopedPath;
  }
  return dependencyPageMap[normalizedType]?.admin ?? null;
}
