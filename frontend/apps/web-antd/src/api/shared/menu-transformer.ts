/**
 * Menu data transformer / 菜单数据转换器
 * Converts backend menu data to vben-admin RouteRecordStringComponent format
 * 将后端返回的菜单数据转换为框架所需格式
 */
import type { RouteRecordStringComponent } from '@vben/types';

import type { ApiEndpoint } from './types';

/**
 * Backend menu item raw format (snake_case) / 后端菜单项原始格式
 * Defined per RBAC permission management spec / 根据 RBAC 权限管理规范定义
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
  /** Permission codes associated with this menu / 菜单关联的权限码列表 */
  permissions?: string[];
  // meta field can be nested object or flat fields / meta 字段可能是嵌套对象或扁平字段
  meta?: {
    affix_tab?: boolean;
    ai?: {
      capabilities?: string[];
      category?: string;
      description?: string;
      keywords?: string[];
      mode?: string;
    };
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

const PLUGIN_STANDALONE_ROUTE_PREFIXES = [
  '/admin/plugins/',
  '/tenant/plugins/',
] as const;

/**
 * Recursively extract all permission codes from menu data / 从菜单数据中递归提取所有权限码
 * @param menus Menu list / 菜单列表
 * @returns Deduplicated permission code array / 去重后的权限码数组
 */
export function extractPermissionsFromMenus(
  menus: BackendMenuItemRaw[],
): string[] {
  const permissions = new Set<string>();

  function traverse(items: BackendMenuItemRaw[]) {
    for (const item of items) {
      if (typeof item.code === 'string' && item.code.trim().length > 0) {
        permissions.add(item.code.trim());
      }
      // Extract current menu's permission codes / 提取当前菜单的权限码
      if (item.permissions && Array.isArray(item.permissions)) {
        for (const code of item.permissions) {
          permissions.add(code);
        }
      }
      // Recursively process child menus / 递归处理子菜单
      if (item.children && item.children.length > 0) {
        traverse(item.children);
      }
    }
  }

  traverse(menus);
  return [...permissions];
}

/**
 * Transform component path / 转换组件路径
 * Converts backend component path to actual frontend views path.
 * Supports two structures:
 *   - File: tenant/List -> /admin/tenant/list.vue
 *   - Directory (preferred): tenant/List -> /admin/tenant/list/index.vue
 * @param component Backend component path / 后端组件路径
 * @param endpoint Endpoint type / 端类型
 * @returns Frontend component path / 前端组件路径
 */
function transformComponentPath(
  component: string | undefined,
  endpoint: ApiEndpoint,
): string {
  if (!component) return '';

  // If layout component, no conversion needed / layout 组件不转换
  if (component === 'BasicLayout' || component === 'IFrameView') {
    return component;
  }

  // Normalize path: ensure starts with / / 标准化路径
  const path = component.startsWith('/') ? component : `/${component}`;

  // Split directory and file name / 分离目录和文件名
  const lastSlash = path.lastIndexOf('/');
  const dirPath = path.slice(0, lastSlash + 1);
  let fileName = path.slice(lastSlash + 1);

  // Remove .vue suffix (if present) / 移除 .vue 后缀
  if (fileName.endsWith('.vue')) {
    fileName = fileName.slice(0, -4);
  }

  // Lowercase file name / 文件名转小写
  fileName = fileName.toLowerCase();

  // Add prefix based on endpoint type / 根据端类型添加前缀
  let prefix = '';
  if (endpoint === 'admin' && !path.startsWith('/admin/')) {
    prefix = '/admin';
  } else if (endpoint === 'tenant' && !path.startsWith('/tenant/')) {
    prefix = '/tenant';
  }

  // Prefer directory structure: /admin/tenant/list/index.vue / 优先目录结构
  const dirStructurePath = `${prefix}${dirPath}${fileName}/index.vue`;
  if (componentExists(dirStructurePath)) {
    return dirStructurePath;
  }

  // Fallback to file structure: /admin/tenant/list.vue / 回退文件结构
  const fileStructurePath = `${prefix}${dirPath}${fileName}.vue`;
  return fileStructurePath;
}

/**
 * Transform route path / 转换路由路径
 * Adds endpoint prefix to path / 根据端类型添加前缀
 * @param path Backend path, e.g. /system/admins / 后端路径
 * @param endpoint Endpoint type / 端类型
 * @returns Prefixed path, e.g. /admin/system/admins / 带前缀的路径
 */
function transformRoutePath(path: string, endpoint: ApiEndpoint): string {
  if (!path) return '';

  // Ensure path starts with / / 确保路径以 / 开头
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  // Add prefix based on endpoint type / 根据端类型添加前缀
  if (endpoint === 'admin' && !normalizedPath.startsWith('/admin')) {
    return `/admin${normalizedPath}`;
  }
  if (endpoint === 'tenant' && !normalizedPath.startsWith('/tenant')) {
    return `/tenant${normalizedPath}`;
  }
  // User endpoint: no prefix / user 端不添加前缀
  return normalizedPath;
}

/**
 * Transform single menu item / 转换单个菜单项
 * @param item Backend menu item / 后端菜单项
 * @param endpoint Endpoint type / 端类型
 * @returns vben-admin format menu item / vben-admin 格式菜单项
 */
function transformMenuItem(
  item: BackendMenuItemRaw,
  endpoint: ApiEndpoint,
): RouteRecordStringComponent {
  // Build meta object / 构建 meta 对象
  // Backend 'name' is display name, used as meta.title (required for framework $t()) / 后端 name 为展示名，用作 meta.title
  // 后端 name 是显示名称，作为 meta.title（框架 $t() 必须）
  const meta: Record<
    string,
    boolean | number | string | string[] | undefined
  > & { title: string } = {
    title: item.name,
  };

  // Process meta fields (may come from nested object or flat fields) / 处理 meta 字段
  if (item.meta) {
    // Backend meta object (explicit title overrides default) / 后端 meta 对象
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
    if (item.meta.ai) {
      const aiMeta: Record<string, unknown> = {};
      if (item.meta.ai.description)
        aiMeta.description = item.meta.ai.description;
      if (item.meta.ai.category) aiMeta.category = item.meta.ai.category;
      if (item.meta.ai.keywords) aiMeta.keywords = item.meta.ai.keywords;
      if (item.meta.ai.capabilities) {
        aiMeta.capabilities = item.meta.ai.capabilities;
      }
      if (item.meta.ai.mode) aiMeta.mode = item.meta.ai.mode;
      if (Object.keys(aiMeta).length > 0) {
        (meta as Record<string, unknown>).ai = aiMeta;
      }
    }
  }

  // Process flat fields (compat with different backend formats) / 处理扁平字段
  if (item.title && item.title !== meta.title) meta.title = item.title;
  if (item.icon && !meta.icon) meta.icon = item.icon;
  if (item.sort_order !== undefined && meta.order === undefined)
    meta.order = item.sort_order;
  if (item.hidden) meta.hideInMenu = item.hidden;

  // Generate route name (use code field or generate from path) / 生成路由名称
  // Route name must be a unique identifier, no Chinese / 路由名称必须是唯一标识符
  const routeName = item.code || generateRouteName(item.path, endpoint);

  // Transform route path (add endpoint prefix) / 转换路由路径
  const routePath = transformRoutePath(item.path, endpoint);

  // Build route item / 构建路由项
  const transformedComponent = isPluginStandalonePageMenu(item)
    ? ''
    : transformComponentPath(item.component, endpoint);
  const route: RouteRecordStringComponent = {
    name: routeName,
    path: routePath,
    // Empty component path (e.g. plugin menus) uses undefined instead of '' to avoid Vue Router warning / 空组件路径用 undefined 避免 Vue Router 警告
    // 空组件路径用 undefined 而非 '' 避免 Vue Router 警告
    component: transformedComponent || undefined,
    meta,
  };

  // Add optional fields (redirect also needs prefix) / 添加可选字段
  if (item.redirect) {
    route.redirect = transformRoutePath(item.redirect, endpoint);
  }

  // Recursively process child menus / 递归处理子菜单
  if (item.children && item.children.length > 0) {
    route.children = item.children.map((child) =>
      transformMenuItem(child, endpoint),
    );
  }

  return route;
}

function isPluginStandalonePageMenu(item: BackendMenuItemRaw): boolean {
  const path = item.path ?? '';
  return PLUGIN_STANDALONE_ROUTE_PREFIXES.some((prefix) =>
    path.startsWith(prefix),
  );
}

/** Missing component info for logging / 缺失组件提示信息 */
interface MissingComponentInfo {
  menuName: string;
  componentPath: string;
  expectedFile: string;
}

/** Component map type / 组件映射表类型 */
type ComponentMap = Record<string, unknown>;

/** Cached existing component paths (parsed from pageMap) / 缓存已存在的组件路径 */
let cachedExistingPaths: null | Set<string> = null;

/**
 * Set existing component map / 设置已存在的组件映射表
 * Should be called at app startup with import.meta.glob result
 * 应在应用启动时调用
 * @param pageMap Component map / 组件映射表
 */
export function setExistingComponents(pageMap: ComponentMap): void {
  cachedExistingPaths = new Set<string>();
  for (const key of Object.keys(pageMap)) {
    // Parse path: ../views/admin/dashboard/index.vue -> /admin/dashboard/index.vue / 解析路径
    const normalizedPath = key.replace(/^\.\.?\/views/, '').toLowerCase();
    cachedExistingPaths.add(normalizedPath);
  }
}

/**
 * Check if component exists / 检查组件是否存在
 * @param componentPath Component path, e.g. /admin/dashboard/index.vue / 组件路径
 */
function componentExists(componentPath: string): boolean {
  if (!cachedExistingPaths) {
    // If pageMap not set, cannot check, default to not exists / 未设置 pageMap 默认不存在
    return false;
  }
  return cachedExistingPaths.has(componentPath.toLowerCase());
}

/**
 * Transform menu list / 转换菜单列表
 * Converts backend menu data to vben-admin framework format
 * @param menus Backend menu list / 后端菜单列表
 * @param endpoint Endpoint type, determines component path prefix / 端类型
 * @returns vben-admin format menu list / vben-admin 格式菜单列表
 */
/** Log prefix / 日志前缀 */
const LOG_TAG = '[DynamicMenu]';

export function transformMenuData(
  menus: BackendMenuItemRaw[],
  endpoint: ApiEndpoint = 'admin',
): RouteRecordStringComponent[] {
  if (!Array.isArray(menus)) {
    console.warn(`${LOG_TAG} Invalid menu data:`, menus);
    return [];
  }

  // Collect missing component info / 收集缺失的组件信息
  const missingComponents: MissingComponentInfo[] = [];

  const result = menus.map((item) =>
    transformMenuItemWithCheck(item, endpoint, missingComponents),
  );

  // Output friendly warning / 输出友好的警告信息
  if (missingComponents.length > 0) {
    printMissingComponentsWarning(missingComponents, endpoint);
  }

  return result;
}

/**
 * Transform single menu item and check component / 转换单个菜单项并检查组件
 */
function transformMenuItemWithCheck(
  item: BackendMenuItemRaw,
  endpoint: ApiEndpoint,
  missingComponents: MissingComponentInfo[],
): RouteRecordStringComponent {
  const route = transformMenuItem(item, endpoint);

  // Check component path (exclude parent menus and layout components) / 检查组件路径
  if (
    route.component &&
    route.component !== 'BasicLayout' &&
    route.component !== 'IFrameView' &&
    route.component !== '' && // Only record truly missing components / 只记录真正缺失的组件
    !componentExists(route.component)
  ) {
    missingComponents.push({
      menuName: item.name,
      componentPath: route.component,
      expectedFile: `src/views${route.component}`,
    });
  }

  // Recursively process child menus / 递归处理子菜单
  if (item.children && item.children.length > 0) {
    route.children = item.children.map((child) =>
      transformMenuItemWithCheck(child, endpoint, missingComponents),
    );
  }

  return route;
}

/**
 * Print missing components warning (forward check) / 打印缺失组件告警（前置检查）
 * Uses console.error in DEV for high visibility (red highlight in devtools).
 */
function printMissingComponentsWarning(
  missingComponents: MissingComponentInfo[],
  endpoint: ApiEndpoint,
): void {
  const endpointName = getEndpointDisplayName(endpoint);

  const componentList = missingComponents
    .map(({ menuName, expectedFile }) => `  - "${menuName}" -> ${expectedFile}`)
    .join('\n');

  const msg =
    `${LOG_TAG} [CRITICAL] ${endpointName}: ${missingComponents.length} menu component(s) not found:\n` +
    `Please create the corresponding Vue component files:\n${componentList}\n` +
    `Note: these menus will show as 404 pages until the components are created.`;

  if (import.meta.env.DEV) {
    console.error(msg);
  } else {
    console.warn(msg);
  }
}

/**
 * Generate route name from path / 根据路径生成路由名称
 * @param path Route path / 路由路径
 * @param endpoint Endpoint type / 端类型
 * @returns Route name / 路由名称
 */
function generateRouteName(path: string, endpoint: ApiEndpoint): string {
  // Convert path to route name, e.g. /system/admins -> admin.system.admins / 路径转路由名
  const cleanPath = path.replace(/^\//, '').replaceAll('/', '.');
  return `${endpoint}.${cleanPath || 'index'}`;
}

/**
 * Recursively collect all component paths from transformed menu routes.
 * 从转换后的菜单路由中递归收集所有组件路径。
 */
export function collectMenuComponentPaths(
  routes: RouteRecordStringComponent[],
): Set<string> {
  const paths = new Set<string>();
  function traverse(items: RouteRecordStringComponent[]) {
    for (const route of items) {
      if (
        route.component &&
        typeof route.component === 'string' &&
        route.component !== 'BasicLayout' &&
        route.component !== 'IFrameView'
      ) {
        paths.add(route.component.toLowerCase());
      }
      if (route.children && route.children.length > 0) {
        traverse(route.children as RouteRecordStringComponent[]);
      }
    }
  }
  traverse(routes);
  return paths;
}

/** Patterns for views that are legitimately hidden (no menu entry needed). / 无需菜单项的正规隐藏视图匹配规则 */
const ORPHAN_EXCLUDED_PATTERNS: RegExp[] = [
  /authentication\//,
  /_core\//,
  /modules\//,
  /profile\//,
  /dashboard\//,
  /analytics\//,
  /detail\.vue$/,
  /impersonate/,
  /(?:modal|drawer|wizard|progress)\.vue$/,
];

/**
 * Reverse check: detect view files that have no menu entry or static route.
 * Only runs in DEV mode.
 * 反向校验：检测存在但无菜单入口/静态路由的页面文件（仅 DEV 模式）。
 */
export function checkOrphanedViews(
  menuComponentPaths: Set<string>,
  staticRoutePaths: Set<string>,
  endpoint: ApiEndpoint,
): void {
  if (!import.meta.env.DEV || !cachedExistingPaths) return;

  const orphaned: string[] = [];
  for (const viewPath of cachedExistingPaths) {
    if (!viewPath.startsWith(`/${endpoint}/`)) continue;
    if (ORPHAN_EXCLUDED_PATTERNS.some((p) => p.test(viewPath))) continue;
    if (menuComponentPaths.has(viewPath)) continue;
    if (staticRoutePaths.has(viewPath)) continue;
    orphaned.push(viewPath);
  }

  if (orphaned.length > 0) {
    const endpointName = getEndpointDisplayName(endpoint);
    console.warn(
      `[MenuCheck] ${endpointName}: ${orphaned.length} view(s) have no menu entry or static route:\n${orphaned
        .map((p) => `  - src/views${p}`)
        .join(
          '\n',
        )}\nThese pages exist but cannot be accessed from the sidebar. ` +
        `Register them in backend menu definitions or frontend static routes.`,
    );
  }
}

function getEndpointDisplayName(
  endpoint: ApiEndpoint,
): 'Admin' | 'Tenant' | 'User' {
  if (endpoint === 'admin') {
    return 'Admin';
  }
  if (endpoint === 'tenant') {
    return 'Tenant';
  }
  return 'User';
}

/**
 * Check if backend menu data needs transformation / 判断菜单是否需要转换
 * If data is already in camelCase format, no conversion needed
 * @param menus Menu data / 菜单数据
 * @returns Whether transformation is needed / 是否需要转换
 */
export function needsTransform(menus: unknown[]): boolean {
  if (!Array.isArray(menus) || menus.length === 0) {
    return false;
  }

  const firstItem = menus[0] as Record<string, unknown>;

  // Check for snake_case fields / 检查 snake_case 字段
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
