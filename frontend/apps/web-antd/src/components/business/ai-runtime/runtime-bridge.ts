import type {
  ActiveFormSummary,
  PageContext,
  PageContextSuggestedTools,
} from '#/api/shared/ai-chat';

import type { FormFieldDescriptor, FormSession } from './form-session-manager';
import type { UIRouteLike } from './types';
import type { UISnapshot, UISnapshotMode } from './ui-snapshot-generator';

import { nextTick } from 'vue';

import { resolveRoutePageKey } from '#/components/business/ai-runtime/page-key-utils';
import { formStateTracker } from '#/composables/use-form-state-tracker';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
import { getActivePageSessionId } from '#/composables/use-page-session';

import { tAiRuntime } from './i18n';
import { readValueForAI, resolveAISecurityPolicy } from './security-policy';
import { createUIRuntime, type UIRuntime } from './ui-runtime';
import { UISnapshotGenerator } from './ui-snapshot-generator';

interface EnsureGlobalUIRuntimeOptions {
  getRoute?: () => null | UIRouteLike;
}

interface RuntimeSnapshotResult {
  pageContext: PageContext;
  sizeBytes: number;
  snapshot: UISnapshot;
}

interface RuntimeFormActionResult {
  data?: Record<string, unknown>;
  error?: string;
  error_type?: string;
  message: string;
  success: boolean;
}

let globalRuntime: null | UIRuntime = null;
let globalRouteGetter: (() => null | UIRouteLike) | undefined;

const snapshotGenerator = new UISnapshotGenerator();

function byteSize(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value)).length;
}

