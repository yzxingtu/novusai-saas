/**
 * 菜单数据转换器
 * 将后端返回的菜单数据格式转换为 vben-admin 框架需要的 RouteRecordStringComponent 格式
 */
import type { RouteRecordStringComponent } from '@vben/types';

import type { ApiEndpoint } from './types';

/**
 * 后端返回的菜单项原始格式（snake_case）
 * 根据 RBAC 权限管理开发规范定义
 */
export interface BackendMenuItemRaw {
  id?: number | string;
  code?: string;
  name: string;
  path: string;
  component?: string;
  redirect?: string;
  parent_id?: null | number | string;
  sort_order?: number;
  icon?: string;
  title?: string;
  hidden?: boolean;
  /** 该菜单关联的权限码列表 */
  permissions?: string[];
  // meta 字段可能是嵌套对象或扁平字段
  meta?: {
    affix_tab?: boolean;
    authority?: string[];
    badge?: string;
    badge_type?: string;
    badge_variants?: string;
    hide_in_breadcrumb?: boolean;
    hide_in_menu?: boolean;
    hide_in_tab?: boolean;
    icon?: string;
    iframe_src?: string;
    keep_alive?: boolean;
    link?: string;
    order?: number;
    title?: string;
  };
  children?: BackendMenuItemRaw[];
}

/**
 * 从菜单数据中递归提取所有权限码
 * @param menus 菜单列表
 * @returns 去重后的权限码数组
 */
export function extractPermissionsFromMenus(
  menus: BackendMenuItemRaw[],
): string[] {
  const permissions = new Set<string>();

  function traverse(items: BackendMenuItemRaw[]) {
    for (const item of items) {
      // 提取当前菜单的权限码
      if (item.permissions && Array.isArray(item.permissions)) {
        for (const code of item.permissions) {
          permissions.add(code);
        }
      }
      // 递归处理子菜单
      if (item.children && item.children.length > 0) {
        traverse(item.children);
      }
    }
  }

  traverse(menus);
  return [...permissions];
}

/**
 * 转换组件路径
 * 将后端返回的组件路径转换为前端 views 目录下的实际路径
 * 支持两种结构：
 *   - 文件结构: tenant/List -> /admin/tenant/list.vue
 *   - 目录结构: tenant/List -> /admin/tenant/list/index.vue (优先)
 * @param component 后端组件路径，如 tenant/List
 * @param endpoint 端类型
 * @returns 前端组件路径
 */
function transformComponentPath(
  component: string | undefined,
  endpoint: ApiEndpoint,
): string {
  if (!component) return '';

  // 如果是 layout 组件，不做转换
  if (component === 'BasicLayout' || component === 'IFrameView') {
    return component;
  }

  // 标准化路径：确保以 / 开头
  const path = component.startsWith('/') ? component : `/${component}`;

  // 割离目录和文件名
  const lastSlash = path.lastIndexOf('/');
  const dirPath = path.slice(0, lastSlash + 1);
  let fileName = path.slice(lastSlash + 1);

  // 移除 .vue 后缀（如果有）
  if (fileName.endsWith('.vue')) {
    fileName = fileName.slice(0, -4);
  }

  // 文件名转小写
  fileName = fileName.toLowerCase();

  // 根据端类型添加前缀
  let prefix = '';
  if (endpoint === 'admin' && !path.startsWith('/admin/')) {
    prefix = '/admin';
  } else if (endpoint === 'tenant' && !path.startsWith('/tenant/')) {
    prefix = '/tenant';
  }

  // 优先尝试目录结构: /admin/tenant/list/index.vue
  const dirStructurePath = `${prefix}${dirPath}${fileName}/index.vue`;
  if (componentExists(dirStructurePath)) {
    return dirStructurePath;
  }

  // 回退到文件结构: /admin/tenant/list.vue
  const fileStructurePath = `${prefix}${dirPath}${fileName}.vue`;
  return fileStructurePath;
}

/**
 * 转换路由路径
 * 根据端类型添加前缀
 * @param path 后端返回的路径，如 /system/admins
 * @param endpoint 端类型
 * @returns 带前缀的路径，如 /admin/system/admins
 */
function transformRoutePath(path: string, endpoint: ApiEndpoint): string {
  if (!path) return '';

  // 确保路径以 / 开头
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  // 根据端类型添加前缀
  if (endpoint === 'admin' && !normalizedPath.startsWith('/admin')) {
    return `/admin${normalizedPath}`;
  }
  if (endpoint === 'tenant' && !normalizedPath.startsWith('/tenant')) {
    return `/tenant${normalizedPath}`;
  }
  // user 端不添加前缀
  return normalizedPath;
}

