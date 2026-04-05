import type { RouteLocationNormalizedLoaded } from 'vue-router';

import type { MenuNavigationEntry } from './menu-navigation';

import type { PageContext } from '#/api/shared/ai-chat';

import { nextTick } from 'vue';

import { resolvePageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-slide-panel/page-key-utils';
import {
  getRegisteredOperationKeys,
  listPageOperations,
} from '#/components/business/ai-slide-panel/page-operation-registry';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { router } from '#/router';
import {
  canExposePageOperations,
  filterPageOperationsByPolicy,
  normalizePageAIMode,
} from '#/utils/ai-page-capabilities';

const NAVIGATION_STABILIZE_MS = 80;
const NAVIGATION_READY_TIMEOUT_MS = 10_000;
const NAVIGATION_READY_POLL_MS = 100;
const POST_NAVIGATION_SETTLE_MS = 400;
const FALLBACK_PAGE_CONTEXT_SOURCES = new Set([
  'dom_snapshot',
  'minimal_fallback',
]);
const DEFAULT_OPERATION_NAMES = new Set([
  'capture_screenshot',
  'list_available_menus',
  'navigate_menu',
  'read_current_sections',
  'read_current_view',
]);

export function buildPageDataPreview(
  pageData: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!pageData) return undefined;

  const {
    available_operations: _availableOperations,
    available_menus: _availableMenus,
    form_fields: _formFields,
    visual_state: _visualState,
    ...rest
  } = pageData;

  const preview: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(rest)) {
    if (value === undefined || value === null || value === '') continue;
    if (typeof value === 'string') {
      preview[key] = value.length > 240 ? `${value.slice(0, 240)}...` : value;
      continue;
    }
    preview[key] = value;
  }

  return Object.keys(preview).length > 0 ? preview : undefined;
}

