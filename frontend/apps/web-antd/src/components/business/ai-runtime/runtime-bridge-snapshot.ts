import type { MenuRecordRaw } from '@vben/types';

import type { FormSession } from './form-session-manager';
import type { RuntimeSnapshotResult } from './runtime-bridge-core';
import type {
  UISnapshotMode,
  UISnapshotNodeInput,
} from './ui-snapshot-generator';

import type {
  ActiveFormSummary,
  PageContext,
  PageContextSearchInputAffordance,
  PageContextVisibleTableAffordance,
} from '#/api/shared/ai-chat';

import { useAccessStore } from '@vben/stores';

import { formStateTracker } from '#/composables/use-form-state-tracker';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
import { getEndpointFromPath } from '#/utils/endpoint';
import {
  buildCompactNavigationPageData,
  buildMenuNavigationEntries,
} from '#/utils/menu-navigation';

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
const SEARCH_INPUT_HINT_TOKENS = [
  'search',
  'filter',
  'query',
  'keyword',
  '搜索',
  '筛选',
  '查找',
  '关键字',
  '关键词',
] as const;

type RuntimeGraphNode = {
  kind?: string;
  label?: string;
  locator?: string;
  metadata?: Record<string, unknown>;
};

const READABLE_CONTENT_SELECTOR = [
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'p',
  'li',
  'dt',
  'dd',
  'blockquote',
  '[data-ai-readable]',
  '[data-ai-content]',
  '.ant-alert',
  '.ant-card',
  '.ant-descriptions',
  '.ant-list',
  '.ant-result',
  '.ant-statistic',
  '[aria-controls]',
  '[aria-haspopup]',
  '[data-ai-action]',
  'form',
  '.ant-form',
  'table',
  '.ant-table-wrapper',
  '.vxe-table',
  'button',
  '.ant-btn',
  '.ant-dropdown-trigger',
  '.ant-input-search-button',
  '.vben-button',
  '.vxe-button',
  '.vxe-pager--next-btn',
  '.vxe-pager--prev-btn',
  '[role="button"]',
].join(',');

const AI_EXCLUDE_SELECTOR =
  '[data-ai-panel],[data-ai="off"],[data-ai-disabled]';
const ACTIVE_CONTENT_SELECTOR = [
  '.ant-modal',
  '.ant-modal-wrap',
  '[role="dialog"]',
  '.ant-drawer-content',
  '.ant-drawer-content-wrapper',
  '.ant-popover',
].join(',');
const MAIN_CONTENT_SELECTOR = [
  '[data-ai-main]',
  '[data-ai-region="main"]',
  '[role="main"]',
  'main',
  '.vben-page',
  '.vben-main',
  '.vben-layout-content',
  '.page-content',
  '.ant-layout-content',
].join(',');
const CORE_CONTENT_SELECTOR = [
  '[data-ai-region]',
  '[data-ai-card]',
  '.ant-alert',
  '.ant-card',
  '.ant-descriptions',
  '.ant-list',
  '.ant-result',
  '.ant-statistic',
  '.ant-table-wrapper',
  '.vxe-table',
  'form',
  'table',
].join(',');
const NAVIGATION_NOISE_SELECTOR = [
  'header',
  '.ant-layout-header',
  '.vben-layout-header',
  'aside',
  '.ant-layout-sider',
  '.vben-layout-sider',
  'nav',
  '.ant-menu',
  '[data-ai-region="navigation"]',
  '[data-ai-region="sidebar"]',
  '[class*="topbar" i]',
  '[class*="weather" i]',
].join(',');

const SNAPSHOT_CACHE_TTL_MS = 160;

let snapshotCache:
  | {
      expiresAt: number;
      key: string;
      value: RuntimeSnapshotResult;
    }
  | null = null;

function buildSnapshotCacheKey(mode: UISnapshotMode): string {
  const body = typeof document === 'undefined' ? null : document.body;
  return [
    mode,
    resolveRuntimePathname(),
    resolveRuntimePageKey(),
    getActivePageSessionId() || '',
    getRuntimeEpochFloor(),
    body?.childElementCount ?? 0,
    body?.textContent?.length ?? 0,
  ].join('|');
}

