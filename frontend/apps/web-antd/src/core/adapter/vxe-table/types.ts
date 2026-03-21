/**
 * Declarative table type definitions
 * 声明式表格类型定义
 */
import type { Component } from 'vue';

import type { Recordable } from '@vben/types';

import type { VbenFormSchema } from '#/adapter/form';
import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-registry';
import type {
  PageAICapabilityKey,
  TablePolicySupportConfig,
} from '#/utils/ai-page-capabilities';

// Export base types from vben plugin / 从 vben 插件导出基础类型
export type { VxeTableGridOptions } from '@vben/plugins/vxe-table';

/**
 * Action button click params / 操作按钮点击参数
 */
export interface OnActionClickParams<T = Recordable<any>> {
  code: string;
  row: T;
}

/**
 * Action button click callback / 操作按钮点击回调函数
 */
export type OnActionClickFn<T = Recordable<any>> = (
  params: OnActionClickParams<T>,
) => void;

/**
 * Base row data interface / 基础行数据接口
 */
export interface BaseRow {
  id: number | string;
  isActive?: boolean;
  is_active?: boolean;
  name?: string;
  [key: string]: any;
}

/**
 * Form operation mode / 表单操作模式
 */
export type FormMode = 'add' | 'copy' | 'edit' | 'view';

/**
 * Column definition factory type, returns VxeTableGridOptions['columns'] (can be undefined)
 * 列定义函数类型，返回 VxeTableGridOptions['columns'] 类型（可以是 undefined）
 */

export type ColumnsFactory<_T = any> = (...args: any[]) => any[] | undefined;

/**
 * Toggle status API type, accepts id and status data, returns Promise
 * 切换状态 API 类型，接受 id 和状态数据，返回 Promise
 */

export type ToggleStatusApi = (id: any, data: any) => Promise<unknown>;

/**
 * Toggle status config, supports multiple quick toggles (e.g. is_active, is_visible, is_published)
 * 切换状态配置，支持多个快捷开关（如 is_active, is_visible, is_published 等）
 */
export type ToggleStatusConfig = Record<string, ToggleStatusApi>;

/**
 * API configuration
 * API 配置
 *
 * Conventions:
 * 约定：
 * - `list`: Required, list query API / 必填，列表查询 API
 * - `resource`: Required, resource path (e.g. '/admin/admins', '/tenant/roles'),
 *   used to auto-construct DELETE requests: DELETE {resource}/{id}
 *   必填，资源路径，用于自动构造 DELETE 请求
 * - `toggles`: Optional, multiple quick toggle configs / 可选，多个快捷开关配置
 */
export interface CrudApiConfig<T = any> {
  /** List query API (required) / 列表查询 API（必填） */
  list: (params: Record<string, any>) => Promise<{ items: T[]; total: number }>;

  /**
   * Resource base path (required), used to auto-construct DELETE requests: DELETE {resource}/{id}
   * 资源基础路径（必填），用于自动构造 DELETE 请求：DELETE {resource}/{id}
   * @example '/admin/admins', '/admin/tenants', '/tenant/roles'
   */
  resource: string;

  /**
   * Custom delete API (optional). If not provided, DELETE request is auto-constructed from resource path.
   * 自定义删除 API（可选）。如不提供，将使用 resource 路径自动构造 DELETE 请求
   */
  delete?: (id: number) => Promise<unknown>;

  /**
   * Quick toggle config (supports multiple)
   * 快捷开关配置（支持多个）
   * @example
   * toggles: {
   *   is_active: admin.toggleAdminStatusApi,
   *   is_visible: admin.toggleAdminVisibilityApi,
   * }
   */
  toggles?: ToggleStatusConfig;
}

/**
 * Toolbar configuration / 工具栏配置
 */
export interface ToolbarConfig {
  custom?: boolean;
  export?: boolean;
  refresh?: boolean;
  search?: boolean;
  zoom?: boolean;
}

export interface CrudPageAiOptions {
  /** Page key matching registerPageOperations / 匹配 registerPageOperations 的页面标识 */
  pageKey?: string;
  /** Form schema factory for AI field extraction / 表单 schema 工厂函数，用于 AI 字段提取 */
  formSchema?: (isEdit?: boolean) => VbenFormSchema[];
  /** Detail route template / 详情页路由模板 */
  detailRoute?: string;
  /** Legacy disabled operation names / 旧版禁用操作名称列表 */
  disabled?: string[];
  /** Disabled capability groups / 禁用的能力分组 */
  disabledCapabilities?: PageAICapabilityKey[];
  /** Disabled operation names / 禁用的操作名称列表 */
  disabledOperations?: string[];
  /** Extra custom operations merged with standard ops / 额外自定义操作 */
  extra?: PageOperation[];
  /** Entity display name for AI context / AI 上下文中的实体显示名 */
  entityName?: string;
  /** Entity description for AI context / AI 上下文中的实体描述 */
  entityDescription?: string;
  /** Form purpose descriptions / 表单用途描述 */
  formPurpose?: {
    create?: string;
    edit?: string;
  };
  /** Extra page_data merged into auto-registered context / 合并到自动注册上下文的额外 page_data */
  contextExtras?: () => Record<string, unknown>;
  /** Table policy runtime capability block / 表策略运行时能力块 */
  tablePolicy?: TablePolicySupportConfig;
}

