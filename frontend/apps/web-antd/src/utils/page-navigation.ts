import type { RouteLocationNormalizedLoaded } from 'vue-router';

import type { MenuRecordRaw } from '@vben/types';
import type { MenuNavigationEntry } from './menu-navigation';

import type { PageContext } from '#/api/shared/ai-chat';
import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import { nextTick } from 'vue';

import { useAccessStore } from '@vben/stores';

import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-runtime/page-key-utils';
import { getRuntimeThinPageContext } from '#/components/business/ai-runtime/runtime-bridge';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
import { router } from '#/router';
import {
  canExposePageOperations,
  filterPageOperationsByPolicy,
  normalizePageAIMode,
} from '#/utils/ai-page-capabilities';
import {
  buildCompactNavigationPageData,
  buildMenuNavigationEntries,
} from '#/utils/menu-navigation';
import { getEndpointFromPath } from '#/utils/endpoint';
import {
  buildPageOperation,
  buildRuntimePageOperationNames,
  hasRuntimePageState,
  isPageContextSuggestedTool,
} from '#/utils/runtime-page-operations';

const NAVIGATION_STABILIZE_MS = 80;
const NAVIGATION_READY_TIMEOUT_MS = 10_000;
const NAVIGATION_READY_POLL_MS = 100;
const POST_NAVIGATION_SETTLE_MS = 400;

export function buildPageDataPreview(
  pageContext: null | PageContext,
  extras?: {
    availableOperationNames?: string[];
    navigationContext?: Record<string, unknown>;
  },
): Record<string, unknown> | undefined {
  if (!pageContext) {
    return undefined;
  }

  const preview: Record<string, unknown> = {
    page_key: pageContext.page_key,
    page_title: pageContext.page_title,
    ui_epoch: pageContext.ui_epoch,
    active_surface_id: pageContext.active_surface_id,
    active_form_session_id: pageContext.active_form_session_id,
    has_active_form: !!pageContext.active_form_summary,
    suggested_tool_count:
      pageContext.suggested_tools?.primary?.length ??
      pageContext.suggested_tools?.secondary?.length ??
      0,
    surface_count: Array.isArray(pageContext.surface_stack)
      ? pageContext.surface_stack.length
      : 0,
  };
  const navigationCatalog = pageContext.page_data?.navigation_catalog;
  if (Array.isArray(navigationCatalog) && navigationCatalog.length > 0) {
    preview.navigation_catalog_count = navigationCatalog.length;
  }
  if (
    extras?.availableOperationNames &&
    extras.availableOperationNames.length > 0
  ) {
    preview.available_operation_names = extras.availableOperationNames.slice(
      0,
      8,
    );
  }
  if (extras?.navigationContext) {
    preview.navigation_context = extras.navigationContext;
  }
  return preview;
}

function routePageKey(route: RouteLocationNormalizedLoaded): string {
  return resolveRoutePageKey(route, route.path);
}

function resolveNavigationPageData(
  route: RouteLocationNormalizedLoaded,
  pageKey: string,
): PageContext['page_data'] | undefined {
  let accessMenus: MenuRecordRaw[] = [];
  try {
    const accessStore = useAccessStore();
    accessMenus = Array.isArray(accessStore.accessMenus)
      ? (accessStore.accessMenus as MenuRecordRaw[])
      : [];
  } catch {
    return undefined;
  }
  if (accessMenus.length === 0) {
    return undefined;
  }

  const currentPath =
    route.path ||
    (typeof window === 'undefined' ? '' : window.location.pathname) ||
    '';
  const entries = buildMenuNavigationEntries({
    currentEndpoint: getEndpointFromPath(currentPath),
    menus: accessMenus,
    translate: $t,
  });

  return buildCompactNavigationPageData({
    currentPageKey: pageKey,
    currentPath,
    entries,
  });
}

function resolveDisplayTitle(title: string): string {
  const normalizedTitle = String(title || '').trim();
  if (!normalizedTitle) {
    return '';
  }
  const localizedTitle = String($t(normalizedTitle) || '').trim();
  return localizedTitle || normalizedTitle;
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
    locale: resolveRuntimeLocale(),
    page_key: target.pageKey,
    page_title: target.title,
    suggested_tools: {
      primary: ['ui_get_snapshot', 'ui_list_interactables'],
      reason: 'fallback_navigation_context',
      secondary: ['ui_read_region'],
    },
    surface_stack: [
      {
        kind: 'page',
        surface_id: `page:${target.pageKey}`,
        title: target.title,
      },
    ],
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
    title: resolveDisplayTitle(
      metaTitle || fallback.title || normalizePageKey(route.path),
    ),
  };
}

function serializeAvailableOperations(
  route: RouteLocationNormalizedLoaded,
  pageContext: null | PageContext,
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

  const normalizedToolNames = buildRuntimePageOperationNames(pageContext);

  const operations: PageOperation[] = [];
  const seen = new Set<string>();
  for (const toolName of normalizedToolNames) {
    const operation = buildPageOperation(toolName);
    if (!operation || seen.has(operation.name)) {
      continue;
    }
    seen.add(operation.name);
    operations.push(operation);
  }

  const filtered = filterPageOperationsByPolicy(operations, {
    disabledCapabilities: rawAiMeta.disabledCapabilities as
      | string
      | string[]
      | undefined,
    disabledOperations: rawAiMeta.disabledOperations as
      | string
      | string[]
      | undefined,
    mode,
  });

  if (filtered.length === 0 && normalizePageKey(pageKey) === 'global') {
    return [];
  }

  return filtered.map((operation) => ({
    name: operation.name,
    label: operation.label,
    description: operation.description,
    readonly: operation.readonly,
    ...(operation.params ? { params: operation.params } : {}),
  }));
}

