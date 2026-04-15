import type {
  ActiveFormSummary,
  PageContext,
  PageContextSuggestedTools,
} from '#/api/shared/ai-chat';

import type { FormSession } from './form-session-manager';
import type { UISnapshotMode } from './ui-snapshot-generator';

import { formStateTracker } from '#/composables/use-form-state-tracker';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';

import {
  byteSize,
  ensureRuntimeInstance,
  normalizeText,
  queryElementByLocator,
  readFormLikeElementValue,
  resolveCurrentRoute,
  resolvePageTitle,
  resolveRuntimePageKey,
  type RuntimeSnapshotResult,
} from './runtime-bridge-core';
import { readValueForAI, resolveAISecurityPolicy } from './security-policy';
import { UISnapshotGenerator } from './ui-snapshot-generator';

const snapshotGenerator = new UISnapshotGenerator();

export function toFormSummary(
  session: null | FormSession,
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
    .filter((session): session is FormSession => Boolean(session));
}

export function resolveActiveFormSessionForPage(
  pageKey: string,
): null | FormSession {
  const normalizedPageKey = pageKey.trim();
  const tracker = formStateTracker as {
    getActiveSession?: (surfaceId?: string) => FormSession | null;
    getActiveSessionByPageKey?: (pageKey: string) => FormSession | null;
    getSession?: (pageKeyOrSessionId: string) => FormSession | null;
    getSessionId?: (pageKey: string) => null | string;
  };

  if (normalizedPageKey) {
    if (typeof tracker.getActiveSessionByPageKey === 'function') {
      const byPageKey = tracker.getActiveSessionByPageKey(normalizedPageKey);
      if (byPageKey) {
        return byPageKey;
      }
    }

    if (
      typeof tracker.getSessionId === 'function' &&
      typeof tracker.getSession === 'function'
    ) {
      const sessionId = tracker.getSessionId(normalizedPageKey);
      if (sessionId) {
        const bySessionId = tracker.getSession(sessionId);
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
  const runtimeSnapshot = runtime.rebuildGraph({
    mode,
    route: resolveCurrentRoute(),
  });
  const pageKey = resolveRuntimePageKey();
  const formSessions = getTrackedFormSessions();
  const activeFormSummary = toFormSummary(
    resolveActiveFormSessionForPage(pageKey),
  );
  const hasTable = document.querySelector('table') !== null;
  const thinSnapshot = snapshotGenerator.generateSnapshot(
    {
      active_form_session_id: activeFormSummary?.form_session_id,
      active_form_summary: activeFormSummary,
      active_surface_id: runtimeSnapshot.active_surface?.id ?? undefined,
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
      ui_epoch: runtimeSnapshot.ui_epoch,
    },
    mode,
  );

  const pageContext = snapshotGenerator.buildThinPageContext({
    locale: resolveRuntimeLocale(),
    pageKey,
    pageSessionId: getActivePageSessionId() || undefined,
    pageTitle: resolvePageTitle(pageKey),
    snapshot: thinSnapshot,
  });
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
