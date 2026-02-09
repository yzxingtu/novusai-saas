/**
 * 租户端可用模型列表 - 表格列、搜索配置（只读）
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridOptions } from '#/adapter/vxe-table';

import { searchInput, select } from '#/adapter/form';
import { $t } from '#/locales';

function getModelTypeOptions() {
  return [
    { label: $t('tenant.ai.model.type_options.chat'), value: 'chat' },
    { label: $t('tenant.ai.model.type_options.embedding'), value: 'embedding' },
    { label: $t('tenant.ai.model.type_options.image'), value: 'image' },
  ];
}

/**
 * 获取模型类型文本
 */
export function getModelTypeText(type: string | undefined): string {
  if (!type) return '-';
  switch (type) {
    case 'chat': return $t('tenant.ai.model.type_options.chat');
    case 'embedding': return $t('tenant.ai.model.type_options.embedding');
    case 'image': return $t('tenant.ai.model.type_options.image');
    default: return type;
  }
}

/**
 * 格式化 Token 数量
 */
export function formatTokens(num: null | number | undefined): string {
  if (!num) return '-';
  if (num >= 1000000) return `${(num / 1000000).toFixed(0)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return `${num}`;
}

/**
 * 格式化价格
 */
export function formatPrice(price: null | number | undefined): string {
  if (price === null || price === undefined) return '-';
  return `$${price}`;
}

/**
 * 表格列定义
 */
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.ai.model.name'),
      minWidth: 200,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('tenant.ai.model.type'),
      width: 100,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'provider_name',
      title: $t('tenant.ai.model.providerName'),
      width: 140,
      align: 'center',
    },
    {
      field: 'context_window',
      title: $t('tenant.ai.model.contextWindow'),
      width: 130,
      align: 'right',
      slots: { default: 'contextWindow_cell' },
    },
    {
      field: 'input_price_per_1k',
      title: $t('tenant.ai.model.inputPrice'),
      width: 130,
      align: 'right',
      slots: { default: 'inputPrice_cell' },
    },
    {
      field: 'output_price_per_1k',
      title: $t('tenant.ai.model.outputPrice'),
      width: 130,
      align: 'right',
      slots: { default: 'outputPrice_cell' },
    },
    {
      field: 'capabilities',
      title: $t('tenant.ai.model.streaming'),
      width: 200,
      align: 'center',
      slots: { default: 'capabilities_cell' },
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.ai.model.name'), {
      placeholder: $t('tenant.ai.model.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('tenant.ai.model.type'), {
      options: getModelTypeOptions(),
      placeholder: $t('tenant.ai.model.placeholder.allTypes'),
    }),
  ];
}