function resolveExactPageContext(pageKey: string): null | PageContext {
  const pageContext = getRuntimeThinPageContext(pageKey);
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
  const basePageContext =
    routePageContext &&
    normalizePageKey(String(routePageContext.page_key ?? '')) ===
      normalizePageKey(resolvedTarget.pageKey)
      ? routePageContext
      : buildFallbackPageContext(resolvedTarget);
  const availableOperations = serializeAvailableOperations(
    currentRoute,
    basePageContext,
    resolvedTarget.pageKey,
  );
  const fallbackSurfaceStack: NonNullable<PageContext['surface_stack']> = [
    {
      kind: 'page',
      surface_id: `page:${resolvedTarget.pageKey}`,
      title: resolvedTarget.title,
    },
  ];
  const surfaceStack =
    Array.isArray(basePageContext.surface_stack) &&
    basePageContext.surface_stack.length > 0
      ? basePageContext.surface_stack
      : fallbackSurfaceStack;
  const navigationPageData =
    basePageContext.page_data ??
    resolveNavigationPageData(currentRoute, resolvedTarget.pageKey);
  const availableOperationNames = availableOperations
    .map((operation) => String(operation.name ?? '').trim())
    .filter(Boolean);
  const suggestedToolNames = availableOperationNames.filter((operationName) =>
    isPageContextSuggestedTool(operationName),
  );
  const suggestedTools =
    basePageContext.suggested_tools ??
    (suggestedToolNames.length > 0
      ? {
          primary: suggestedToolNames.slice(0, 3),
          reason: 'navigation_target_ui_tools_detected',
          secondary: suggestedToolNames.slice(3, 6),
        }
      : {
          primary: ['ui_get_snapshot', 'ui_read_region'],
          reason: 'navigation_target_fallback',
          secondary: ['ui_list_interactables'],
        });
  const navigationContext = navigationPageData?.navigation_context ?? {
    breadcrumb: resolvedTarget.breadcrumb ?? [],
    endpoint: resolvedTarget.endpoint,
    page_key: resolvedTarget.pageKey,
    path: resolvedTarget.path,
  };
  const pageContext: PageContext = {
    ...basePageContext,
    active_surface_id:
      basePageContext.active_surface_id ??
      surfaceStack[surfaceStack.length - 1]?.surface_id,
    locale: basePageContext.locale ?? resolveRuntimeLocale(),
    ...(navigationPageData ? { page_data: navigationPageData } : {}),
    page_key: resolvedTarget.pageKey,
    page_session_id:
      basePageContext.page_session_id ??
      pageSessionIdOverride ??
      getActivePageSessionId() ??
      undefined,
    page_title:
      resolvedTarget.title ||
      basePageContext.page_title ||
      resolvedTarget.pageKey,
    suggested_tools: suggestedTools,
    surface_stack: surfaceStack,
    ui_epoch:
      typeof basePageContext.ui_epoch === 'number'
        ? basePageContext.ui_epoch
        : 0,
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
    page_data_preview: buildPageDataPreview(pageContext, {
      availableOperationNames,
      navigationContext,
    }),
    ui_navigation: {
      available_operation_names: availableOperationNames,
      available_operation_count: availableOperationNames.length,
      navigation_catalog_count:
        navigationPageData?.navigation_catalog?.length ?? 0,
      navigation_context: navigationContext,
    },
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

function hasThinContextSignals(pageContext: null | PageContext): boolean {
  return hasRuntimePageState(pageContext);
}

function hasAvailableUITools(
  operations: Array<Record<string, unknown>>,
): boolean {
  return operations.some((operation) =>
    String(operation.name ?? '')
      .trim()
      .startsWith('ui_'),
  );
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
  return hasThinContextSignals(pageContext);
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
    const targetOperations = serializeAvailableOperations(
      currentRoute,
      targetPageContext,
      target.pageKey,
    );
    const targetUIToolsReady = hasAvailableUITools(targetOperations);
    const destinationReady =
      isTargetRoute(currentRoute, target) &&
      isAuthoritativeTargetContext(targetPageContext, target.pageKey);
    const canAutoContinue = destinationReady && targetUIToolsReady;

    if (destinationReady) {
      await delay(POST_NAVIGATION_SETTLE_MS);
      await stabilizeNavigation();
      return {
        canAutoContinue,
        destinationReady,
        destinationReadyReason: canAutoContinue
          ? 'target_ui_tools_ready'
          : 'target_ui_tools_not_ready',
        pageContext: resolveExactPageContext(target.pageKey),
        pageSessionId: getActivePageSessionId() || currentPageSessionId,
        route: router.currentRoute.value,
      };
    }

    if (
      isTargetRoute(currentRoute, target) &&
      targetPageContext &&
      !isAuthoritativeTargetContext(targetPageContext, target.pageKey)
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
      currentPageContext,
      target.pageKey,
    );
    const canAutoContinue = hasAvailableUITools(currentOperations);
    let destinationReadyReason = 'destination_not_ready';
    if (currentPageContext) {
      destinationReadyReason = canAutoContinue
        ? 'target_ui_tools_ready'
        : 'target_ui_tools_not_ready';
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
