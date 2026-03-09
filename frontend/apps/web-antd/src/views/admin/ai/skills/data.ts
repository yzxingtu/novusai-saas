/**
 * 技能管理（平台端） - 表格列、搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { searchInput, select } from '#/adapter/form';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

function getSkillTypeOptions(currentType?: string) {
  const predefined = [
    { label: $t('admin.ai.skill.type_options.toolkit'), value: 'toolkit' },
    {
      label: $t('admin.ai.skill.type_options.data_intelligence'),
      value: 'data_intelligence',
    },
    { label: $t('admin.ai.skill.type_options.builtin'), value: 'builtin' },
    { label: $t('admin.ai.skill.type_options.http'), value: 'http' },
    { label: $t('admin.ai.skill.type_options.email'), value: 'email' },
    {
      label: $t('admin.ai.skill.type_options.code_execution'),
      value: 'code_execution',
    },
  ];
  if (currentType && !predefined.some((o) => o.value === currentType)) {
    const key = `admin.ai.skill.type_options.${currentType}`;
    const text = $t(key);
    predefined.push({
      label: text === key ? currentType : text,
      value: currentType,
    });
  }
  return predefined;
}

/**
 * 获取技能类型文本
 */
export function getSkillTypeText(type: string | undefined): string {
  if (!type) return '-';
  const key = `admin.ai.skill.type_options.${type}`;
  const text = $t(key);
  // fallback: 插件注册的 type 没有系统 i18n key，显示人类可读的格式
  if (text === key) {
    return type
      .replaceAll('_', ' ')
      .replaceAll(/\b\w/g, (c) => c.toUpperCase());
  }
  return text;
}

export { getSkillTypeColor } from '#/utils/ai-helpers';

/**
 * 表格列定义
 */
export function useColumns<T = AdminSkillInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('admin.ai.skill.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('admin.ai.skill.type'),
      width: 120,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'is_active',
      title: $t('admin.ai.skill.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'tenant_id',
      title: $t('admin.ai.skill.tenantId'),
      width: 100,
      align: 'center',
      slots: { default: 'tenantId_cell' },
    },
    {
      field: 'timeout',
      title: $t('admin.ai.skill.timeout'),
      width: 100,
      align: 'center',
      slots: { default: 'timeout_cell' },
    },
    {
      field: 'created_at',
      title: $t('admin.common.createdAt'),
      width: 170,
      sortable: true,
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'ai_skill',
          nameField: 'name',
          nameTitle: $t('admin.ai.skill.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          {
            code: 'test',
            text: $t('admin.ai.skill.testBtn'),
            icon: 'lucide:play',
          },
          'edit',
          { code: 'delete', show: (row: AdminSkillInfo) => !row.is_system },
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('admin.common.operation'),
      width: 200,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('filter[name][ilike]', $t('admin.ai.skill.name'), {
      placeholder: $t('admin.ai.skill.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('admin.ai.skill.type'), {
      options: getSkillTypeOptions(),
      placeholder: $t('admin.ai.skill.placeholder.allTypes'),
    }),
    select('filter[tenant_id]', $t('admin.ai.skill.tenantId'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.skill.placeholder.allTenants'),
    }),
  ];
}
