import type {
  UIAdapterResult,
  UIComponentAdapter,
  UIPageSurfaceInput,
  UIRouteLike,
} from '../types';

export const VUE_ROUTER_ADAPTER_ID = 'vue-router';

export interface CreateVueRouterAdapterOptions {
  getRoute?: () => null | UIRouteLike;
}

function normalizePageKey(raw: string): string {
  const normalized = raw
    .trim()
    .replaceAll(/[?#].*$/g, '')
    .replaceAll(/\/+/g, '/');
  if (!normalized || normalized === '/') {
    return 'root';
  }
  return normalized.replaceAll('/', ':').replaceAll(/^:+|:+$/g, '') || 'root';
}

export function routeToPageSurface(route: UIRouteLike): UIPageSurfaceInput {
  const routeName =
    typeof route.name === 'string' && route.name.length > 0 ? route.name : null;
  const fullPath = route.fullPath || '/';
  const pageKey = normalizePageKey(routeName ?? fullPath);
  const titleFromMeta =
    typeof route.meta?.title === 'string' ? route.meta.title.trim() : '';
  return {
    key: `page:${pageKey}`,
    metadata: {
      source: VUE_ROUTER_ADAPTER_ID,
    },
    pageKey,
    routePath: fullPath,
    title: titleFromMeta || pageKey,
  };
}

export function createVueRouterAdapter(
  options: CreateVueRouterAdapterOptions = {},
  priority = 100,
): UIComponentAdapter {
  return {
    id: VUE_ROUTER_ADAPTER_ID,
    priority,
    collect(context): UIAdapterResult {
      const route = options.getRoute?.() ?? context.route;
      if (!route) {
        return {};
      }
      return {
        page: routeToPageSurface(route),
      };
    },
  };
}
