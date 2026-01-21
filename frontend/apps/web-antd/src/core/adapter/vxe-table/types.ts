/**
 * 声明式表格类型定义
 */
import type { Component } from 'vue';

import type { Recordable } from '@vben/types';

import type { VbenFormSchema } from '#/adapter/form';

// 从 vben 插件导出基础类型
export type { VxeTableGridOptions } from '@vben/plugins/vxe-table';

/**
 * 操作按钮点击参数
 */
export interface OnActionClickParams<T = Recordable<any>> {
  code: string;
  row: T;
}

/**
 * 操作按钮点击回调函数
 */
export type OnActionClickFn<T = Recordable<any>> = (
  params: OnActionClickParams<T>,
) => void;

/**
 * 基础行数据接口
 */
export interface BaseRow {
  id: number | string;
  isActive?: boolean;
  is_active?: boolean;
  name?: string;
  [key: string]: any;
}

/**
 * 表单操作模式
 */
export type FormMode = 'add' | 'copy' | 'edit' | 'view';

/**
 * 列定义函数类型
 * 返回 VxeTableGridOptions['columns'] 类型（可以是 undefined）
 */

export type ColumnsFactory<_T = any> = (...args: any[]) => any[] | undefined;

/**
 * 切换状态 API 类型
 * 接受 id 和状态数据，返回 Promise
 */

export type ToggleStatusApi = (id: any, data: any) => Promise<unknown>;

/**
 * 切换状态配置
 * 支持多个快捷开关（如 is_active, is_visible, is_published 等）
 */
export type ToggleStatusConfig = Record<string, ToggleStatusApi>;

/**
 * API 配置
 *
 * 约定：
 * - `list`: 必填，列表查询 API
 * - `resource`: 必填，资源路径（如 '/admin/admins', '/tenant/roles'）
 *   用于自动构造 DELETE 请求：DELETE {resource}/{id}
 * - `toggles`: 可选，多个快捷开关配置
 */
export interface CrudApiConfig<T = any> {
  /** 列表查询 API（必填） */
  list: (params: Record<string, any>) => Promise<{ items: T[]; total: number }>;

  /**
   * 资源基础路径（必填）
   * 用于自动构造 DELETE 请求：DELETE {resource}/{id}
   * @example '/admin/admins', '/admin/tenants', '/tenant/roles'
   */
  resource: string;

  /**
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
 * 工具栏配置
 */
export interface ToolbarConfig {
  custom?: boolean;
  export?: boolean;
  refresh?: boolean;
  search?: boolean;
  zoom?: boolean;
}

/**
 * useCrudPage 配置选项
 */
export interface UseCrudPageOptions<T extends BaseRow = BaseRow> {
  /** API 配置（必填） */
  api: CrudApiConfig<T>;

  /** 列定义函数（必填） */
  columns: ColumnsFactory<T>;

  /** 搜索表单 Schema */
  searchSchema?: VbenFormSchema[];

  /** 表单组件 */
  formComponent?: Component;

  /** 表单类型：drawer 或 modal，默认 drawer */
  formType?: 'drawer' | 'modal';

  /**
   * 新建模式的表单默认值
   * 会通过 setData 传递给表单组件，表单组件需支持 _defaults 字段
   */
  formDefaults?: (() => Record<string, any>) | Record<string, any>;

  /** i18n 前缀（必填） */
  i18nPrefix: string;

  /** 用于显示的名称字段，默认 'name' */
  nameField?: keyof T & string;

  /** 默认排序字段，默认 '-created_at' */
  defaultSort?: string;

  /** 行高，默认 64 */
  rowHeight?: number;

  /** 是否启用分页，默认 true */
  pager?: boolean;

  /** 是否启用斑马纹（交替行背景色），默认 true */
  stripe?: boolean;

  /** 工具栏配置 */
  toolbar?: ToolbarConfig;

  /** 自定义操作处理器（用于扩展非标准操作） */
  customActions?: Record<string, (row: T) => void>;
}

/**
 * 表格配置工厂函数参数
 */
export interface GridOptionsConfig {
  /** 列配置（必填） */
  columns: any[];
  /** 查询 API 函数（必填） */
  queryApi: (params: Record<string, any>) => Promise<any>;
  /** 默认排序字段，默认 '-created_at' */
  defaultSort?: string;
  /** 行高，默认 64 */
  rowHeight?: number;
  /** 是否启用分页，默认 true */
  pager?: boolean;
  /** 是否启用斑马纹（交替行背景色），默认 true */
  stripe?: boolean;
  /** 工具栏配置，默认显示全部 */
  toolbar?: ToolbarConfig;
  /** 其他自定义配置 */
  [key: string]: any;
}
