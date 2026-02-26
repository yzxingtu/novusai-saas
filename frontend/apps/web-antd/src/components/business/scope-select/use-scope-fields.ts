/**
 * useScopeFields — 统一作用域表单字段生成器
 *
 * 为 VbenForm 生成一组 scope 相关的表单字段：
 * 1. 作用域下拉（scope）
 * 2. 所属租户单选（scope=all_tenants 时显示）
 * 3. 分配租户多选（scope=assigned_tenants / admin_and_assigned 时显示）
 *
 * 所有需要作用域选择的表单（技能包、知识库、智能体等）统一使用此函数。
 */
import type { VbenFormSchema } from '#/adapter/form';

import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import { getScopeOptions } from '#/utils/scope-helpers';

export interface ScopeFieldsOptions {
  /** 允许的 scope 值列表，不传则返回全部 5 种 */
  allowedScopes?: string[];
  /** scope 字段的 help 文本 */
  scopeHelp?: string;
  /** scope 字段是否禁用（编辑时锁定） */
  scopeDisabled?: boolean | ((values: Record<string, unknown>) => boolean);
  /** 是否显示「所属租户」单选（scope=all_tenants），默认 true */
  showTenantId?: boolean;
  /** scope 字段名，默认 'scope' */
  scopeField?: string;
  /** 所属租户字段名，默认 'tenant_id' */
  tenantIdField?: string;
  /** 分配租户字段名，默认 'tenant_ids' */
  tenantIdsField?: string;
}

/**
 * 生成 scope 相关的 VbenForm schema 字段组
 */
export function useScopeFields(options: ScopeFieldsOptions = {}): VbenFormSchema[] {
  const {
    allowedScopes,
    scopeHelp,
    scopeDisabled = false,
    showTenantId = true,
    scopeField = 'scope',
    tenantIdField = 'tenant_id',
    tenantIdsField = 'tenant_ids',
  } = options;

  const needsAssignment = (v: Record<string, unknown>) =>
    v[scopeField] === 'assigned_tenants' || v[scopeField] === 'admin_and_assigned';

  const isTenantScope = (v: Record<string, unknown>) =>
    v[scopeField] === 'all_tenants';

  const fields: VbenFormSchema[] = [];

  // ── 1. 作用域下拉 ──
  const scopeSchema: VbenFormSchema = {
    component: 'Select',
    fieldName: scopeField,
    label: $t('common.scope.label'),
    rules: 'selectRequired',
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
  if (scopeDisabled !== false) {
    scopeSchema.dependencies = {
      triggerFields: ['_mode'],
      disabled: typeof scopeDisabled === 'function'
        ? scopeDisabled
        : () => scopeDisabled,
    };
  }
  fields.push(scopeSchema);

  // ── 2. 所属租户（scope=all_tenants 时显示） ──
  if (showTenantId) {
    fields.push({
      component: 'ApiSelect',
      fieldName: tenantIdField,
      label: $t('common.scope.tenantId'),
      rules: 'selectRequired',
      componentProps: {
        api: getTenantSelectApi,
        params: { is_active: 'true' },
        resultField: 'items',
        allowClear: true,
        showSearch: true,
        filterOption: false,
        class: 'w-full',
        placeholder: $t('common.scope.selectTenant'),
      },
      dependencies: {
        triggerFields: [scopeField],
        if: isTenantScope,
      },
    });
  }

  // ── 3. 分配租户（scope=assigned_tenants / admin_and_assigned 时显示） ──
  fields.push({
    component: 'ApiSelect',
    fieldName: tenantIdsField,
    label: $t('common.scope.assignedTenantsLabel'),
    help: $t('common.scope.assignedTenantsHelp'),
    rules: 'selectRequired',
    componentProps: {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      resultField: 'items',
      mode: 'multiple',
      allowClear: true,
      showSearch: true,
      filterOption: false,
      class: 'w-full',
      placeholder: $t('common.scope.selectAssignedTenants'),
    },
    dependencies: {
      triggerFields: [scopeField],
      if: needsAssignment,
    },
  });

  return fields;
}

/**
 * 判断 scope 是否需要租户分配
 */
export function scopeNeedsAssignment(scope: string): boolean {
  return scope === 'assigned_tenants' || scope === 'admin_and_assigned';
}

/**
 * 从表单值中提取 scope 相关的提交数据
 *
 * @param values 表单值
 * @param scopeField scope 字段名
 */
export function extractScopePayload(
  values: Record<string, unknown>,
  scopeField = 'scope',
): Record<string, unknown> {
  const scope = values[scopeField] as string;
  const result: Record<string, unknown> = { [scopeField]: scope };

  if (scope === 'all_tenants') {
    result.tenant_id = values.tenant_id;
  } else {
    result.tenant_id = null;
  }

  if (scopeNeedsAssignment(scope)) {
    result.tenant_ids = values.tenant_ids ?? [];
  }

  return result;
}

/**
 * 从详情数据中提取 scope 相关的表单回填值
 */
export function extractScopeFormValues(
  data: { scope?: string; tenant_id?: number | null; assigned_tenant_ids?: number[]; [k: string]: unknown },
): Record<string, unknown> {
  return {
    scope: data.scope,
    tenant_id: data.tenant_id ?? null,
    tenant_ids: data.assigned_tenant_ids ?? [],
  };
}