/**
 * 转换单个菜单项
 * @param item 后端菜单项
 * @param endpoint 端类型
 * @returns vben-admin 格式的菜单项
 */
function transformMenuItem(
  item: BackendMenuItemRaw,
  endpoint: ApiEndpoint,
): RouteRecordStringComponent {
  // 构建 meta 对象
  // 后端的 name 字段是菜单显示名称，应作为 meta.title
  // 这是最重要的字段，必须设置，否则框架的 $t() 函数会报错
  const meta: Record<
    string,
    boolean | number | string | string[] | undefined
  > & { title: string } = {
    title: item.name,
  };

  // 处理 meta 字段（可能来自嵌套对象或扁平字段）
  if (item.meta) {
    // 后端返回的 meta 对象（如果有显式的 title，覆盖默认值）
    if (item.meta.title) meta.title = item.meta.title;
    if (item.meta.icon) meta.icon = item.meta.icon;
    if (item.meta.order !== undefined) meta.order = item.meta.order;
    if (item.meta.hide_in_menu) meta.hideInMenu = item.meta.hide_in_menu;
    if (item.meta.hide_in_tab) meta.hideInTab = item.meta.hide_in_tab;
    if (item.meta.hide_in_breadcrumb)
      meta.hideInBreadcrumb = item.meta.hide_in_breadcrumb;
    if (item.meta.affix_tab) meta.affixTab = item.meta.affix_tab;
    if (item.meta.keep_alive) meta.keepAlive = item.meta.keep_alive;
    if (item.meta.badge) meta.badge = item.meta.badge;
    if (item.meta.badge_type) meta.badgeType = item.meta.badge_type;
    if (item.meta.badge_variants) meta.badgeVariants = item.meta.badge_variants;
    if (item.meta.authority) meta.authority = item.meta.authority;
    if (item.meta.iframe_src) meta.iframeSrc = item.meta.iframe_src;
    if (item.meta.link) meta.link = item.meta.link;
  }

  // 处理扁平字段（兼容不同后端格式）
  if (item.title && item.title !== meta.title) meta.title = item.title;
  if (item.icon && !meta.icon) meta.icon = item.icon;
  if (item.sort_order !== undefined && meta.order === undefined)
    meta.order = item.sort_order;
  if (item.hidden) meta.hideInMenu = item.hidden;

  // 生成路由名称（使用 code 字段或根据 path 生成）
  // 路由名称应该是唯一标识符，不能使用中文
  const routeName = item.code || generateRouteName(item.path, endpoint);

  // 转换路由路径（添加端前缀）
  const routePath = transformRoutePath(item.path, endpoint);

  // 构建路由项
  const transformedComponent = transformComponentPath(item.component, endpoint);
  const route: RouteRecordStringComponent = {
    name: routeName,
    path: routePath,
    // 空组件路径（如插件菜单）用 undefined 而非 '' —— 避免 Vue Router 将空字符串视为无效 component 并报警告
    component: transformedComponent || undefined,
    meta,
  };

  // 添加可选字段（redirect 也需要添加前缀）
  if (item.redirect) {
    route.redirect = transformRoutePath(item.redirect, endpoint);
  }

  // 递归处理子菜单
  if (item.children && item.children.length > 0) {
    route.children = item.children.map((child) =>
      transformMenuItem(child, endpoint),
    );
  }

  return route;
}

/** 用于收集缺失组件的提示信息 */
interface MissingComponentInfo {
  menuName: string;
  componentPath: string;
  expectedFile: string;
}

/** 组件映射表类型 */
type ComponentMap = Record<string, unknown>;

/** 缓存已存在的组件路径（从 pageMap 解析） */
let cachedExistingPaths: null | Set<string> = null;

/**
 * 设置已存在的组件映射表
 * 这个函数应该在应用启动时调用，传入 import.meta.glob 的结果
 * @param pageMap 组件映射表
 */
export function setExistingComponents(pageMap: ComponentMap): void {
  cachedExistingPaths = new Set<string>();
  for (const key of Object.keys(pageMap)) {
    // 解析路径：../views/admin/dashboard/index.vue -> /admin/dashboard/index.vue
    const normalizedPath = key.replace(/^\.\.?\/views/, '').toLowerCase();
    cachedExistingPaths.add(normalizedPath);
  }
}

