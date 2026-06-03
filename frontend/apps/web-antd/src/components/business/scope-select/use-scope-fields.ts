/**
 * useScopeFields — Unified scope form field generator
 * useScopeFields — 统一作用域表单字段生成器
 *
 * Generates a set of scope-related form fields for VbenForm:
 * 为 VbenForm 生成一组 scope 相关的表单字段：
 * 1. Scope dropdown (scope) / 作用域下拉（scope）
 * 2. Tenant select (shown when scope=all_tenants，仅特殊场景如定时任务) / 所属企业单选
 * 3. Tenant multi-select (selected_tenants / admin_and_selected_tenants) / 分配企业多选
 *
 * All forms requiring scope selection (knowledge bases, agents, API keys, etc.) use this.
 * 所有需要作用域选择的表单（知识库、智能体、API Key 等）统一使用此函数。
 */
import type { VbenFormSchema } from '#/adapter/form';

import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import { getScopeOptions } from '#/utils/scope-helpers';

export interface ScopeFieldsOptions {
  /** Allowed scope values list, returns all 5 if not passed / 允许的 scope 値列表，不传则返回全部 5 种 */
  allowedScopes?: string[];
  /** Help text for scope field / scope 字段的 help 文本 */
  scopeHelp?: string;
  /** Whether scope field is disabled (locked during edit) / scope 字段是否禁用（编辑时锁定） */
  scopeDisabled?: ((values: Record<string, unknown>) => boolean) | boolean;
  /** Default scope value exposed to form schema and explicit AI data tools / 作用域默认值，用于表单 schema 与显式 AI 数据工具 */
  scopeDefaultValue?: string;
  /**
   * Whether to show an owner-tenant select for special scenarios, default false.
   * 是否显示「所属企业」单选，仅特殊场景使用，默认 false。
   * Regular resources (agents/knowledge bases / periodic tasks) don't pass this.
   * 普通资源（智能体/知识库/定时任务）不传此项。
   */
  showTenantId?: boolean;
  /**
   * Show single owner-tenant select when scope is in this list (e.g. API Key: selected_tenants).
   * 当 scope 属于列表时显示「归属企业」单选（如 API Key 的 selected_tenants）。
   */
  ownerTenantWhenScopes?: string[];
  /** Hide assigned-tenants multi-select (API Key 等仅需归属企业、不需 RTA 多选时使用) */
  hideTenantIdsField?: boolean;
  /**
   * Whether tenant_id is required when shown, default true.
   * 所属企业是否必填，默认 true。
   * Set to false when tenant_id=null has valid meaning (e.g. API Key: null = platform-wide shared).
   * 当 tenant_id=null 有合法含义时设为 false（如 API Key：null = 平台共享）。
   */
  tenantIdRequired?: boolean;
  /** Scope field name, default 'scope' / scope 字段名，默认 'scope' */
  scopeField?: string;
  /** Tenant ID field name, default 'tenant_id' / 所属企业字段名，默认 'tenant_id' */
  tenantIdField?: string;
  /** Assigned tenants field name, default 'tenant_ids' / 分配企业字段名，默认 'tenant_ids' */
  tenantIdsField?: string;
  /** Whether assigned tenants multi-select is required when shown, default true / 分配企业多选展示时是否必填，默认 true */
  tenantIdsRequired?: boolean;
}

/**
 * Generate scope-related VbenForm schema field group
 * 生成 scope 相关的 VbenForm schema 字段组
 */
