import type { MenuRecordRaw } from '@vben/types';

import type { FormSession } from './form-session-manager';
import type { RuntimeSnapshotResult } from './runtime-bridge-core';
import type { UISnapshotMode } from './ui-snapshot-generator';

import type {
  ActiveFormSummary,
  PageContext,
  PageContextSuggestedTools,
} from '#/api/shared/ai-chat';

import { useAccessStore } from '@vben/stores';

import { formStateTracker } from '#/composables/use-form-state-tracker';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
import {
  buildCompactNavigationPageData,
  buildMenuNavigationEntries,
} from '#/utils/menu-navigation';
import { getEndpointFromPath } from '#/utils/endpoint';

import {
  byteSize,
  ensureRuntimeInstance,
  getCurrentRouteSecurityPolicy,
  normalizeText,
  queryElementByLocator,
  readFormLikeElementValue,
  resolveCurrentRoute,
  resolvePageTitle,
  resolveRuntimePageKey,
} from './runtime-bridge-core';
import { readValueForAI, resolveAISecurityPolicy } from './security-policy';
import { getRuntimeEpochFloor } from './ui-epoch-floor';
import { UISnapshotGenerator } from './ui-snapshot-generator';

const snapshotGenerator = new UISnapshotGenerator();

function resolveRuntimePathname(): string {
  const routePath = resolveCurrentRoute()?.fullPath;
  const windowPath =
    typeof window === 'undefined' ? '' : window.location.pathname;
  return String(routePath || windowPath || '').split(/[?#]/, 1)[0] || '';
}

function resolveRuntimeNavigationPageData(
  pageKey: string,
): PageContext['page_data'] | undefined {
  const currentPath = resolveRuntimePathname();
  if (!currentPath) {
    return undefined;
  }

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

export function toFormSummary(
  session: FormSession | null,
): ActiveFormSummary | undefined {
  if (!session) {
    return undefined;
  }
  return {
    can_submit: session.can_submit,
    entity_name: session.entity_name,
    form_session_id: session.form_session_id,
    mode: session.mode,
    record_id: session.record_id ?? undefined,
    remaining_required_fields: [...session.remaining_required_fields],
    stage: session.stage,
    submit_policy: session.submit_policy,
  };
}

export function getTrackedFormSessions(): FormSession[] {
  const tracker = formStateTracker as {
    listSessions?: () => FormSession[];
  };
  if (typeof tracker.listSessions === 'function') {
    return tracker.listSessions();
  }

  return formStateTracker
    .getTrackedKeys()
    .map((pageKey) => formStateTracker.getSession(pageKey))
    .filter((session): session is FormSession => session !== null);
}

export function resolveActiveFormSessionForPage(
  pageKey: string,
  options?: {
    activeSurfaceId?: string;
    surfaceIds?: string[];
  },
): FormSession | null {
  const normalizedPageKey = pageKey.trim();
  const tracker = formStateTracker as {
    getActiveSession?: (surfaceId?: string) => FormSession | null;
    getActiveSessionByPageKey?: (pageKey: string) => FormSession | null;
    getActiveSessionBySurfaceId?: (surfaceId: string) => FormSession | null;
    getSession?: (pageKeyOrSessionId: string) => FormSession | null;
    getSessionByPageKey?: (pageKey: string) => FormSession | null;
    getSessionBySessionId?: (sessionId: string) => FormSession | null;
    getSessionBySurfaceId?: (surfaceId: string) => FormSession | null;
    getSessionId?: (pageKey: string) => null | string;
    getSessionIdBySurfaceId?: (surfaceId: string) => null | string;
  };
  const orderedSurfaceIds = [
    String(options?.activeSurfaceId || '').trim(),
    ...((options?.surfaceIds ?? []).map((surfaceId) =>
      String(surfaceId || '').trim(),
    ) ?? []),
  ].filter(
    (surfaceId, index, values) =>
      surfaceId && values.indexOf(surfaceId) === index,
  );

  for (const surfaceId of orderedSurfaceIds) {
    if (typeof tracker.getSessionBySurfaceId === 'function') {
      const sessionBySurfaceId = tracker.getSessionBySurfaceId(surfaceId);
      if (sessionBySurfaceId) {
        return sessionBySurfaceId;
      }
    }

    if (typeof tracker.getActiveSessionBySurfaceId === 'function') {
      const bySurface = tracker.getActiveSessionBySurfaceId(surfaceId);
      if (bySurface) {
        return bySurface;
      }
    }

    if (
      typeof tracker.getSessionIdBySurfaceId === 'function' &&
      (typeof tracker.getSessionBySessionId === 'function' ||
        typeof tracker.getSession === 'function')
    ) {
      const sessionId = tracker.getSessionIdBySurfaceId(surfaceId);
      if (sessionId) {
        const bySessionId =
          tracker.getSessionBySessionId?.(sessionId) ??
          tracker.getSession?.(sessionId) ??
          null;
        if (bySessionId) {
          return bySessionId;
        }
      }
    }

    if (typeof tracker.getActiveSession === 'function') {
      const byActiveSurface = tracker.getActiveSession(surfaceId);
      if (byActiveSurface) {
        return byActiveSurface;
      }
    }
  }

  if (normalizedPageKey) {
    if (typeof tracker.getSessionByPageKey === 'function') {
      const byExplicitPageKey = tracker.getSessionByPageKey(normalizedPageKey);
      if (byExplicitPageKey) {
        return byExplicitPageKey;
      }
    }

    if (typeof tracker.getActiveSessionByPageKey === 'function') {
      const byPageKey = tracker.getActiveSessionByPageKey(normalizedPageKey);
      if (byPageKey) {
        return byPageKey;
      }
    }

    if (
      typeof tracker.getSessionId === 'function' &&
      (typeof tracker.getSessionBySessionId === 'function' ||
        typeof tracker.getSession === 'function')
    ) {
      const sessionId = tracker.getSessionId(normalizedPageKey);
      if (sessionId) {
        const bySessionId =
          tracker.getSessionBySessionId?.(sessionId) ??
          tracker.getSession?.(sessionId) ??
          null;
        if (bySessionId) {
          return bySessionId;
        }
      }
    }
  }

  if (typeof tracker.getActiveSession === 'function') {
    if (normalizedPageKey) {
      const byLegacySurface = tracker.getActiveSession(normalizedPageKey);
      if (byLegacySurface) {
        return byLegacySurface;
      }
    }
    return tracker.getActiveSession() ?? null;
  }

  return null;
}

function computeSuggestedTools(args: {
  activeFormSummary?: ActiveFormSummary;
  hasInteractables: boolean;
  hasTable: boolean;
}): PageContextSuggestedTools {
  if (args.activeFormSummary) {
    return {
      primary: ['ui_get_form_state', 'ui_fill_form', 'ui_submit_form'],
      reason: $t('common.aiRuntime.suggestedTools.activeFormDetected'),
      secondary: ['ui_read_region', 'ui_click'],
    };
  }
  if (args.hasTable) {
    return {
      primary: ['ui_get_snapshot', 'ui_read_table'],
      reason: $t('common.aiRuntime.suggestedTools.tableDetected'),
      secondary: ['ui_click', 'ui_read_region'],
    };
  }
  if (args.hasInteractables) {
    return {
      primary: ['ui_get_snapshot', 'ui_list_interactables'],
      reason: $t('common.aiRuntime.suggestedTools.interactablesDetected'),
      secondary: ['ui_click', 'ui_read_region'],
    };
  }
  return {
    primary: ['ui_get_snapshot', 'ui_read_region'],
    reason: $t('common.aiRuntime.suggestedTools.generalPageContext'),
    secondary: ['ui_list_interactables'],
  };
}

export function buildSnapshot(
  mode: UISnapshotMode = 'compact',
): RuntimeSnapshotResult {
  const runtime = ensureRuntimeInstance();
  const runtimeSnapshot = runtime.readPage(mode);
  const effectiveUiEpoch = Math.max(
    runtimeSnapshot.ui_epoch,
    getRuntimeEpochFloor(),
  );
  const pageKey = resolveRuntimePageKey();
  const routePolicy = getCurrentRouteSecurityPolicy();
  const formSessions = getTrackedFormSessions();
  const activeSurfaceId = runtimeSnapshot.active_surface?.id ?? undefined;
  const activeFormSummary = toFormSummary(
    resolveActiveFormSessionForPage(pageKey, {
      activeSurfaceId,
      surfaceIds: runtimeSnapshot.surface_stack.map((surface) => surface.id),
    }),
  );
  const hasTable = document.querySelector('table') !== null;
  const thinSnapshot = snapshotGenerator.generateSnapshot(
    {
      active_form_session_id: activeFormSummary?.form_session_id,
      active_form_summary: activeFormSummary,
      active_surface_id: activeSurfaceId,
      form_sessions: formSessions.map((session) => ({
        can_submit: session.can_submit,
        entity_name: session.entity_name,
        form_session_id: session.form_session_id,
        mode: session.mode,
        record_id: session.record_id ?? undefined,
        remaining_required_fields: [...session.remaining_required_fields],
        stage: session.stage,
        submit_policy: session.submit_policy,
      })),
      nodes: runtimeSnapshot.ui_graph.nodes.map((node) => {
        const element = queryElementByLocator(node.locator);
        const fieldPolicy = element
          ? resolveAISecurityPolicy({
              element,
              fieldName: element.getAttribute('name') || undefined,
              fieldType:
                element instanceof HTMLInputElement ||
                element instanceof HTMLTextAreaElement ||
                element instanceof HTMLSelectElement
                  ? element.type || undefined
                  : undefined,
              routePolicy,
            })
          : null;
        const content =
          mode === 'full' && element
            ? readValueForAI(
                normalizeText(
                  element instanceof HTMLInputElement ||
                    element instanceof HTMLTextAreaElement ||
                    element instanceof HTMLSelectElement
                    ? readFormLikeElementValue(element)
                    : element.innerText || element.textContent || '',
                  2000,
                ),
                fieldPolicy ?? { canRead: true, readAccess: 'allow' },
              )
            : undefined;
        return {
          children_count: element?.children.length,
          content: typeof content === 'string' ? content : undefined,
          disabled: node.disabled,
          interactable: !node.disabled,
          kind: node.kind,
          label: node.label,
          locator: node.locator,
          node_id: node.id,
          role: undefined,
          surface_id: node.surfaceId,
          text: node.label,
        };
      }),
      suggested_tools: computeSuggestedTools({
        activeFormSummary,
        hasInteractables: runtimeSnapshot.ui_graph.nodes.length > 0,
        hasTable,
      }),
      surface_stack: runtimeSnapshot.surface_stack.map((surface) => ({
        kind: surface.kind,
        surface_id: surface.id,
        title: surface.title,
      })),
      ui_epoch: effectiveUiEpoch,
    },
    mode,
  );
  const navigationPageData = resolveRuntimeNavigationPageData(pageKey);

  const pageContext: PageContext = {
    ...snapshotGenerator.buildThinPageContext({
      locale: resolveRuntimeLocale(),
      pageKey,
      pageSessionId: getActivePageSessionId() || undefined,
      pageTitle: resolvePageTitle(pageKey),
      snapshot: thinSnapshot,
    }),
    ...(navigationPageData ? { page_data: navigationPageData } : {}),
  };
  return {
    pageContext,
    sizeBytes: byteSize(pageContext),
    snapshot: thinSnapshot,
  };
}

export function getRuntimeThinPageContext(
  explicitPageKey?: string,
): null | PageContext {
  const built = buildSnapshot('compact');
  if (!built.pageContext.page_key) {
    return null;
  }
  if (explicitPageKey?.trim()) {
    return {
      ...built.pageContext,
      page_key: resolveRuntimePageKey(explicitPageKey),
    };
  }
  return built.pageContext;
}

export function getRuntimePageContextDiagnostics(): Record<string, unknown> {
  const built = buildSnapshot('compact');
  return {
    interactables_count: built.snapshot.interactables_count,
    size_bytes: built.sizeBytes,
    source: 'ui_runtime',
    ui_epoch: built.snapshot.ui_epoch,
  };
}

export function getRuntimeSnapshot(mode: UISnapshotMode = 'compact') {
  return buildSnapshot(mode).snapshot;
}

export function getRuntimePageSnapshot(mode: UISnapshotMode = 'compact') {
  return buildSnapshot(mode);
}

export function readRuntimeSurface(
  surfaceId?: string,
): Record<string, unknown> {
  const runtime = ensureRuntimeInstance();
  const surfaceRead = runtime.readSurface(surfaceId, 'full');
  return {
    active_surface_id: surfaceRead.active_surface?.id,
    mode: surfaceRead.mode,
    nodes: surfaceRead.nodes,
    surface: surfaceRead.surface
      ? {
          kind: surfaceRead.surface.kind,
          surface_id: surfaceRead.surface.id,
          title: surfaceRead.surface.title,
        }
      : null,
    surface_stack: surfaceRead.surface_stack.map((surface) => ({
      kind: surface.kind,
      surface_id: surface.id,
      title: surface.title,
    })),
    ui_epoch: surfaceRead.ui_epoch,
  };
}