/**
 * 检查组件是否存在
 * @param componentPath 组件路径，如 /admin/dashboard/index.vue
 */
function componentExists(componentPath: string): boolean {
  if (!cachedExistingPaths) {
    // 如果没有设置 pageMap，无法检查，默认认为不存在
    return false;
  }
  return cachedExistingPaths.has(componentPath.toLowerCase());
}

/**
 * 转换菜单列表
 * 将后端返回的菜单数据转换为 vben-admin 框架格式
 * @param menus 后端菜单列表
 * @param endpoint 端类型，用于确定组件路径前缀
 * @returns vben-admin 格式的菜单列表
 */
/** 日志前缀 */
const LOG_TAG = '[DynamicMenu]';

export function transformMenuData(
  menus: BackendMenuItemRaw[],
  endpoint: ApiEndpoint = 'admin',
): RouteRecordStringComponent[] {
  if (!Array.isArray(menus)) {
    console.warn(`${LOG_TAG} Invalid menu data:`, menus);
    return [];
  }

  // 收集缺失的组件信息
  const missingComponents: MissingComponentInfo[] = [];

  const result = menus.map((item) =>
    transformMenuItemWithCheck(item, endpoint, missingComponents),
  );

  // 输出友好的警告信息
  if (missingComponents.length > 0) {
    printMissingComponentsWarning(missingComponents, endpoint);
  }

  return result;
}

/**
 * 转换单个菜单项并检查组件
 */
function transformMenuItemWithCheck(
  item: BackendMenuItemRaw,
  endpoint: ApiEndpoint,
  missingComponents: MissingComponentInfo[],
): RouteRecordStringComponent {
  const route = transformMenuItem(item, endpoint);

  // 检查是否有组件路径（排除父级菜单和 layout 组件）
  if (
    route.component &&
    route.component !== 'BasicLayout' &&
    route.component !== 'IFrameView' &&
    route.component !== '' && // 只记录真正缺失的组件
    !componentExists(route.component)
  ) {
    missingComponents.push({
      menuName: item.name,
      componentPath: route.component,
      expectedFile: `src/views${route.component}`,
    });
  }

  // 递归处理子菜单
  if (item.children && item.children.length > 0) {
    route.children = item.children.map((child) =>
      transformMenuItemWithCheck(child, endpoint, missingComponents),
    );
  }

  return route;
}

/**
 * 输出缺失组件的警告信息
 */
function printMissingComponentsWarning(
  missingComponents: MissingComponentInfo[],
  endpoint: ApiEndpoint,
): void {
  let endpointName: string;
  if (endpoint === 'admin') {
    endpointName = 'Admin';
  } else if (endpoint === 'tenant') {
    endpointName = 'Tenant';
  } else {
    endpointName = 'User';
  }

  const componentList = missingComponents
    .map(({ menuName, expectedFile }) => `  - "${menuName}" -> ${expectedFile}`)
    .join('\n');

  console.warn(
    `${LOG_TAG} ${endpointName}: ${missingComponents.length} menu component(s) not found:\n` +
      `Please create the corresponding Vue component files:\n${componentList}\n` +
      `Note: these menus will show as 404 pages until the components are created.`,
  );
}

/**
 * 根据路径生成路由名称
 * @param path 路由路径
 * @param endpoint 端类型
 * @returns 路由名称
 */
function generateRouteName(path: string, endpoint: ApiEndpoint): string {
  // 将路径转换为路由名称，如 /system/admins -> admin.system.admins
  const cleanPath = path.replace(/^\//, '').replaceAll('/', '.');
  return `${endpoint}.${cleanPath || 'index'}`;
}

/**
 * 判断后端返回的菜单是否需要转换
 * 如果后端返回的数据已经是 camelCase 格式，则不需要转换
 * @param menus 菜单数据
 * @returns 是否需要转换
 */
export function needsTransform(menus: unknown[]): boolean {
  if (!Array.isArray(menus) || menus.length === 0) {
    return false;
  }

  const firstItem = menus[0] as Record<string, unknown>;

  // Check for snake_case fields
  return (
    'parent_id' in firstItem ||
    'sort_order' in firstItem ||
    (typeof firstItem.meta === 'object' &&
      firstItem.meta !== null &&
      ('hide_in_menu' in (firstItem.meta as Record<string, unknown>) ||
        'hide_in_tab' in (firstItem.meta as Record<string, unknown>) ||
        'affix_tab' in (firstItem.meta as Record<string, unknown>)))
  );
}
