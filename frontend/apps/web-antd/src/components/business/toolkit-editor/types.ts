/**
 * Toolkit 编辑器共享类型
 *
 * 避免共享组件从 admin/tenant API 跨端导入。
 */

/** Toolkit 解析结果中的 Tool */
export interface ToolkitToolInfo {
  name: string;
  description: string;
  parameters: Array<{
    default?: unknown;
    description: string;
    name: string;
    required: boolean;
    type: string;
  }>;
  is_async: boolean;
}

/** Toolkit 解析响应 */
export interface ToolkitParseResult {
  title?: string;
  description?: string;
  version?: string;
  author?: string;
  requirements?: string[];
  tools: ToolkitToolInfo[];
  valves_schema: Record<string, unknown>;
  errors: string[];
}