export function useScopeFields(
  options: ScopeFieldsOptions = {},
): VbenFormSchema[] {
  const {
    allowedScopes,
    scopeHelp,
    scopeDisabled = false,
    scopeDefaultValue,
    showTenantId = false,
    ownerTenantWhenScopes = [],
    hideTenantIdsField = false,
    tenantIdRequired = true,
    tenantIdsRequired = true,
    scopeField = 'scope',
    tenantIdField = 'tenant_id',
    tenantIdsField = 'tenant_ids',
  } = options;

  const needsAssignment = (v: Record<string, unknown>) =>
    v[scopeField] === 'selected_tenants' ||
    v[scopeField] === 'admin_and_selected_tenants';

  const fields: VbenFormSchema[] = [];

  // ── 1. Scope dropdown / 作用域下拉 ──
  const scopeSchema: VbenFormSchema = {
    component: 'Select',
    fieldName: scopeField,
    label: $t('common.scope.label'),
    rules: 'selectRequired',
    ...(scopeDefaultValue === undefined
      ? {}
      : { defaultValue: scopeDefaultValue }),
    componentProps: {
      allowClear: false,
      class: 'w-full',
      options: getScopeOptions(allowedScopes),
      showSearch: true,
      optionFilterProp: 'label',
    },
  };
  if (scopeHelp) {
    scopeSchema.help = scopeHelp;
  }
  // Always set dependencies.disabled (even when scopeDisabled=false) so that / 始终设置 dependencies.disabled
  // when the schema switches from locked→unlocked the Vben dependency watcher / 以便 locked→unlocked 时 Vben 依赖监听
  // calls resetConditionState() and clears the stale isDisabled=true state. / 触发 resetConditionState 清除陈旧禁用态
  scopeSchema.dependencies = {
    triggerFields: ['_mode'],
    disabled:
      typeof scopeDisabled === 'function'
        ? scopeDisabled
        : () => Boolean(scopeDisabled),
  };
  fields.push(scopeSchema);

  // ── 2. Tenant select (all_tenants 特例 / ownerTenantWhenScopes 如 API Key) / 所属企业 ──
  if (showTenantId || ownerTenantWhenScopes.length > 0) {
    const isTenantScope = (v: Record<string, unknown>) => {
      const sc = v[scopeField] as string;
      if (showTenantId && sc === 'all_tenants') {
        return true;
      }
      return ownerTenantWhenScopes.includes(sc);
    };
    const tenantField: VbenFormSchema = {
      component: 'ApiSelect',
      fieldName: tenantIdField,
      label: $t('common.scope.tenantId'),
      componentProps: {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        resultField: 'items',
        allowClear: true,
        showSearch: true,
        filterOption: false,
        pagination: true,
        clickPagination: true,
        pageSize: 10,
        class: 'w-full',
        placeholder: $t('common.scope.selectTenant'),
      },
      dependencies: {
        triggerFields: [scopeField],
        if: isTenantScope,
      },
    };
    if (tenantIdRequired) {
      tenantField.rules = 'selectRequired';
    }
    fields.push(tenantField);
  }

  // ── 3. Assigned tenants / 分配企业 ──
  if (!hideTenantIdsField) {
    fields.push({
      component: 'ApiSelect',
      fieldName: tenantIdsField,
      label: $t('common.scope.assignedTenantsLabel'),
      help: $t('common.scope.assignedTenantsHelp'),
      ...(tenantIdsRequired ? { rules: 'selectRequired' } : {}),
      componentProps: {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        resultField: 'items',
        mode: 'multiple',
        allowClear: true,
        showSearch: true,
        filterOption: false,
        pagination: true,
        clickPagination: true,
        pageSize: 10,
        class: 'w-full',
        placeholder: $t('common.scope.selectAssignedTenants'),
      },
      dependencies: {
        triggerFields: [scopeField],
        if: needsAssignment,
      },
    });
  }

  return fields;
}

/**
 * Check if scope requires tenant assignment
 * 判断 scope 是否需要企业分配
 */
export function scopeNeedsAssignment(scope: string): boolean {
  return scope === 'selected_tenants' || scope === 'admin_and_selected_tenants';
}

/**
 * Extract scope-related submit data from form values
 * 从表单值中提取 scope 相关的提交数据
 *
 * @param values Form values / 表单值
 * @param scopeField Scope field name / scope 字段名
 * @param withTenantId Whether to include tenant_id for special ownership scenarios / 是否包含 tenant_id
 */
export function extractScopePayload(
  values: Record<string, unknown>,
  scopeField = 'scope',
  withTenantId = false,
): Record<string, unknown> {
  const scope = values[scopeField] as string;
  const result: Record<string, unknown> = {
    [scopeField]: scope,
    tenant_id:
      withTenantId && scope === 'all_tenants'
        ? (values.tenant_id ?? null)
        : null,
  };

  if (scopeNeedsAssignment(scope)) {
    result.tenant_ids = values.tenant_ids ?? [];
  }

  return result;
}

/**
 * Extract scope-related form backfill values from detail data
 * 从详情数据中提取 scope 相关的表单回填值
 */
export function extractScopeFormValues(data: {
  [k: string]: unknown;
  assigned_tenant_ids?: number[];
  scope?: string;
  tenant_id?: null | number;
}): Record<string, unknown> {
  return {
    scope: data.scope,
    tenant_id: data.tenant_id ?? null,
    tenant_ids: data.assigned_tenant_ids ?? [],
  };
}
