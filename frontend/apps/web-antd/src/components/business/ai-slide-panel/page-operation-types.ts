/**
 * Page operation shared types
 * 页面操作共享类型
 */

/** Operation execution result / 操作执行结果 */
export interface PageOperationResult {
  /** Whether execution succeeded / 是否执行成功 */
  success: boolean;
  /** Result message (returned to LLM) / 结果消息（返回给 LLM） */
  message: string;
  /** Additional data (optional, structured result for LLM analysis) / 附加数据 */
  data?: Record<string, unknown>;
  /** Error type for failure classification / 失败分类 */
  error_type?: string;
}

/** Operation handler function type / 操作处理函数类型 */
export type PageOperationHandler = (
  params: Record<string, unknown>,
) => PageOperationResult | Promise<PageOperationResult>;

/**
 * Page operation declaration
 * 页面操作声明
 */
export interface PageOperation {
  /** Operation unique identifier / 操作唯一标识 */
  name: string;
  /** Human-readable label / 人类可读标签 */
  label: string;
  /** Operation description (for LLM intent understanding) / 操作描述 */
  description?: string;
  /** Whether it is a read-only operation / 是否为只读操作 */
  readonly: boolean;
  /** Parameter schema (JSON Schema subset) / 参数 schema */
  params?: Record<string, unknown>;
  /** Operation handler function / 操作处理函数 */
  handler?: PageOperationHandler;
}