function routePageKey(route: RouteLocationNormalizedLoaded): string {
  return resolveRoutePageKey(route, route.path);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function stabilizeNavigation(): Promise<void> {
  await nextTick();
  await delay(NAVIGATION_STABILIZE_MS);
  await nextTick();
}

function isRoutePermissionDenied(
  route: RouteLocationNormalizedLoaded,
): boolean {
  const path = route.path.toLowerCase();
  const name = String(route.name ?? '').toLowerCase();
  return (
    path.includes('/403') ||
    path.includes('/forbidden') ||
    name.includes('forbidden')
  );
}

function buildFallbackPageContext(target: NavigationTarget): PageContext {
  return {
    page_key: target.pageKey,
    page_title: target.title,
    page_data: {
      source: 'minimal_fallback',
    },
  };
}

export interface NavigationTarget {
  breadcrumb?: string[];
  endpoint?: string;
  pageKey: string;
  path: string;
  title: string;
}

interface NavigationReadinessResult {
  canAutoContinue: boolean;
  destinationReady: boolean;
  destinationReadyReason: string;
  pageContext: null | PageContext;
  pageSessionId: string;
  route: RouteLocationNormalizedLoaded;
}

function buildNavigationTargetFromRoute(
  route: RouteLocationNormalizedLoaded,
  fallback: NavigationTarget,
): NavigationTarget {
  const metaTitle =
    typeof route.meta?.title === 'string' ? route.meta.title : fallback.title;

  return {
    breadcrumb: fallback.breadcrumb ?? [],
    endpoint: fallback.endpoint,
    pageKey: normalizePageKey(fallback.pageKey || routePageKey(route)),
    path: route.path,
    title: metaTitle || fallback.title || normalizePageKey(route.path),
  };
}

function serializeAvailableOperations(
  route: RouteLocationNormalizedLoaded,
  pageKey: string,
) {
  const rawAiMeta =
    route.meta && typeof route.meta === 'object'
      ? ((route.meta as { ai?: Record<string, unknown> }).ai ?? {})
      : {};
  const mode = normalizePageAIMode(
    rawAiMeta.mode as Parameters<typeof normalizePageAIMode>[0],
    'operate',
  );
  if (!canExposePageOperations(mode)) {
    return [];
  }
  return filterPageOperationsByPolicy(listPageOperations(pageKey), {
    disabledCapabilities: rawAiMeta.disabledCapabilities as
      | string
      | string[]
      | undefined,
    disabledOperations: rawAiMeta.disabledOperations as
      | string
      | string[]
      | undefined,
    mode,
  }).map((operation) => ({
    name: operation.name,
    label: operation.label,
    description: operation.description,
    readonly: operation.readonly,
    ...(operation.params ? { params: operation.params } : {}),
  }));
}

function resolveExactPageContext(pageKey: string): null | PageContext {
  const pageContext = resolvePageContext(pageKey);
  if (
    !pageContext ||
    normalizePageKey(String(pageContext.page_key ?? '')) !==
      normalizePageKey(pageKey)
  ) {
    return null;
  }
  return pageContext;
}

function buildNavigationResultPayload(
  target: NavigationTarget,
  currentRoute: RouteLocationNormalizedLoaded,
  pageContextOverride?: null | PageContext,
  pageSessionIdOverride?: null | string,
  readiness?: Pick<
    NavigationReadinessResult,
    'canAutoContinue' | 'destinationReady' | 'destinationReadyReason'
  >,
): Record<string, unknown> {
  const resolvedTarget = buildNavigationTargetFromRoute(currentRoute, target);
  const routePageContext =
    pageContextOverride ?? buildFallbackPageContext(resolvedTarget);
  const availableOperations = serializeAvailableOperations(
    currentRoute,
    resolvedTarget.pageKey,
  );
  const basePageContext =
    routePageContext &&
    normalizePageKey(String(routePageContext.page_key ?? '')) ===
      normalizePageKey(resolvedTarget.pageKey)
      ? routePageContext
      : buildFallbackPageContext(resolvedTarget);
  const pageContext: PageContext = {
    ...basePageContext,
    page_key: resolvedTarget.pageKey,
    page_title:
      resolvedTarget.title ||
      basePageContext.page_title ||
      resolvedTarget.pageKey,
    page_data: {
      ...basePageContext.page_data,
      navigation_context: {
        breadcrumb: resolvedTarget.breadcrumb ?? [],
        endpoint: resolvedTarget.endpoint,
        page_key: resolvedTarget.pageKey,
        path: resolvedTarget.path,
      },
      ...(availableOperations.length > 0
        ? { available_operations: availableOperations }
        : {}),
    },
  };

  return {
    navigation_target: {
      breadcrumb: resolvedTarget.breadcrumb ?? [],
      endpoint: resolvedTarget.endpoint,
      page_key: resolvedTarget.pageKey,
      path: resolvedTarget.path,
      title: resolvedTarget.title,
    },
    page_context: pageContext,
    page_data_preview: buildPageDataPreview(
      (pageContext.page_data as Record<string, unknown> | undefined) ??
        undefined,
    ),
    page_session_id:
      pageSessionIdOverride ?? (getActivePageSessionId() || null),
    route_path: currentRoute.path,
    navigation_succeeded: true,
    destination_ready: readiness?.destinationReady ?? false,
    destination_ready_reason:
      readiness?.destinationReadyReason ?? 'destination_not_ready',
    can_auto_continue: readiness?.canAutoContinue ?? false,
  };
}

function getPageContextSource(pageContext: null | PageContext): string {
  const source = pageContext?.page_data?.source;
  return typeof source === 'string' ? source : '';
}

function hasPageSpecificOperations(
  operations: Array<Record<string, unknown>>,
): boolean {
  return operations.some((operation) => {
    const name = String(operation.name ?? '').trim();
    return name.length > 0 && !DEFAULT_OPERATION_NAMES.has(name);
  });
}

function isAuthoritativeTargetContext(
  pageContext: null | PageContext,
  targetPageKey: string,
): boolean {
  if (
    !pageContext ||
    normalizePageKey(String(pageContext.page_key ?? '')) !==
      normalizePageKey(targetPageKey)
  ) {
    return false;
  }
  return !FALLBACK_PAGE_CONTEXT_SOURCES.has(getPageContextSource(pageContext));
}

function isTargetRoute(
  route: RouteLocationNormalizedLoaded,
  target: NavigationTarget,
): boolean {
  return (
    route.path === target.path ||
    normalizePageKey(routePageKey(route)) === normalizePageKey(target.pageKey)
  );
}

async function waitForNavigationReadiness(
  target: NavigationTarget,
): Promise<NavigationReadinessResult> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < NAVIGATION_READY_TIMEOUT_MS) {
    await stabilizeNavigation();
    const currentRoute = router.currentRoute.value;
    const currentPageSessionId = getActivePageSessionId() || '';
    const targetPageContext = resolveExactPageContext(target.pageKey);
    const registeredOperationKeys = getRegisteredOperationKeys();
    const hasRegisteredPageOperations = registeredOperationKeys.includes(
      normalizePageKey(target.pageKey),
    );
    const targetOperations = serializeAvailableOperations(
      currentRoute,
      target.pageKey,
    );
    const targetSpecificOperationsReady =
      hasPageSpecificOperations(targetOperations);
    const destinationReady =
      isTargetRoute(currentRoute, target) &&
      isAuthoritativeTargetContext(targetPageContext, target.pageKey);
    const canAutoContinue =
      destinationReady &&
      hasRegisteredPageOperations &&
      targetSpecificOperationsReady;

    if (destinationReady) {
      await delay(POST_NAVIGATION_SETTLE_MS);
      await stabilizeNavigation();
      return {
        canAutoContinue,
        destinationReady,
        destinationReadyReason: canAutoContinue
          ? 'target_operations_ready'
          : 'target_operations_not_ready',
        pageContext: resolveExactPageContext(target.pageKey),
        pageSessionId: getActivePageSessionId() || currentPageSessionId,
        route: router.currentRoute.value,
      };
    }

    if (
      isTargetRoute(currentRoute, target) &&
      targetPageContext &&
      FALLBACK_PAGE_CONTEXT_SOURCES.has(getPageContextSource(targetPageContext))
    ) {
      return {
        canAutoContinue: false,
        destinationReady: false,
        destinationReadyReason: 'destination_not_ready',
        pageContext: targetPageContext,
        pageSessionId: currentPageSessionId,
        route: currentRoute,
      };
    }

    await delay(NAVIGATION_READY_POLL_MS);
  }

  return {
    canAutoContinue: false,
    destinationReady: false,
    destinationReadyReason: 'destination_not_ready',
    pageContext: resolveExactPageContext(target.pageKey),
    pageSessionId: getActivePageSessionId() || '',
    route: router.currentRoute.value,
  };
}

