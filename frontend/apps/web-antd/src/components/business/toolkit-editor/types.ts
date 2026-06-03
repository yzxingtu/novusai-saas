/**
 * Toolkit 编辑器共享类型 / Toolkit editor shared types
 *
 * 避免共享组件从 admin/tenant API 跨端导入。Avoid cross-import from admin/tenant API.
 */

/** Toolkit 解析结果中的 Tool / Tool in toolkit parse result */
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

/** Toolkit 解析响应 / Toolkit parse response */
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