/**
 * useCrudPage configuration options / useCrudPage 配置选项
 */
export interface UseCrudPageOptions<T extends BaseRow = BaseRow> {
  /** API config (required) / API 配置（必填） */
  api: CrudApiConfig<T>;

  /** Column definition function (required) / 列定义函数（必填） */
  columns: ColumnsFactory<T>;

  /** Search form schema / 搜索表单 Schema */
  searchSchema?: VbenFormSchema[];

  /** Form component / 表单组件 */
  formComponent?: Component;

  /** Form type: drawer or modal, default drawer / 表单类型：drawer 或 modal，默认 drawer */
  formType?: 'drawer' | 'modal';

  /**
   * Form defaults for create mode, passed to form component via setData (_defaults field)
   * 新建模式的表单默认值，会通过 setData 传递给表单组件（_defaults 字段）
   */
  formDefaults?: (() => Record<string, any>) | Record<string, any>;

  /** i18n prefix (required) / i18n 前缀（必填） */
  i18nPrefix: string;

  /** Name field for display, default 'name' / 用于显示的名称字段，默认 'name' */
  nameField?: keyof T & string;

  /** Default sort field, default '-created_at' / 默认排序字段，默认 '-created_at' */
  defaultSort?: string;

  /** Row height, default 56 / 行高，默认 56 */
  rowHeight?: number;

  /** Enable pagination, default true / 是否启用分页，默认 true */
  pager?: boolean;

  /** Enable striped rows (alternating row backgrounds), default true / 是否启用斑马纹（交替行背景色），默认 true */
  stripe?: boolean;

  /** Toolbar config / 工具栏配置 */
  toolbar?: ToolbarConfig;

  /** Custom action handlers (for extending non-standard actions) / 自定义操作处理器（用于扩展非标准操作） */
  customActions?: Record<string, (row: T) => void>;

  /**
   * Create button permission code. When provided, CrudGrid auto-renders a permission-guarded create button in the left toolbar.
   * 创建按钮权限码。提供后 CrudGrid 会在左侧工具栏自动渲染带权限的创建按钮
   * @example 'ai_api_key:create'
   */
  createPermission?: string;

  /**
   * Recycle bin config
   * 回收站配置
   * - true: Enable with default config / 启用，使用默认配置
   * - RecycleBinConfig: Enable with custom config / 启用并自定义
   * - false/undefined: Disabled / 不启用
   */
  recycleBin?: boolean | RecycleBinConfig;

  /**
   * Extra VXE Grid config (deep-merged with internal defaults), for options not directly supported in useCrudPage like expandConfig, editConfig.
   * 额外的 VXE Grid 配置（会与内部默认配置深度合并），用于 expandConfig、editConfig 等不在 useCrudPage 中直接支持的选项
   * @example { expandConfig: { lazy: true, accordion: true } }
   */
  gridOptions?: Record<string, unknown>;

  /**
   * AI page awareness config.
   * - Omit / 省略: auto-enable page AI with inferred defaults / 自动启用并推导默认配置
   * - false: fully disable page AI for this CRUD page / 完全禁用该 CRUD 页的页面 AI
   * - CrudPageAiOptions: enable with overrides / 启用并覆盖默认配置
   */
  ai?: CrudPageAiOptions | false;
}

/**
 * Recycle bin configuration / 回收站配置
 */
export interface RecycleBinConfig {
  /** Name field, default 'name' / 名称字段，默认 'name' */
  nameField?: string;
  /** Custom column config / 自定义列配置 */
  columns?: Array<{ dataIndex: string; title: string; width?: number }>;
  /** Permission code override (auto-derived from createPermission when omitted) / 权限码覆盖（省略时从 createPermission 自动推导） */
  permission?: string;
}

/**
 * Grid options factory function params / 表格配置工厂函数参数
 */
export interface GridOptionsConfig {
  /** Column config (required) / 列配置（必填） */
  columns: any[];
  /** Query API function (required) / 查询 API 函数（必填） */
  queryApi: (params: Record<string, any>) => Promise<any>;
  /** Default sort field, default '-created_at' / 默认排序字段，默认 '-created_at' */
  defaultSort?: string;
  /** Row height, default 56 / 行高，默认 56 */
  rowHeight?: number;
  /** Enable pagination, default true / 是否启用分页，默认 true */
  pager?: boolean;
  /** Enable striped rows, default true / 是否启用斑马纹，默认 true */
  stripe?: boolean;
  /** Toolbar config, default show all / 工具栏配置，默认显示全部 */
  toolbar?: ToolbarConfig;
  /** Other custom config / 其他自定义配置 */
  [key: string]: any;
}