function resolveRuntimePathname(): string {
  const routePath = resolveCurrentRoute()?.fullPath;
  const windowPath =
    typeof window === 'undefined' ? '' : window.location.pathname;
  return String(routePath || windowPath || '').split(/[?#]/, 1)[0] || '';
}

function isReadableElementVisible(element: HTMLElement): boolean {
  if (element.hidden || element.getAttribute('aria-hidden') === 'true') {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (style.display === 'none' || style.visibility === 'hidden') {
    return false;
  }
  return style.opacity !== '0';
}

function isAIExcludedElement(element: HTMLElement): boolean {
  let cursor: HTMLElement | null = element;
  while (cursor) {
    if (cursor.matches(AI_EXCLUDE_SELECTOR)) {
      return true;
    }
    const dataAI = cursor.dataset.ai;
    if (
      typeof dataAI === 'string' &&
      dataAI
        .split(/\s+/)
        .some((token) => token.trim().toLocaleLowerCase() === 'off')
    ) {
      return true;
    }
    const aiDisabled = cursor.dataset.aiDisabled;
    if (
      typeof aiDisabled === 'string' &&
      !['', '0', 'false', 'no', 'off'].includes(
        aiDisabled.trim().toLocaleLowerCase(),
      )
    ) {
      return true;
    }
    cursor = cursor.parentElement;
  }
  return false;
}

function escapeReadableSelectorValue(value: string): string {
  const escaper =
    typeof CSS !== 'undefined' && typeof CSS.escape === 'function'
      ? CSS.escape
      : (raw: string) => raw.replaceAll('"', String.raw`\"`);
  return escaper(value);
}

function buildReadableLocator(element: HTMLElement): string {
  const aiId = element.dataset.aiId;
  if (aiId) {
    return `ai-id:${aiId}`;
  }
  const testId = element.dataset.testid;
  if (testId) {
    return `testid:${testId}`;
  }
  const actionId = element.dataset.aiActionId;
  if (actionId) {
    return `action-id:${actionId}`;
  }
  const action = element.dataset.aiAction;
  if (action) {
    return `action:${action}`;
  }
  if (element.id) {
    return `id:${element.id}`;
  }
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel) {
    return `css:${element.tagName.toLocaleLowerCase()}[aria-label="${escapeReadableSelectorValue(ariaLabel)}"]`;
  }
  const name = element.getAttribute('name');
  if (name) {
    return `name:${name}`;
  }
  const tag = element.tagName.toLocaleLowerCase();
  const index = [
    ...(element.parentElement?.querySelectorAll(tag) || []),
  ].indexOf(element);
  return `css:${tag}:nth-of-type(${Math.max(index + 1, 1)})`;
}

function readDirectElementText(element: HTMLElement): string {
  const textParts: string[] = [];
  element.childNodes.forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      textParts.push(node.textContent || '');
    }
  });
  return normalizeText(textParts.join(' '), 600);
}

function readInputLabel(
  element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
): string {
  if (element.id) {
    const label = document.querySelector<HTMLLabelElement>(
      `label[for="${escapeReadableSelectorValue(element.id)}"]`,
    );
    const labelText = normalizeText(label?.textContent || '', 120);
    if (labelText) {
      return labelText;
    }
  }
  return normalizeText(
    element.getAttribute('aria-label') ||
      element.getAttribute('placeholder') ||
      element.getAttribute('name') ||
      '',
    120,
  );
}

function readFormText(element: HTMLElement): string {
  const fields = [
    ...element.querySelectorAll<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >('input,select,textarea'),
  ]
    .filter(
      (field) => !isAIExcludedElement(field) && isReadableElementVisible(field),
    )
    .map((field) =>
      normalizeText(
        `${readInputLabel(field)} ${
          field instanceof HTMLSelectElement
            ? field.selectedOptions[0]?.textContent || field.value
            : field.value || field.getAttribute('value') || ''
        }`,
        240,
      ),
    )
    .filter(Boolean);
  const ownText = readDirectElementText(element);
  return normalizeText([ownText, ...fields].filter(Boolean).join(' '), 1200);
}

