import type { RouteLocationNormalizedLoaded } from 'vue-router';

import type { MenuNavigationEntry } from './menu-navigation';

import type { PageContext } from '#/api/shared/ai-chat';
import type { PageContextSuggestedTool } from '#/api/shared/ai-chat';
import type { PageOperation } from '#/components/business/ai-slide-panel/page-operation-types';

import { nextTick } from 'vue';

import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-slide-panel/page-key-utils';
import { getRuntimeThinPageContext } from '#/components/business/ai-runtime/runtime-bridge';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
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
const BASELINE_UI_TOOLS = [
  'ui_get_snapshot',
  'ui_list_interactables',
  'ui_read_region',
] as const;

const UI_TOOL_META: Record<
  string,
  Omit<PageOperation, 'description' | 'handler' | 'label' | 'name'>
> = {
  ui_click: { readonly: false },
  ui_fill_form: { readonly: false },
  ui_get_form_state: { readonly: true },
  ui_get_snapshot: { readonly: true },
  ui_list_interactables: { readonly: true },
  ui_open_surface: { readonly: false },
  ui_read_region: { readonly: true },
  ui_read_table: { readonly: true },
  ui_set_field: { readonly: false },
  ui_submit_form: { readonly: false },
};

const PAGE_CONTEXT_TOOL_SET = new Set<PageContextSuggestedTool>([
  'ui_click',
  'ui_fill_form',
  'ui_get_form_state',
  'ui_get_snapshot',
  'ui_list_interactables',
  'ui_open_surface',
  'ui_read_region',
  'ui_read_table',
  'ui_set_field',
  'ui_submit_form',
]);

function isPageContextSuggestedTool(
  value: string,
): value is PageContextSuggestedTool {
  return PAGE_CONTEXT_TOOL_SET.has(value as PageContextSuggestedTool);
}

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

function toToolLabel(name: string): string {
  return name
    .replace(/^ui_/, '')
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function toToolDescription(name: string): string {
  const descriptions: Record<string, string> = {
    ui_click: 'Trigger a click on an interactable element.',
    ui_fill_form: 'Fill multiple form fields in the current form session.',
    ui_get_form_state: 'Read the current form session state and field values.',
    ui_get_snapshot: 'Read the current UI snapshot for the active page.',
    ui_list_interactables:
      'List interactable controls available on the current page.',
    ui_open_surface: 'Open a UI surface such as drawer, modal, or dropdown.',
    ui_read_region: 'Read structured text from a specific UI region.',
    ui_read_table: 'Read rows from a table region.',
    ui_set_field: 'Set a single form field value.',
    ui_submit_form: 'Submit the current form session.',
  };
  return descriptions[name] || toToolLabel(name);
}

function buildToolOperation(name: string): null | PageOperation {
  const normalizedName = String(name || '').trim();
  if (!normalizedName.startsWith('ui_')) {
    return null;
  }
  return {
    name: normalizedName,
    label: toToolLabel(normalizedName),
    description: toToolDescription(normalizedName),
    readonly: UI_TOOL_META[normalizedName]?.readonly ?? true,
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

  const candidateToolNames = [
    ...(pageContext?.suggested_tools?.primary ?? []),
    ...(pageContext?.suggested_tools?.secondary ?? []),
  ];
  const normalizedToolNames =
    candidateToolNames.length > 0
      ? candidateToolNames
      : [...BASELINE_UI_TOOLS];

  const operations: PageOperation[] = [];
  const seen = new Set<string>();
  for (const toolName of normalizedToolNames) {
    const operation = buildToolOperation(toolName);
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
  const availableOperationNames = availableOperations
    .map((operation) => String(operation.name ?? '').trim())
    .filter(Boolean);
  const suggestedToolNames = availableOperationNames.filter(
    isPageContextSuggestedTool,
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
  const navigationContext = {
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
  if (!pageContext) {
    return false;
  }
  const pageContextRecord = pageContext as unknown as Record<string, unknown>;
  if (typeof pageContextRecord.ui_epoch === 'number') {
    return true;
  }
  if (Array.isArray(pageContextRecord.surface_stack)) {
    return (pageContextRecord.surface_stack as unknown[]).length > 0;
  }
  if (typeof pageContextRecord.active_surface_id === 'string') {
    return pageContextRecord.active_surface_id.trim().length > 0;
  }
  if (typeof pageContextRecord.active_form_session_id === 'string') {
    return pageContextRecord.active_form_session_id.trim().length > 0;
  }
  const suggestedTools = pageContextRecord.suggested_tools;
  if (suggestedTools && typeof suggestedTools === 'object') {
    return (
      Array.isArray((suggestedTools as Record<string, unknown>).primary) &&
      ((suggestedTools as Record<string, unknown>).primary as unknown[])
        .length > 0
    );
  }
  return false;
}

function hasAvailableUITools(operations: Array<Record<string, unknown>>): boolean {
  return operations.some((operation) =>
    String(operation.name ?? '').trim().startsWith('ui_'),
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
