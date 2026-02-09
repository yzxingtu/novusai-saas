/**
 * AI 使用量统计 - 表格列和搜索配置
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { VxeTableGridOptions } from '#/adapter/vxe-table';

import { dateField, select } from '#/adapter/form';
import { getAIModelListApi } from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

/**
 * 格式化 Token 数量
 */
export function formatTokens(tokens: number | null | undefined): string {
  if (!tokens) return '0';
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(2)}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
  return `${tokens}`;
}

/**
 * 格式化费用
 */
export function formatCost(cost: number | null | undefined): string {
  if (!cost) return '$0.00';
  return `$${Number(cost).toFixed(4)}`;
}

/**
 * 表格列定义
 */
export function useColumns(): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'stat_date',
      title: $t('admin.ai.usage.statDate'),
      width: 120,
      sortable: true,
    },
    {
      field: 'tenant_name',
      title: $t('admin.ai.usage.tenantName'),
      width: 140,
    },
    {
      field: 'model_name',
      title: $t('admin.ai.usage.modelName'),
      width: 140,
    },
    {
      field: 'request_type',
      title: $t('admin.ai.usage.requestType'),
      width: 100,
      align: 'center',
    },
    {
      field: 'total_tokens',
      title: $t('admin.ai.usage.totalTokens'),
      width: 120,
      align: 'right',
      sortable: true,
      slots: { default: 'totalTokens_cell' },
    },
    {
      field: 'input_tokens',
      title: $t('admin.ai.usage.inputTokens'),
      width: 120,
      align: 'right',
      slots: { default: 'inputTokens_cell' },
    },
    {
      field: 'output_tokens',
      title: $t('admin.ai.usage.outputTokens'),
      width: 120,
      align: 'right',
      slots: { default: 'outputTokens_cell' },
    },
    {
      field: 'call_count',
      title: $t('admin.ai.usage.callCount'),
      width: 100,
      align: 'right',
      sortable: true,
    },
    {
      field: 'success_count',
      title: $t('admin.ai.usage.successRate'),
      width: 120,
      align: 'center',
      slots: { default: 'successRate_cell' },
    },
    {
      field: 'total_cost',
      title: $t('admin.ai.usage.totalCost'),
      width: 120,
      align: 'right',
      sortable: true,
      slots: { default: 'totalCost_cell' },
    },
    {
      field: 'avg_latency_ms',
      title: $t('admin.ai.usage.avgLatency'),
      width: 130,
      align: 'right',
    },
  ];
}

/**
 * 获取模型下拉选项
 */
async function getModelSelectOptions() {
  const response = await getAIModelListApi({
    'page[size]': 200,
    'sort': 'name',
    'filter[is_active]': true,
  });
  return response.items.map((item) => ({
    label: `${item.name} (${item.provider_name || '-'})`,
    value: item.id,
  }));
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    select('filter[tenant_id]', $t('admin.ai.usage.tenantName'), {
      api: getTenantSelectApi,
      params: { is_active: 'true' },
      placeholder: $t('admin.ai.usage.placeholder.selectTenant'),
    }),
    select('filter[model_id]', $t('admin.ai.usage.modelName'), {
      api: getModelSelectOptions,
      placeholder: $t('admin.ai.usage.placeholder.selectModel'),
    }),
    select('filter[request_type][eq]', $t('admin.ai.usage.requestType'), {
      options: [
        { label: $t('admin.ai.usage.type_options.chat'), value: 'chat' },
        { label: $t('admin.ai.usage.type_options.embedding'), value: 'embedding' },
        { label: $t('admin.ai.usage.type_options.image'), value: 'image' },
      ],
      placeholder: $t('admin.ai.usage.requestType'),
    }),
    dateField('filter[stat_date][gte]', $t('admin.ai.usage.placeholder.startDate'), {
      placeholder: $t('admin.ai.usage.placeholder.startDate'),
      showTime: false,
    }),
    dateField('filter[stat_date][lte]', $t('admin.ai.usage.placeholder.endDate'), {
      placeholder: $t('admin.ai.usage.placeholder.endDate'),
      showTime: false,
    }),
  ];
}