function readButtonText(element: HTMLElement): string {
  const labelledBy = (element.getAttribute('aria-labelledby') || '')
    .split(/\s+/)
    .map((id) => id.trim())
    .filter(Boolean)
    .map(
      (id) =>
        document.querySelector(`#${escapeReadableSelectorValue(id)}`)
          ?.textContent || '',
    )
    .filter(Boolean)
    .join(' ');
  return normalizeText(
    element.dataset.aiLabel ||
      element.getAttribute('aria-label') ||
      labelledBy ||
      element.getAttribute('title') ||
      element.dataset.aiAction ||
      element.textContent ||
      '',
    200,
  );
}

function readTableText(element: HTMLElement): string {
  const cells = [
    ...element.querySelectorAll<HTMLTableCellElement>('th,td'),
  ].map((cell) => normalizeText(cell.textContent || '', 160));
  return normalizeText(cells.filter(Boolean).join(' '), 1200);
}

function readReadableElementText(element: HTMLElement): string {
  if (element.matches('form,.ant-form')) {
    return readFormText(element);
  }
  if (element.matches('table,.ant-table-wrapper,.vxe-table')) {
    return readTableText(element);
  }
  if (
    element.matches(
      'button,.ant-btn,.ant-dropdown-trigger,.ant-input-search-button,.vben-button,.vxe-button,[data-ai-action],[role="button"]',
    )
  ) {
    return readButtonText(element);
  }
  return normalizeText(element.textContent || '', 1200);
}

function scoreReadableElement(element: HTMLElement): number {
  let score = 0;
  if (element.closest(ACTIVE_CONTENT_SELECTOR)) {
    score += 140;
  }
  if (element.matches(MAIN_CONTENT_SELECTOR)) {
    score += 90;
  }
  if (element.closest(MAIN_CONTENT_SELECTOR)) {
    score += 70;
  }
  if (element.matches(CORE_CONTENT_SELECTOR)) {
    score += 35;
  }
  if (element.closest(CORE_CONTENT_SELECTOR)) {
    score += 15;
  }
  if (element.matches('h1,h2,h3,h4,.ant-card-head-title')) {
    score += 20;
  }
  if (element.matches('table,.ant-table-wrapper,.vxe-table,form,.ant-form')) {
    score += 25;
  }
  if (element.closest(NAVIGATION_NOISE_SELECTOR)) {
    score -= 120;
  }
  return score;
}

function scoreSnapshotNode(node: UISnapshotNodeInput): number {
  const element = node.locator ? queryElementByLocator(node.locator) : null;
  let score = element ? scoreReadableElement(element) : 0;
  const kind = normalizeText(node.kind || '', 64);
  if (['region', 'text', 'heading'].includes(kind)) {
    score += 8;
  }
  if (['form', 'table'].includes(kind)) {
    score += 18;
  }
  if (node.interactable) {
    score -= 4;
  }
  const text = normalizeText(node.label || node.text || node.content || '', 400);
  if (text) {
    score += Math.min(Math.floor(text.length / 80), 8);
  }
  return score;
}

function resolveReadableKind(element: HTMLElement): string {
  const tag = element.tagName.toLocaleLowerCase();
  if (element.matches('form,.ant-form')) {
    return 'form';
  }
  if (element.matches('table,.ant-table-wrapper,.vxe-table')) {
    return 'table';
  }
  if (
    element.matches(
      'button,.ant-btn,.ant-dropdown-trigger,.ant-input-search-button,.vben-button,.vxe-button,[data-ai-action],[role="button"]',
    )
  ) {
    return 'button';
  }
  if (/^h[1-6]$/.test(tag)) {
    return 'heading';
  }
  return 'text';
}