function normalizeText(value: unknown, maxLength = 240): string {
  return String(value ?? '')
    .replaceAll(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
}

function escapeSelectorValue(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replaceAll('"', '\\"');
}

function resolveCurrentRoute(): null | UIRouteLike {
  return globalRouteGetter?.() ?? null;
}

function resolveRuntimePageKey(explicitPageKey?: string): string {
  if (explicitPageKey?.trim()) {
    return resolveRoutePageKey(undefined, explicitPageKey.trim());
  }
  const route = resolveCurrentRoute();
  return resolveRoutePageKey(
    route
      ? {
          meta: route.meta,
          path: route.fullPath,
        }
      : undefined,
    typeof window === 'undefined' ? '' : window.location.pathname,
  );
}

function resolvePageTitle(pageKey: string): string {
  const routeTitle = resolveCurrentRoute()?.meta?.title;
  if (typeof routeTitle === 'string' && routeTitle.trim()) {
    const localizedTitle = String($t(routeTitle.trim()) || '').trim();
    return normalizeText(localizedTitle || routeTitle.trim(), 200) || pageKey;
  }
  return normalizeText(document.title || pageKey, 200) || pageKey;
}

function ensureRuntimeInstance(): UIRuntime {
  if (!globalRuntime) {
    globalRuntime = createUIRuntime({
      getRoute: resolveCurrentRoute,
    });
    globalRuntime.initialize();
  }
  return globalRuntime;
}

function ensureElementVisible(element: null | HTMLElement): element is HTMLElement {
  if (!element) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (element.hidden || style.display === 'none' || style.visibility === 'hidden') {
    return false;
  }
  return element.getClientRects().length > 0 || style.opacity !== '0';
}

function queryElementsByText(text: string): HTMLElement[] {
  const normalized = normalizeText(text).toLocaleLowerCase();
  if (!normalized) {
    return [];
  }
  return Array.from(document.querySelectorAll<HTMLElement>('body *')).filter(
    (element) => {
      if (!ensureElementVisible(element)) {
        return false;
      }
      return normalizeText(element.innerText || element.textContent || '')
        .toLocaleLowerCase()
        .includes(normalized);
    },
  );
}

function queryElementByLocator(locator: string): null | HTMLElement {
  const normalized = normalizeText(locator);
  if (!normalized) {
    return null;
  }

  const prefixed = [
    ['ai-id:', `[data-ai-id="${escapeSelectorValue(normalized.slice(6))}"]`],
    ['testid:', `[data-testid="${escapeSelectorValue(normalized.slice(7))}"]`],
    ['id:', `#${escapeSelectorValue(normalized.slice(3))}`],
    ['name:', `[name="${escapeSelectorValue(normalized.slice(5))}"]`],
    ['href:', `a[href="${escapeSelectorValue(normalized.slice(5))}"]`],
  ] as const;
  for (const [prefix, selector] of prefixed) {
    if (normalized.startsWith(prefix)) {
      try {
        const match = document.querySelector<HTMLElement>(selector);
        return ensureElementVisible(match) ? match : null;
      } catch {
        return null;
      }
    }
  }

  if (normalized.startsWith('text:')) {
    return queryElementsByText(normalized.slice(5))[0] ?? null;
  }

  const cssSelector = normalized.startsWith('css:')
    ? normalized.slice(4)
    : normalized;
  try {
    const match = document.querySelector<HTMLElement>(cssSelector);
    return ensureElementVisible(match) ? match : null;
  } catch {
    return null;
  }
}

function toFormSummary(session: null | FormSession): ActiveFormSummary | undefined {
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

function getTrackedFormSessions(): FormSession[] {
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

function resolveActiveFormSessionForPage(pageKey: string): null | FormSession {
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

function readFormLikeElementValue(
  element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
): string {
  if (element instanceof HTMLSelectElement) {
    return element.value || '';
  }
  return element.value || element.placeholder || '';
}

function buildSnapshot(mode: UISnapshotMode = 'compact'): RuntimeSnapshotResult {
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

function findSurfaceIdForElement(
  element: HTMLElement,
  snapshot: UISnapshot,
): string | undefined {
  const selectors: Array<[string, UISnapshot['surface_stack'][number]['kind']]> = [
    ['.ant-popover', 'popover'],
    ['.ant-dropdown, .ant-select-dropdown', 'dropdown'],
    ['.ant-modal, .ant-modal-wrap, [role="dialog"]', 'modal'],
    ['.ant-drawer, .ant-drawer-content-wrapper, .ant-drawer-content', 'drawer'],
  ];
  for (const [selector, kind] of selectors) {
    if (!element.closest(selector)) {
      continue;
    }
    for (let index = snapshot.surface_stack.length - 1; index >= 0; index -= 1) {
      const surface = snapshot.surface_stack[index];
      if (surface?.kind === kind) {
        return surface.surface_id;
      }
    }
  }
  return snapshot.active_surface_id || snapshot.surface_stack[0]?.surface_id;
}

function readElementText(element: HTMLElement): string | undefined {
  const decision = resolveAISecurityPolicy({
    element,
    fieldName: element.getAttribute('name') || undefined,
    fieldType:
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLSelectElement
        ? element.type || undefined
        : undefined,
  });
  if (
    element instanceof HTMLInputElement ||
    element instanceof HTMLTextAreaElement ||
    element instanceof HTMLSelectElement
  ) {
    const value = readValueForAI(readFormLikeElementValue(element), decision);
    return typeof value === 'string' ? normalizeText(value, 4000) : undefined;
  }
  const value = readValueForAI(
    element.innerText || element.textContent || '',
    decision,
  );
  return typeof value === 'string' ? normalizeText(value, 4000) : undefined;
}

function readRegionItems(element: HTMLElement): Array<{ label?: string; value?: string }> {
  const items: Array<{ label?: string; value?: string }> = [];
  const labels = element.querySelectorAll<HTMLElement>('label,[data-label],dt,th');
  labels.forEach((labelElement) => {
    if (items.length >= 50) {
      return;
    }
    const label = normalizeText(
      labelElement.getAttribute('data-label') ||
        labelElement.innerText ||
        labelElement.textContent ||
        '',
      200,
    );
    if (!label) {
      return;
    }
    const sibling =
      labelElement.nextElementSibling instanceof HTMLElement
        ? labelElement.nextElementSibling
        : null;
    const value = sibling ? readElementText(sibling) : undefined;
    items.push({
      ...(label ? { label } : {}),
      ...(value ? { value } : {}),
    });
  });
  return items;
}

function filterTableCells(cells: HTMLElement[]): string[] {
  return cells
    .map((cell) => normalizeText(cell.innerText || cell.textContent || '', 240))
    .filter(Boolean);
}

function resolveFormSession(formSessionId?: string): null | FormSession {
  if (formSessionId?.trim()) {
    return formStateTracker.getSession(formSessionId.trim());
  }
  return resolveActiveFormSessionForPage(resolveRuntimePageKey());
}

function buildFormStateData(session: FormSession): Record<string, unknown> {
  return {
    can_submit: session.can_submit,
    entity_name: session.entity_name,
    fields: session.fields.map((field) => serializeFormField(field)),
    form_session_id: session.form_session_id,
    mode: session.mode,
    record_id: session.record_id ?? undefined,
    remaining_required_fields: [...session.remaining_required_fields],
    stage: session.stage,
    submit_policy: session.submit_policy,
  };
}

function serializeFormField(field: FormFieldDescriptor): Record<string, unknown> {
  const element = queryElementByLocator(`name:${field.name}`) ?? queryElementByLocator(`id:${field.name}`);
  const decision = resolveAISecurityPolicy({
    element,
    fieldName: field.name,
    fieldType: field.type,
  });
  const safeValue = readValueForAI(field.value, decision);
  return {
    disabled: !!field.disabled,
    label: field.label,
    name: field.name,
    readonly: !!field.readonly,
    required: !!field.required,
    type: field.type,
    ...(safeValue !== undefined ? { value: safeValue } : {}),
  };
}

async function applyFormValues(
  updates: Record<string, unknown>,
  formSessionId?: string,
): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }

  const formApi = formStateTracker.getFormApi(session.form_session_id);
  if (!formApi) {
    return {
      error: tAiRuntime('formApiUnavailable'),
      error_type: 'form_api_unavailable',
      message: tAiRuntime('currentFormNotReady'),
      success: false,
    };
  }

  const fieldsByName = new Map(session.fields.map((field) => [field.name, field]));
  const writableUpdates: Record<string, unknown> = {};
  const fieldsFailed: Array<{ field: string; error: string }> = [];

  for (const [fieldName, value] of Object.entries(updates)) {
    const descriptor = fieldsByName.get(fieldName);
    if (!descriptor) {
      fieldsFailed.push({ field: fieldName, error: 'field_not_found' });
      continue;
    }
    if (descriptor.disabled || descriptor.readonly) {
      fieldsFailed.push({ field: fieldName, error: 'field_not_writable' });
      continue;
    }
    writableUpdates[fieldName] = value;
  }

  if (Object.keys(writableUpdates).length === 0) {
    return {
      data: {
        fields_failed: fieldsFailed,
        form_session: buildFormStateData(session),
      },
      error: tAiRuntime('noWritableFieldsProvided'),
      error_type: 'no_writable_fields',
      message: tAiRuntime('noWritableFieldsUpdated'),
      success: false,
    };
  }

  formApi.setValues(writableUpdates);
  await nextTick();
  let currentValues = writableUpdates;
  try {
    currentValues = await formApi.getValues();
  } catch {
    // Keep applied values when the form is still stabilizing.
  }
  const updatedSession =
    formStateTracker.setSessionFieldValues(session.form_session_id, currentValues) ??
    formStateTracker.getSession(session.form_session_id) ??
    session;

  return {
    data: {
      fields_failed: fieldsFailed,
      fields_updated: Object.keys(writableUpdates),
      form_session: buildFormStateData(updatedSession),
    },
    message:
      fieldsFailed.length > 0
        ? tAiRuntime('formFieldsUpdatedPartial')
        : tAiRuntime('formFieldsUpdated'),
    success: true,
  };
}

export function ensureGlobalUIRuntime(
  options: EnsureGlobalUIRuntimeOptions = {},
): UIRuntime {
  if (options.getRoute) {
    globalRouteGetter = options.getRoute;
  }
  return ensureRuntimeInstance();
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

export function getRuntimeSnapshot(mode: UISnapshotMode = 'compact'): UISnapshot {
  return buildSnapshot(mode).snapshot;
}

export function readRuntimeRegion(locator: string): Record<string, unknown> {
  const element = queryElementByLocator(locator);
  if (!element) {
    throw new Error(tAiRuntime('regionLocatorNotFound', { locator }));
  }
  const snapshot = buildSnapshot('compact').snapshot;
  const title =
    normalizeText(
      element.getAttribute('aria-label') ||
        element.getAttribute('title') ||
        element.querySelector('h1,h2,h3,h4,.ant-card-head-title')?.textContent ||
        '',
      200,
    ) || undefined;
  return {
    items: readRegionItems(element),
    region_locator: locator,
    surface_id: findSurfaceIdForElement(element, snapshot),
    text: readElementText(element),
    title,
    truncated: false,
  };
}

export function readRuntimeTable(args: {
  locator: string;
  page?: number;
  pageSize?: number;
}): Record<string, unknown> {
  const element = queryElementByLocator(args.locator);
  const table =
    element?.matches('table')
      ? element
      : element?.querySelector('table');
  if (!(table instanceof HTMLTableElement)) {
    throw new Error(
      tAiRuntime('tableLocatorNotFound', { locator: args.locator }),
    );
  }
  const snapshot = buildSnapshot('compact').snapshot;
  const page = Math.max(args.page ?? 1, 1);
  const pageSize = Math.max(Math.min(args.pageSize ?? 20, 100), 1);
  const headerCells = filterTableCells(
    Array.from(table.querySelectorAll<HTMLElement>('thead th')),
  );
  const headers =
    headerCells.length > 0
      ? headerCells
      : filterTableCells(
          Array.from(table.querySelectorAll<HTMLElement>('tbody tr:first-child td')),
        );
  const allRows = Array.from(table.querySelectorAll<HTMLTableRowElement>('tbody tr'));
  const startIndex = (page - 1) * pageSize;
  const rows = allRows.slice(startIndex, startIndex + pageSize).map((row) => {
    const cells = Array.from(row.querySelectorAll<HTMLElement>('td'));
    const values = filterTableCells(cells);
    const normalizedRow: Record<string, unknown> = {};
    values.forEach((value, index) => {
      normalizedRow[headers[index] || `column_${index + 1}`] = value;
    });
    return normalizedRow;
  });
  return {
    columns: headers,
    has_more: startIndex + rows.length < allRows.length,
    page,
    page_size: pageSize,
    rows,
    surface_id: snapshot.active_surface_id,
    table_locator: args.locator,
    total_rows: allRows.length,
    truncated: false,
  };
}

export function listRuntimeInteractables(surfaceId?: string): Record<string, unknown> {
  const snapshot = buildSnapshot('compact').snapshot;
  const items = snapshot.nodes
    .filter((node) => node.interactable || ['button', 'input', 'link', 'select', 'tab'].includes(node.kind))
    .filter((node) => !surfaceId || node.surface_id === surfaceId)
    .map((node) => {
      const element = queryElementByLocator(node.locator || '');
      const decision = resolveAISecurityPolicy({
        actionKind: node.kind === 'button' ? 'click' : node.kind,
        element,
      });
      return {
        enabled: !node.kind || decision.canAct,
        kind: node.kind,
        label: node.summary,
        locator: node.locator,
        requires_confirmation: decision.requireConfirm,
        surface_id: node.surface_id,
      };
    })
    .slice(0, 200);
  return {
    count: items.length,
    items,
    surface_id: surfaceId,
    truncated: snapshot.nodes.length > items.length,
  };
}

export async function getRuntimeFormState(
  formSessionId?: string,
): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }
  return {
    data: buildFormStateData(session),
    message: tAiRuntime('formStateLoaded'),
    success: true,
  };
}

export async function setRuntimeFormField(args: {
  fieldName: string;
  formSessionId?: string;
  value: unknown;
}): Promise<RuntimeFormActionResult> {
  return applyFormValues(
    {
      [args.fieldName]: args.value,
    },
    args.formSessionId,
  );
}

export async function fillRuntimeForm(args: {
  fields: Record<string, unknown>;
  formSessionId?: string;
}): Promise<RuntimeFormActionResult> {
  return applyFormValues(args.fields, args.formSessionId);
}

export async function submitRuntimeForm(args: {
  confirm?: boolean;
  formSessionId?: string;
}): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(args.formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }
  const formApi = formStateTracker.getFormApi(session.form_session_id);
  if (!formApi?.submitForm) {
    return {
      error: tAiRuntime('formSubmitUnavailable'),
      error_type: 'form_submit_unavailable',
      message: tAiRuntime('currentFormCannotSubmit'),
      success: false,
    };
  }
  if (session.submit_policy === 'confirm' && !args.confirm) {
    return {
      data: {
        form_session: buildFormStateData(session),
      },
      error: tAiRuntime('formSubmissionRequiresConfirmation'),
      error_type: 'confirmation_required',
      message: tAiRuntime('formSubmissionRequiresConfirmation'),
      success: false,
    };
  }

  await formApi.submitForm();
  await nextTick();
  let currentValues: Record<string, unknown> = {};
  try {
    currentValues = await formApi.getValues();
  } catch {
    // Ignore when the form closes immediately after submit.
  }
  const updatedSession =
    formStateTracker.setSessionFieldValues(session.form_session_id, currentValues) ??
    formStateTracker.getSession(session.form_session_id) ??
    session;
  return {
    data: {
      form_session: buildFormStateData(updatedSession),
    },
    message: tAiRuntime('formSubmissionTriggered'),
    success: true,
  };
}
