import type { Component } from 'vue';
import type { Router, RouteRecordRaw } from 'vue-router';

/**
 * 页面 AI 策略模式
 *
 * - disabled:     该页面禁用 AI（隐藏入口）
 * - context_only: 仅提供页面上下文（默认值）
 * - navigation_only: 允许只读页面导航
 * - operate:      允许页面操作（预留，本轮不实现执行）
 */
type AIPageMode = 'context_only' | 'disabled' | 'navigation_only' | 'operate';

/**
 * 页面级 AI 元信息
 *
 * 声明在 route.meta.ai 中，与 RBAC 权限共同决定 AI 入口可见性。
 */
interface AIPageMeta {
  /** AI 模式 */
  mode?: AIPageMode;
  /** 页面上下文注册表 key（可选，用于 resolvePageContext 精确匹配） */
  pageContextKey?: string;
}

interface RouteMeta {
  /**
   * 需要具备的权限码（静态路由守卫使用）
   * @default []
   */
  accessCodes?: string[];
  /**
   * 权限码判定模式：`any` 任意一项满足，`all` 需要全部满足
   * @default 'any'
   */
  accessCodesMode?: 'all' | 'any';
  /**
   * 激活图标（菜单/tab）
   */
  activeIcon?: string;
  /**
   * 当前激活的菜单，有时候不想激活现有菜单，需要激活父级菜单时使用
   */
  activePath?: string;
  /**
   * 是否固定标签页
   * @default false
   */
  affixTab?: boolean;
  /**
   * 固定标签页的顺序
   * @default 0
   */
  affixTabOrder?: number;
  /**
   * 页面级 AI 策略（与 RBAC 权限共同控制 AI 入口可见性）
   *
   * 未声明时默认为 { mode: 'context_only' }
   */
  ai?: AIPageMeta;
  /**
   * 需要特定的角色标识才可以访问
   * @default []
   */
  authority?: string[];
  /**
   * 徽标
   */
  badge?: string;
  /**
   * 徽标类型
   */
  badgeType?: 'dot' | 'normal';
  /**
   * 徽标颜色
   */
  badgeVariants?:
    | 'default'
    | 'destructive'
    | 'primary'
    | 'success'
    | 'warning'
    | string;
  /**
   * 路由的完整路径作为key（默认true）
   */
  fullPathKey?: boolean;
  /**
   * 当前路由的子级在菜单中不展现
   * @default false
   */
  hideChildrenInMenu?: boolean;
  /**
   * 当前路由在面包屑中不展现
   * @default false
   */
  hideInBreadcrumb?: boolean;
  /**
   * 当前路由在菜单中不展现
   * @default false
   */
  hideInMenu?: boolean;
  /**
   * 当前路由在标签页不展现
   * @default false
   */
  hideInTab?: boolean;
  /**
   * 图标（菜单/tab）
   */
  icon?: Component | string;
  /**
   * iframe 地址
   */
  iframeSrc?: string;
  /**
   * 忽略权限，直接可以访问
   * @default false
   */
  ignoreAccess?: boolean;
  /**
   * 开启KeepAlive缓存
   */
  keepAlive?: boolean;
  /**
   * 外链-跳转路径
   */
  link?: string;
  /**
   * 路由是否已经加载过
   */
  loaded?: boolean;
  /**
   * 标签页最大打开数量
   * @default -1
   */
  maxNumOfOpenTab?: number;
  /**
   * 菜单可以看到，但是访问会被重定向到403
   */
  menuVisibleWithForbidden?: boolean;
  /**
   * 不使用基础布局（仅在顶级生效）
   */
  noBasicLayout?: boolean;
  /**
   * 在新窗口打开
   */
  openInNewWindow?: boolean;
  /**
   * 用于路由->菜单排序
   */
  order?: number;
  /**
   * 菜单所携带的参数
   */
  query?: Recordable;
  /**
   * 标题名称
   */
  title: string;
  /**
   * 路由标题多语言映射（用于插件等运行时动态标题）
   */
  titleLocaleMap?: Record<string, string>;
}

// 定义递归类型以将 RouteRecordRaw 的 component 属性更改为 string
type RouteRecordStringComponent<T = string> = Omit<
  RouteRecordRaw,
  'children' | 'component'
> & {
  children?: RouteRecordStringComponent<T>[];
  component?: T;
};

type ComponentRecordType = Record<string, () => Promise<Component>>;

interface GenerateMenuAndRoutesOptions {
  fetchMenuListAsync?: () => Promise<RouteRecordStringComponent[]>;
  forbiddenComponent?: RouteRecordRaw['component'];
  layoutMap?: ComponentRecordType;
  pageMap?: ComponentRecordType;
  roles?: string[];
  router: Router;
  routes: RouteRecordRaw[];
}

export type {
  AIPageMeta,
  AIPageMode,
  ComponentRecordType,
  GenerateMenuAndRoutesOptions,
  RouteMeta,
  RouteRecordRaw,
  RouteRecordStringComponent,
};