function collectVisibleReadableNodes(
  existingNodes: UISnapshotNodeInput[],
  activeSurfaceId?: string,
): UISnapshotNodeInput[] {
  if (typeof document === 'undefined' || !document.body) {
    return existingNodes.toSorted(
      (left, right) => scoreSnapshotNode(right) - scoreSnapshotNode(left),
    );
  }

  const nodes: UISnapshotNodeInput[] = [];
  const seenLocators = new Set(
    existingNodes
      .map((node) => normalizeText(node.locator || '', 240))
      .filter(Boolean),
  );
  const seenText = new Set<string>();

  existingNodes.forEach((node) => {
    const element = node.locator ? queryElementByLocator(node.locator) : null;
    if (element && (isAIExcludedElement(element) || !isReadableElementVisible(element))) {
      return;
    }
    nodes.push(node);
  });

  const readableElements = [
    ...document.body.querySelectorAll<HTMLElement>(READABLE_CONTENT_SELECTOR),
  ].toSorted((left, right) => {
    const scoreDiff = scoreReadableElement(right) - scoreReadableElement(left);
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    return 0;
  });

  readableElements.forEach((element) => {
    if (isAIExcludedElement(element) || !isReadableElementVisible(element)) {
      return;
    }
    if (
      element.closest(NAVIGATION_NOISE_SELECTOR) &&
      !element.matches(
        'button,.ant-btn,.ant-dropdown-trigger,.ant-input-search-button,[data-ai-action],[role="button"]',
      )
    ) {
      return;
    }
    if (
      element.parentElement?.closest(
        'form,.ant-form,table,.ant-table-wrapper,.vxe-table',
      ) &&
      !element.matches('button,.ant-btn,[role="button"]')
    ) {
      return;
    }
    const text = readReadableElementText(element);
    if (!text || seenText.has(text)) {
      return;
    }
    const locator = buildReadableLocator(element);
    if (seenLocators.has(locator)) {
      return;
    }
    seenLocators.add(locator);
    seenText.add(text);
    const kind = resolveReadableKind(element);
    nodes.push({
      children_count: element.children.length,
      content: text,
      interactable: kind === 'button',
      kind,
      label: text,
      locator,
      node_id: `dom-readable:${kind}:${locator}`,
      surface_id: activeSurfaceId,
      text,
    });
  });

  return nodes.toSorted(
    (left, right) => scoreSnapshotNode(right) - scoreSnapshotNode(left),
  );
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

function looksLikeSearchInputAffordance(text: string): boolean {
  const normalized = text.trim().toLocaleLowerCase();
  if (!normalized) {
    return false;
  }
  return SEARCH_INPUT_HINT_TOKENS.some((token) => normalized.includes(token));
}

function mergeRuntimePageData(
  ...parts: Array<PageContext['page_data'] | undefined>
): PageContext['page_data'] | undefined {
  const merged = Object.assign({}, ...parts.filter(Boolean));
  return Object.keys(merged).length > 0
    ? (merged as PageContext['page_data'])
    : undefined;
}

function resolveRuntimeAffordancePageData(
  nodes: RuntimeGraphNode[],
): PageContext['page_data'] | undefined {
  const searchInputs: PageContextSearchInputAffordance[] = [];
  const visibleTables: PageContextVisibleTableAffordance[] = [];
  const seenSearchLocators = new Set<string>();
  const seenTableLocators = new Set<string>();

  for (const node of nodes) {
    const kind = normalizeText(node.kind || '', 32);
    const locator = normalizeText(node.locator || '', 240);
    if (!kind || !locator) {
      continue;
    }

    if (kind === 'table') {
      if (seenTableLocators.has(locator)) {
        continue;
      }
      seenTableLocators.add(locator);
      const metadata = node.metadata ?? {};
      visibleTables.push({
        label: normalizeText(node.label || '', 200) || undefined,
        locator,
        column_count:
          typeof metadata.columnCount === 'number'
            ? Math.max(Math.floor(metadata.columnCount), 0)
            : undefined,
        row_count:
          typeof metadata.rowCount === 'number'
            ? Math.max(Math.floor(metadata.rowCount), 0)
            : undefined,
      });
      if (visibleTables.length >= 6) {
        continue;
      }
    }

    const isSearchControl =
      ['input', 'select', 'textarea'].includes(kind) ||
      (kind === 'button' &&
        looksLikeSearchInputAffordance(
          [node.label, locator, String(node.metadata?.dataAiAction ?? '')]
            .filter(Boolean)
            .join(' '),
        ));
    if (!isSearchControl) {
      continue;
    }

    const element = queryElementByLocator(locator);
    const placeholder =
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement
        ? normalizeText(element.placeholder || '', 200) || undefined
        : undefined;
    const fieldName = normalizeText(element?.getAttribute('name') || '', 120);
    const label = normalizeText(node.label || '', 200);
    if (
      !looksLikeSearchInputAffordance(
        [label, placeholder, fieldName, locator].filter(Boolean).join(' '),
      )
    ) {
      continue;
    }
    if (seenSearchLocators.has(locator)) {
      continue;
    }
    seenSearchLocators.add(locator);
    searchInputs.push({
      ...(fieldName ? { field_name: fieldName } : {}),
      ...(label ? { label } : {}),
      locator,
      ...(placeholder ? { placeholder } : {}),
    });
    if (searchInputs.length >= 6) {
      break;
    }
  }

  return mergeRuntimePageData(
    searchInputs.length > 0 ? { search_inputs: searchInputs } : undefined,
    visibleTables.length > 0 ? { visible_tables: visibleTables } : undefined,
  );
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

export function resolveActiveFormSession(options?: {
  activeSurfaceId?: string;
  surfaceIds?: string[];
}): FormSession | null {
  const tracker = formStateTracker as {
    getActiveSession?: (surfaceId?: string) => FormSession | null;
    getActiveSessionBySurfaceId?: (surfaceId: string) => FormSession | null;
    getSession?: (pageKeyOrSessionId: string) => FormSession | null;
    getSessionBySessionId?: (sessionId: string) => FormSession | null;
    getSessionBySurfaceId?: (surfaceId: string) => FormSession | null;
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

  if (typeof tracker.getActiveSession === 'function') {
    return tracker.getActiveSession() ?? null;
  }

  return null;
}

export function buildSnapshot(
  mode: UISnapshotMode = 'compact',
): RuntimeSnapshotResult {
  const cacheKey = buildSnapshotCacheKey(mode);
  const now = Date.now();
  if (
    snapshotCache &&
    snapshotCache.key === cacheKey &&
    snapshotCache.expiresAt > now
  ) {
    return snapshotCache.value;
  }

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
    resolveActiveFormSession({
      activeSurfaceId,
      surfaceIds: runtimeSnapshot.surface_stack.map((surface) => surface.id),
    }),
  );
  const snapshotNodes = runtimeSnapshot.ui_graph.nodes.map((node) => {
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
      metadata: node.metadata,
      node_id: node.id,
      role: undefined,
      surface_id: node.surfaceId,
      text: node.label,
    };
  });
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
      nodes: collectVisibleReadableNodes(snapshotNodes, activeSurfaceId),
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
  const affordancePageData = resolveRuntimeAffordancePageData(
    runtimeSnapshot.ui_graph.nodes,
  );
  const pageData = mergeRuntimePageData(navigationPageData, affordancePageData);

  const pageContext: PageContext = {
    ...snapshotGenerator.buildThinPageContext({
      locale: resolveRuntimeLocale(),
      pageKey,
      pageSessionId: getActivePageSessionId() || undefined,
      pageTitle: resolvePageTitle(pageKey),
      snapshot: thinSnapshot,
    }),
    ...(pageData ? { page_data: pageData } : {}),
  };
  const result = {
    pageContext,
    sizeBytes: byteSize(pageContext),
    snapshot: thinSnapshot,
  };
  snapshotCache = {
    expiresAt: now + SNAPSHOT_CACHE_TTL_MS,
    key: cacheKey,
    value: result,
  };
  return result;
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
