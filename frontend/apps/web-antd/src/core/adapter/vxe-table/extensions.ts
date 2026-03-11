/**
 * vxe-table extension features: batch selection, Excel export, expandable rows
 * vxe-table 扩展功能：包含批量选择、Excel导出、展开行
 */
import type { VxeGridInstance } from 'vxe-table';

import { message } from 'ant-design-vue';
import * as XLSX from 'xlsx';

import { $t } from '#/locales';

// ============================================================
// 1. Batch Selection / 批量选择相关
// ============================================================

/**
 * Checkbox column definition / 复选框列定义
 */
export const checkboxColumn = {
  type: 'checkbox' as const,
  width: 50,
  align: 'center' as const,
  fixed: 'left' as const,
};

/**
 * Sequence column definition / 序号列定义
 */
export const seqColumn = {
  type: 'seq' as const,
  title: '#',
  width: 50,
  align: 'center' as const,
};

/**
 * Utility function to get selected rows / 获取选中行的工具函数
 */
export function getSelectedRows<T = any>(
  gridRef: undefined | VxeGridInstance | { value: undefined | VxeGridInstance },
): T[] {
  const grid = gridRef && 'value' in gridRef ? gridRef.value : gridRef;
  if (!grid) return [];
  return grid.getCheckboxRecords() as T[];
}

/**
 * Get selected row ID list / 获取选中行的 ID 列表
 */
export function getSelectedIds<T extends Record<string, any>>(
  gridRef: undefined | VxeGridInstance | { value: undefined | VxeGridInstance },
  keyField: keyof T | string = 'id',
): Array<T[keyof T]> {
  const rows = getSelectedRows<T>(gridRef);
  return rows.map((row) => row[keyField as keyof T]);
}

/**
 * Clear selection / 清空选中
 */
export function clearSelection(
  gridRef: undefined | VxeGridInstance | { value: undefined | VxeGridInstance },
): void {
  const grid = gridRef && 'value' in gridRef ? gridRef.value : gridRef;
  if (!grid) return;
  grid.clearCheckboxRow();
}

// ============================================================
// 2. Excel Export / Excel 导出相关
// ============================================================

export interface ExportColumn {
  /** Field name / 字段名 */
  field: string;
  /** Export column title (supports i18n key) / 导出列标题（支持 i18n key） */
  title?: string;
  /** i18n key (takes priority over title) / i18n key（优先于 title） */
  titleKey?: string;
  /** Formatter function / 格式化函数 */
  formatter?: (value: any, row: any) => string;
}

export interface ExportOptions {
  /** Filename (without extension) / 文件名（不含扩展名） */
  filename?: string;
  /** Export column config, defaults to table columns (auto-detects current locale) / 导出的列配置，不传则使用表格列（自动识别当前语言） */
  columns?: ExportColumn[];
  /** Sheet name / 工作表名称 */
  sheetName?: string;
  /** Before export callback, return false to abort / 导出前回调，返回 false 可中断 */
  beforeExport?: () => boolean | Promise<boolean>;
  /** After export callback / 导出完成回调 */
  afterExport?: () => void;
  /** Whether to export all data (default: current page) / 是否导出全量数据（默认当前页） */
  exportAll?: boolean;
}

/**
 * Export current page data to Excel, auto-supports multilingual headers (using column config title)
 * 导出当前页数据为 Excel，自动支持多语言表头（使用列配置中的 title）
 */
export async function exportToExcel(
  gridRef: undefined | VxeGridInstance | { value: undefined | VxeGridInstance },
  options: ExportOptions = {},
): Promise<void> {
  const grid = gridRef && 'value' in gridRef ? gridRef.value : gridRef;
  if (!grid) {
    message.warning($t('shared.common.noData'));
    return;
  }

  const {
    filename = `export_${new Date().toISOString().slice(0, 10)}`,
    columns,
    sheetName = 'Sheet1',
    beforeExport,
    afterExport,
    exportAll = false,
  } = options;

  // Before export callback / 导出前回调
  if (beforeExport) {
    const canExport = await beforeExport();
    if (canExport === false) return;
  }

  // Get data - use correct vxe-grid API / 获取数据 - 使用正确的 vxe-grid API
  const { fullData, tableData: currentPageData } = grid.getTableData();
  const tableData = exportAll ? fullData : currentPageData;

  if (!tableData || tableData.length === 0) {
    message.warning($t('shared.common.noData'));
    return;
  }

  // Get column config - title is already in current locale text (rendered via $t) / 获取列配置 - title 已经是当前语言的文本（通过 $t 渲染）
  const tableColumns = grid.getTableColumn().fullColumn;
  const exportColumns: ExportColumn[] =
    columns ||
    (tableColumns
      .filter((col) => {
        // Exclude special columns / 排除特殊列
        if (!col.field) return false;
        if (
          col.type === 'checkbox' ||
          col.type === 'seq' ||
          col.type === 'expand'
        )
          return false;
        if (col.field === '_drag' || col.field === 'operation') return false;
        return true;
      })
      .map((col) => ({
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        field: col.field!,
        // title is already i18n-processed current locale text / title 已经是经过 i18n 处理的当前语言文本
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        title: String(col.title || col.field!),
      })) as ExportColumn[]);

  // Transform data / 转换数据
  const exportData = tableData.map((row: any) => {
    const rowData: Record<string, any> = {};
    exportColumns.forEach((col) => {
      const value = row[col.field];
      // Use titleKey for i18n translation, otherwise use title / 使用 titleKey 进行 i18n 翻译，否则使用 title
      const headerTitle = col.titleKey
        ? $t(col.titleKey)
        : col.title || col.field;
      rowData[headerTitle] = col.formatter
        ? col.formatter(value, row)
        : (value ?? '');
    });
    return rowData;
  });

  // Create workbook / 创建工作簿
  const worksheet = XLSX.utils.json_to_sheet(exportData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);

  // Export file / 导出文件
  XLSX.writeFile(workbook, `${filename}.xlsx`);

  message.success($t('shared.common.exportSuccess'));
  afterExport?.();
}

// ============================================================
// 3. Expandable Rows / 展开行相关
// ============================================================

/**
 * Expand column definition / 展开列定义
 */
export const expandColumn = {
  type: 'expand' as const,
  width: 50,
  align: 'center' as const,
  slots: { content: 'expand_content' },
};

/**
 * Expand row configuration / 展开行配置
 */
export interface ExpandConfig {
  /** Lazy loading / 是否懒加载 */
  lazy?: boolean;
  /** Lazy load method / 懒加载方法 */
  loadMethod?: (params: { row: any }) => Promise<any>;
  /** Accordion mode (only expand one row) / 是否手风琴模式（只展开一行） */
  accordion?: boolean;
  /** Height when expanded / 展开时的高度 */
  height?: number;
}

/**
 * Create expand row configuration / 创建展开行配置
 */
export function createExpandConfig(config: ExpandConfig = {}): any {
  const { lazy = false, loadMethod, accordion = false, height } = config;
  return {
    lazy,
    loadMethod,
    accordion,
    height,
    iconOpen: 'vxe-icon-square-minus',
    iconClose: 'vxe-icon-square-plus',
  };
}

// ============================================================
// 4. Renderer Registration (called in vxe-table.ts) / 渲染器注册（在 vxe-table.ts 中调用）
// ============================================================

/**
 * Register export button renderer / 注册导出按钮渲染器
 */
export function registerExportRenderer(_vxeUI: any) {
  // Export button is built into toolbar; extend custom export logic here / 导出按钮已在工具栏中内置，这里可以扩展自定义导出逻辑
}
