/**
 * Page Context Collector / 页面上下文收集器
 *
 * Collects current page context (route, title, params, API info) for AI chat.
 * 收集当前页面上下文信息，供 AI 对话智能体参考。
 */
import { useTabbarStore } from '@vben/stores';

import { useRoute } from 'vue-router';

import { resolveRuntimeLocale } from '#/locales/runtime-locale';

/** 页面上下文信息 / Page context payload sent to the backend */
export interface PageContext {
  /** 当前页面相关的 API 端点列表（可选） */
  available_apis: string[];
  /** 当前用户语言偏好（如 zh-CN、en-US） */
  locale: string;
  /** 页面功能描述 */
  page_description: string;
  /** 页面标题 */
  page_title: string;
  /** URL 查询参数 */
  query_params: Record<string, string>;
  /** 路由名称 */
  route_name: string;
  /** 当前路由路径 */
  route_path: string;
}

/**
 * 从路由 meta 中提取可用 API 端点列表。
 * Extracts available API endpoints from route meta if configured.
 */
function extractAvailableApis(routeMeta: Record<string, unknown>): string[] {
  const apis = routeMeta.apiEndpoints;
  if (Array.isArray(apis)) {
    return apis.filter((item): item is string => typeof item === 'string');
  }
  return [];
}

/**
 * 从路由 meta 中提取页面描述。
 * Extracts page description from route meta.
 */
function extractPageDescription(routeMeta: Record<string, unknown>): string {
  const desc = routeMeta.description || routeMeta.helpText;
  return typeof desc === 'string' ? desc : '';
}

/**
 * 从 tabbar store 获取当前标签页标题。
 * Gets the current tab title from the tabbar store.
 */
function getCurrentTabTitle(routePath: string): string {
  try {
    const tabbarStore = useTabbarStore();
    const tabs = tabbarStore.getTabs;
    const currentTab = tabs.find((tab) => tab.path === routePath);
    if (currentTab) {
      // TabDefinition may have title or _title depending on version
      const tabWithTitle = currentTab as unknown as Record<string, unknown>;
      const title = tabWithTitle.title || tabWithTitle._title;
      if (typeof title === 'string') {
        return title;
      }
    }
  } catch {
    // tabbar store may not be available in all contexts
  }
  return '';
}

/**
 * 收集当前页面上下文信息。
 * Collects the current page context for AI conversation enrichment.
 *
 * 在 Vue 组件 setup 或 composable 中调用（需要 Vue 实例上下文）。
 * Must be called within a Vue component setup or composable (requires Vue instance context).
 */
export function collectCurrentPageContext(): PageContext {
  const route = useRoute();
  const routePath = route.path || '';
  const routeName = (route.name as string) || '';
  const routeMeta = (route.meta || {}) as Record<string, unknown>;

  // 页面标题：优先从路由 meta.title 获取，其次从 tabbar 获取
  const metaTitle =
    typeof routeMeta.title === 'string' ? routeMeta.title : '';
  const pageTitle = metaTitle || getCurrentTabTitle(routePath) || routeName;

  // 查询参数
  const queryParams: Record<string, string> = {};
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === 'string') {
      queryParams[key] = value;
    } else if (Array.isArray(value) && value.length > 0) {
      queryParams[key] = String(value[0]);
    }
  }

  return {
    available_apis: extractAvailableApis(routeMeta),
    locale: resolveRuntimeLocale(),
    page_description: extractPageDescription(routeMeta),
    page_title: pageTitle,
    query_params: queryParams,
    route_name: routeName,
    route_path: routePath,
  };
}

/**
 * 将 PageContext 序列化为简短摘要文本（用于欢迎语等场景）。
 * Serializes PageContext into a brief summary string.
 */
export function summarizePageContext(ctx: PageContext): string {
  const parts: string[] = [];
  if (ctx.page_title) {
    parts.push(`页面: ${ctx.page_title}`);
  }
  if (ctx.route_path) {
    parts.push(`路径: ${ctx.route_path}`);
  }
  if (ctx.page_description) {
    parts.push(`描述: ${ctx.page_description}`);
  }
  if (ctx.available_apis.length > 0) {
    parts.push(`可用接口: ${ctx.available_apis.join(', ')}`);
  }
  return parts.join('; ');
}
