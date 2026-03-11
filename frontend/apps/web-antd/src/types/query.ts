/**
 * Common list query type definitions
 * Aligned with backend JSON:API style
 * 通用列表筛选类型定义
 * 与后端 JSON:API 风格保持一致
 *
 * @module types/query
 */

/**
 * Paginated response format
 * 分页响应格式
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Dropdown option (corresponds to backend SelectOption)
 * 下拉选项（对应后端 SelectOption）
 */
export interface SelectOption {
  /** Display text / 显示文本 */
  label: string;
  /** Value / 值 */
  value: number | string;
  /** Extended data / 扩展数据 */
  extra?: Record<string, unknown>;
  /** Whether disabled / 是否禁用 */
  disabled?: boolean;
}

/**
 * Dropdown option response
 * 下拉选项响应
 */
export interface SelectResponse {
  items: SelectOption[];
}