export async function navigateToPathWithContext(
  target: NavigationTarget,
): Promise<{
  data?: Record<string, unknown>;
  error_type?: string;
  message: string;
  success: boolean;
}> {
  const currentRoute = router.currentRoute.value;
  const currentPageKey = routePageKey(currentRoute);

  if (
    normalizePageKey(currentPageKey) === normalizePageKey(target.pageKey) ||
    currentRoute.path === target.path
  ) {
    const currentPageContext = resolveExactPageContext(target.pageKey);
    const currentOperations = serializeAvailableOperations(
      currentRoute,
      target.pageKey,
    );
    const canAutoContinue = hasPageSpecificOperations(currentOperations);
    let destinationReadyReason = 'destination_not_ready';
    if (currentPageContext) {
      destinationReadyReason = canAutoContinue
        ? 'target_operations_ready'
        : 'target_operations_not_ready';
    }

    return {
      success: true,
      message: `Navigated to ${target.path}`,
      data: {
        already_on_page: true,
        ...buildNavigationResultPayload(
          target,
          currentRoute,
          currentPageContext,
          null,
          {
            canAutoContinue,
            destinationReady: !!currentPageContext,
            destinationReadyReason,
          },
        ),
      },
    };
  }

  await router.push(target.path);
  await stabilizeNavigation();
  const immediateRoute = router.currentRoute.value;
  if (
    !isTargetRoute(immediateRoute, target) &&
    isRoutePermissionDenied(immediateRoute)
  ) {
    return {
      success: false,
      message: `Navigation to ${target.path} was blocked`,
      error_type: 'permission_denied',
    };
  }

  const readiness = await waitForNavigationReadiness(target);
  const sameTarget = isTargetRoute(readiness.route, target);

  if (!sameTarget) {
    return {
      success: false,
      message: `Navigation to ${target.path} was blocked`,
      error_type: isRoutePermissionDenied(readiness.route)
        ? 'permission_denied'
        : 'navigation_blocked',
    };
  }

  return {
    success: true,
    message: `Navigated to ${target.path}`,
    data: buildNavigationResultPayload(
      target,
      readiness.route,
      readiness.pageContext,
      readiness.pageSessionId || null,
      readiness,
    ),
  };
}

export async function navigateToMenuEntry(entry: MenuNavigationEntry) {
  return navigateToPathWithContext({
    breadcrumb: entry.breadcrumb,
    endpoint: entry.endpoint,
    pageKey: entry.pageKey,
    path: entry.path,
    title: entry.title,
  });
}
