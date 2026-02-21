/**
 * 管理端总回收站 — 搜索表单 & 列标签
 *
 * 每个模块使用 searchInput 构建轻量搜索 Schema（不引入原 CRUD data.ts，
 * 避免其 ApiSelect 在回收站上下文触发无关 API 请求）。
 * 租户级模块额外追加「所属租户」下拉。
 */
import type { VbenFormSchema } from '#/adapter/form';

import { searchInput, select, statusSelect } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

// ── 租户选择器 ──
function tenantSelect(): VbenFormSchema {
  return select('filter[tenant_id]', $t('admin.system.recycleBin.tenant'), {
    api: getTenantSelectApi,
    placeholder: $t('admin.system.recycleBin.allTenants'),
  });
}

// ── 各模块搜索 Schema ──
const TENANT_MODULES = new Set([
  'agents',
  'knowledge_bases',
  'skill_packages',
  'tenant_domains',
]);

type SchemaFactory = () => VbenFormSchema[];

const MODULE_SEARCH_SCHEMAS: Record<string, SchemaFactory> = {
  ai_providers: () => [
    searchInput('name', $t('admin.ai.provider.name')),
    searchInput('code', $t('admin.ai.provider.code')),
  ],
  ai_models: () => [
    searchInput('name', $t('admin.ai.model.name')),
    searchInput('model_id', $t('admin.ai.model.code')),
  ],
  agents: () => [
    searchInput('name', $t('admin.ai.agent.name')),
  ],
  skill_packages: () => [
    searchInput('name', $t('admin.ai.skillPackage.name')),
  ],
  knowledge_bases: () => [
    searchInput('name', $t('admin.knowledgeBase.field.name')),
  ],
  admin_roles: () => [
    searchInput('name', $t('admin.system.organization.node.name')),
    searchInput('code', $t('admin.system.organization.node.code')),
  ],
  tenant_plans: () => [
    searchInput('name', $t('admin.tenant.plan.name')),
    searchInput('code', $t('admin.tenant.plan.code')),
    statusSelect(),
  ],
  tenants: () => [
    searchInput('name', $t('admin.tenant.name')),
    searchInput('code', $t('admin.tenant.code')),
    statusSelect(),
  ],
  tenant_domains: () => [
    searchInput('domain', $t('admin.tenant.domain.domain')),
  ],
  table_policies: () => [
    searchInput('table_name', $t('admin.ai.tablePolicy.tableName')),
    searchInput('label', $t('admin.ai.tablePolicy.label')),
  ],
};

/**
 * 获取指定模块的搜索 Schema
 */
export function getModuleSearchSchema(moduleCode: string): VbenFormSchema[] {
  const factory = MODULE_SEARCH_SCHEMAS[moduleCode];
  if (!factory) return [];
  const schemas = factory();
  if (TENANT_MODULES.has(moduleCode)) {
    schemas.push(tenantSelect());
  }
  return schemas;
}

// ── 各模块 × 各字段 → 翻译标签 ──
// key = "module:field" 或 "field"（通用回退）
const COLUMN_LABELS: Record<string, () => string> = {
  // 通用字段
  'status': () => $t('shared.common.status'),
  // AI 供应商
  'ai_providers:name': () => $t('admin.ai.provider.name'),
  'ai_providers:code': () => $t('admin.ai.provider.code'),
  // AI 模型
  'ai_models:name': () => $t('admin.ai.model.name'),
  'ai_models:model_id': () => $t('admin.ai.model.code'),
  'ai_models:provider_id': () => $t('admin.ai.model.providerId'),
  // 智能体
  'agents:name': () => $t('admin.ai.agent.name'),
  // 技能包
  'skill_packages:name': () => $t('admin.ai.skillPackage.name'),
  'skill_packages:scope': () => $t('admin.ai.skillPackage.scope'),
  // 知识库
  'knowledge_bases:name': () => $t('admin.knowledgeBase.field.name'),
  // 角色
  'admin_roles:name': () => $t('admin.system.organization.node.name'),
  'admin_roles:code': () => $t('admin.system.organization.node.code'),
  // 套餐
  'tenant_plans:name': () => $t('admin.tenant.plan.name'),
  'tenant_plans:code': () => $t('admin.tenant.plan.code'),
  // 租户
  'tenants:name': () => $t('admin.tenant.name'),
  'tenants:code': () => $t('admin.tenant.code'),
  // 域名
  'tenant_domains:domain': () => $t('admin.tenant.domain.domain'),
  // 表策略
  'table_policies:table_name': () => $t('admin.ai.tablePolicy.tableName'),
  'table_policies:label': () => $t('admin.ai.tablePolicy.label'),
};

/**
 * 获取列字段的翻译标签
 * 先尝试 "module:field"，再回退到 "field"，最后返回原始字段名
 */
export function getColumnLabel(field: string, moduleCode?: string): string {
  if (moduleCode) {
    const specific = COLUMN_LABELS[`${moduleCode}:${field}`];
    if (specific) return specific();
  }
  const generic = COLUMN_LABELS[field];
  return generic ? generic() : field;
}
