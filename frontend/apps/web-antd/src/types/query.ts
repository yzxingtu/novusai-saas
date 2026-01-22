/**
 * 通用列表筛选类型定义
 * 与后端 JSON:API 风格保持一致
 *
 * @module types/query
 */

/**
 * 分页响应格式
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * 下拉选项（对应后端 SelectOption）
 */
export interface SelectOption {
  /** 显示文本 */
  label: string;
  /** 值 */
  value: number | string;
  /** 扩展数据 */
  extra?: Record<string, unknown>;
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 下拉选项响应
 */
export interface SelectResponse {
  items: SelectOption[];
}
