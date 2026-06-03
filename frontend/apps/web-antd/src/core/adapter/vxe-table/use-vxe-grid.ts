import type { GridOptionsConfig } from './types';

/**
 * Table hooks and config factories / 表格 Hook 和配置工厂
 */
import type { VbenFormSchema } from '#/adapter/form';

import { useVbenVxeGrid as useGrid } from '@vben/plugins/vxe-table';

import { exportToExcel } from './extensions';

/**
 * Enhanced useVbenVxeGrid - adds exportExcel method
 * 增强版 useVbenVxeGrid - 添加 exportExcel 方法
 *
 * @example
 * ```ts
 * const [Grid, gridApi] = useVbenVxeGrid({ gridOptions });
 *
 * // Export Excel / 导出 Excel
 * gridApi.exportExcel({ filename: '用户列表' });
 * ```
 */
export function useVbenVxeGrid(options: Parameters<typeof useGrid>[0]) {
  // Call original useGrid / 调用原始的 useGrid
  const result = useGrid(options);

  // Extend gridApi, add export method / 扩展 gridApi，添加导出方法
  const [Grid, originalGridApi] = result;

  // Add export method to original API / 添加导出方法到原始 API
  (originalGridApi as any).exportExcel = (
    exportOptions?: Parameters<typeof exportToExcel>[1],
  ) => {
    return exportToExcel(originalGridApi.grid, exportOptions);
  };

  return [Grid, originalGridApi] as const;
}

/**
 * Standard list search form options
 * 标准列表搜索表单配置
 *
 * For list page search forms, provides unified config:
 * 用于列表页面的搜索表单，提供统一的配置：
 * - Enables search-on-change (submitOnChange) / 启用输入即搜索
 * - Hides search button (since submitOnChange is enabled) / 隐藏搜索按钮
 * - Reset button uses ghost style, consistent with collapse button / 重置按钮使用文字样式
 *
 * @param schema 表单 schema
 * @returns formOptions 配置对象
 *
 * @example
 * ```ts
 * const [Grid, gridApi] = useVbenVxeGrid({
 *   formOptions: useGridSearchFormOptions(useGridFormSchema()),
 *   gridOptions: { ... },
 * });
 * ```
 */
export function useGridSearchFormOptions(schema: VbenFormSchema[]) {
  return {
    schema,
    submitOnChange: true,
    // Hide search button (submitOnChange enabled) / 隐藏搜索按钮
    submitButtonOptions: {
      show: false,
    },
    // Reset button ghost style, consistent with collapse button / 重置按钮使用文字样式
    resetButtonOptions: {
      variant: 'ghost' as const,
      size: 'sm' as const,
    },
  };
}

/**
 * Grid options factory - minimizes table configuration
 * 表格配置工厂函数 - 极简化表格配置
 *
 * Provides sensible defaults, users only need to pass required config
 * 提供合理的默认值，用户只需传入必要配置
 *
 * @example
 * ```ts
 * const [Grid, gridApi] = useVbenVxeGrid({
 *   formOptions: useGridSearchFormOptions(useGridFormSchema()),
 *   gridOptions: useGridOptions({
 *     columns: useColumns(onActionClick, onToggleStatus),
 *     queryApi: (params) => api.getListApi(params),
 *   }),
 * });
 * ```
 */
export function useGridOptions(config: GridOptionsConfig) {
  const {
    columns,
    queryApi,
    defaultSort = '-created_at',
    rowHeight = 64,
    stripe = true,
    pager = true,
    toolbar = {
      custom: true,
      export: true,
      refresh: true,
      search: true,
      zoom: true,
    },
    ...rest
  } = config;

  return {
    columns,
    stripe,
    keepSource: true,
    pagerConfig: { enabled: pager },
    proxyConfig: {
      ajax: {
        query: async ({ page }: any, formValues: any) => {
          return await queryApi({
            ...formValues,
            'page[number]': page.currentPage,
            'page[size]': page.pageSize,
            sort: defaultSort,
          });
        },
      },
    },
    cellConfig: { height: rowHeight },
    rowConfig: { keyField: 'id' },
    toolbarConfig: toolbar,
    ...rest,
  };
}
