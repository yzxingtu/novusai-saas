import {
  LocatorResolutionError,
  LocatorResolver,
  type LocatorCandidate,
  type LocatorResolverOptions,
  type UIInteractableKind,
} from './locator-resolver';
import { tAiRuntime, tAiRuntimeSurfaceKind } from './i18n';
import { evaluateAIActionSecurity } from './security-policy';

export type UIActionType = 'ui_click' | 'ui_open_surface';

export type UISurfaceKind = 'drawer' | 'dropdown' | 'modal' | 'page' | 'popover';

export interface UISurfaceSummary {
  kind: UISurfaceKind;
  surface_id: string;
  title: string;
}

export interface UIActionDiff {
  active_surface_id: null | string;
  changed: boolean;
  page_key_changed: boolean;
  surfaces_added: UISurfaceSummary[];
  surfaces_removed: string[];
  ui_epoch: number;
}

export interface UIActionInvokePayload {
  action_type: UIActionType;
  confirm?: boolean;
  surface?: {
    kind?: UISurfaceKind;
    locator?: string;
    title?: string;
  };
  target_locator?: string;
  wait_timeout_ms?: number;
}

export interface UIActionExecutionResult {
  data?: Record<string, unknown>;
  diff: UIActionDiff;
  error?: string;
  error_type?: string;
  message: string;
  success: boolean;
}

export interface UIActionExecutorOptions {
  getPageKey?: () => string;
  getUiEpoch?: () => number;
  locatorOptions?: LocatorResolverOptions;
  locatorResolver?: LocatorResolver;
  setUiEpoch?: (value: number) => void;
}

interface UIStateSnapshot {
  activeSurfaceId: null | string;
  pageKey: string;
  surfaces: UISurfaceSummary[];
  uiEpoch: number;
}

const DEFAULT_WAIT_TIMEOUT_MS = 220;

function normalizeText(value: string): string {
  return value.replaceAll(/\s+/g, ' ').trim();
}

function normalizeKey(value: string): string {
  return normalizeText(value).toLocaleLowerCase();
}

function uniqueById(surfaces: UISurfaceSummary[]): UISurfaceSummary[] {
  const map = new Map<string, UISurfaceSummary>();
  surfaces.forEach((item) => {
    map.set(item.surface_id, item);
  });
  return Array.from(map.values());
}

function isVisible(element: Element): boolean {
  if (!(element instanceof HTMLElement)) {
    return false;
  }
  if (element.hidden) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (style.display === 'none' || style.visibility === 'hidden') {
    return false;
  }
  return element.getClientRects().length > 0 || style.opacity !== '0';
}

function resolveSurfaceTitle(root: Element): string {
  const titleNode = root.querySelector(
    '.ant-modal-title, .ant-drawer-title, [data-ai-surface-title], h1, h2, h3',
  );
  return normalizeText(
    (titleNode instanceof HTMLElement ? titleNode.innerText : titleNode?.textContent) ||
      '',
  );
}

function buildSurfaceId(kind: UISurfaceKind, root: Element, index: number): string {
  const customId =
    root.getAttribute('data-ai-surface-id') || root.getAttribute('id');
  if (customId) {
    return `${kind}:${customId}`;
  }
  const title = resolveSurfaceTitle(root);
  if (title) {
    return `${kind}:${title}`;
  }
  return `${kind}:${index}`;
}

function defaultPageKeyResolver(): string {
  const fromAttr = document.body.getAttribute('data-page-key');
  if (fromAttr) {
    return normalizeKey(fromAttr.replaceAll('/', '.'));
  }
  return normalizeKey(window.location.pathname.replace(/^\//, '').replaceAll('/', '.'));
}

function collectPageSurface(pageKey: string): UISurfaceSummary {
  const pageTitle =
    normalizeText(document.title) ||
    normalizeText(document.querySelector('h1')?.textContent || '') ||
    pageKey;
  return {
    kind: 'page',
    surface_id: `page:${pageKey || 'unknown'}`,
    title: pageTitle || tAiRuntime('surfaceTitle.page'),
  };
}

function collectOverlaySurfaces(): UISurfaceSummary[] {
  const overlays: UISurfaceSummary[] = [];

  const drawerNodes = document.querySelectorAll(
    '.ant-drawer, .ant-drawer-content-wrapper',
  );
  drawerNodes.forEach((node, index) => {
    if (!isVisible(node)) {
      return;
    }
    overlays.push({
      kind: 'drawer',
      surface_id: buildSurfaceId('drawer', node, index),
      title:
        resolveSurfaceTitle(node) ||
        tAiRuntime('surfaceTitle.drawer', { index: index + 1 }),
    });
  });

  const modalNodes = document.querySelectorAll(
    '.ant-modal-wrap, .ant-modal, [role="dialog"]',
  );
  modalNodes.forEach((node, index) => {
    if (!isVisible(node)) {
      return;
    }
    overlays.push({
      kind: 'modal',
      surface_id: buildSurfaceId('modal', node, index),
      title:
        resolveSurfaceTitle(node) ||
        tAiRuntime('surfaceTitle.modal', { index: index + 1 }),
    });
  });

  const dropdownNodes = document.querySelectorAll(
    '.ant-dropdown, .ant-select-dropdown, [data-ai-surface-kind="dropdown"]',
  );
  dropdownNodes.forEach((node, index) => {
    if (!isVisible(node)) {
      return;
    }
    overlays.push({
      kind: 'dropdown',
      surface_id: buildSurfaceId('dropdown', node, index),
      title:
        resolveSurfaceTitle(node) ||
        tAiRuntime('surfaceTitle.dropdown', { index: index + 1 }),
    });
  });

  const popoverNodes = document.querySelectorAll(
    '.ant-popover, [data-ai-surface-kind="popover"]',
  );
  popoverNodes.forEach((node, index) => {
    if (!isVisible(node)) {
      return;
    }
    overlays.push({
      kind: 'popover',
      surface_id: buildSurfaceId('popover', node, index),
      title:
        resolveSurfaceTitle(node) ||
        tAiRuntime('surfaceTitle.popover', { index: index + 1 }),
    });
  });

  return uniqueById(overlays);
}

function shouldForceChanged(kind: UIInteractableKind): boolean {
  return ['link', 'menu_item', 'pagination', 'tab'].includes(kind);
}

function findAddedSurfaces(
  before: UISurfaceSummary[],
  after: UISurfaceSummary[],
): UISurfaceSummary[] {
  const beforeIds = new Set(before.map((item) => item.surface_id));
  return after.filter((item) => !beforeIds.has(item.surface_id));
}

function findRemovedSurfaces(
  before: UISurfaceSummary[],
  after: UISurfaceSummary[],
): string[] {
  const afterIds = new Set(after.map((item) => item.surface_id));
  return before
    .filter((item) => !afterIds.has(item.surface_id))
    .map((item) => item.surface_id);
}

export class UIActionExecutor {
  private readonly getPageKey: () => string;
  private readonly getUiEpoch: () => number;
  private readonly locatorResolver: LocatorResolver;
  private readonly setUiEpoch: (value: number) => void;

  constructor(options: UIActionExecutorOptions = {}) {
    let localUiEpoch = 0;
    this.getUiEpoch = options.getUiEpoch ?? (() => localUiEpoch);
    this.setUiEpoch =
      options.setUiEpoch ??
      ((value) => {
        localUiEpoch = value;
      });
    this.getPageKey = options.getPageKey ?? defaultPageKeyResolver;
    this.locatorResolver =
      options.locatorResolver ?? new LocatorResolver(options.locatorOptions);
  }

  async execute(action: UIActionInvokePayload): Promise<UIActionExecutionResult> {
    const before = this.snapshot();
    try {
      if (action.action_type === 'ui_click') {
        return await this.executeClick(action, before);
      }
      if (action.action_type === 'ui_open_surface') {
        return await this.executeOpenSurface(action, before);
      }
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('unsupportedActionType', {
          actionType: action.action_type,
        }),
        error_type: 'invalid_action_type',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    } catch (error) {
      if (error instanceof LocatorResolutionError) {
        return {
          data:
            error.candidates.length > 0
              ? { candidates: error.candidates }
              : undefined,
          diff: this.buildDiff(before, this.snapshot(), false),
          error: error.message,
          error_type: error.code,
          message: tAiRuntime('actionExecutionFailed'),
          success: false,
        };
      }
      return {
        diff: this.buildDiff(before, this.snapshot(), false),
        error: error instanceof Error ? error.message : String(error),
        error_type: 'internal_error',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }
  }

  private buildDiff(
    before: UIStateSnapshot,
    after: UIStateSnapshot,
    semanticChanged: boolean,
  ): UIActionDiff {
    const surfacesAdded = findAddedSurfaces(before.surfaces, after.surfaces);
    const surfacesRemoved = findRemovedSurfaces(before.surfaces, after.surfaces);
    const pageKeyChanged = before.pageKey !== after.pageKey;
    const changed =
      semanticChanged || pageKeyChanged || surfacesAdded.length > 0 || surfacesRemoved.length > 0;
    const nextEpoch = changed ? Math.max(before.uiEpoch + 1, after.uiEpoch + 1) : before.uiEpoch;
    this.setUiEpoch(nextEpoch);

    return {
      active_surface_id: after.activeSurfaceId,
      changed,
      page_key_changed: pageKeyChanged,
      surfaces_added: surfacesAdded,
      surfaces_removed: surfacesRemoved,
      ui_epoch: nextEpoch,
    };
  }

  private clickElement(element: HTMLElement): void {
    const clickTarget =
      element.matches('.ant-pagination-item')
        ? (element.querySelector('a,button') as HTMLElement | null) || element
        : element;
    clickTarget.click();
  }

  private async executeClick(
    action: UIActionInvokePayload,
    before: UIStateSnapshot,
  ): Promise<UIActionExecutionResult> {
    const locator = normalizeText(action.target_locator || '');
    if (!locator) {
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('uiClickRequiresTargetLocator'),
        error_type: 'invalid_input',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    const resolved = this.locatorResolver.resolve(locator);
    if (resolved.candidate.disabled) {
      const target = resolved.candidate.label || locator;
      return {
        data: { candidates: [resolved.candidate] satisfies LocatorCandidate[] },
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetDisabled', { target }),
        error_type: 'element_disabled',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    const security = evaluateAIActionSecurity({
      actionKind: 'ui_click',
      element: resolved.element,
    });
    if (!security.allowed) {
      const target = resolved.candidate.label || locator;
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetBlockedByPolicy', { target }),
        error_type: security.reason || 'policy_blocked',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }
    if (security.requireConfirm && !action.confirm) {
      const target = resolved.candidate.label || locator;
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetRequiresConfirmation', { target }),
        error_type: 'confirmation_required',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    this.clickElement(resolved.element);
    await this.waitForUI(action.wait_timeout_ms);
    const after = this.snapshot();
    const diff = this.buildDiff(
      before,
      after,
      shouldForceChanged(resolved.candidate.kind),
    );

    return {
      data: {
        target_kind: resolved.candidate.kind,
        target_locator: resolved.candidate.locator,
      },
      diff,
      message: resolved.candidate.label
        ? tAiRuntime('clickedTarget', { target: resolved.candidate.label })
        : tAiRuntime('clickActionExecuted'),
      success: true,
    };
  }

  private async executeOpenSurface(
    action: UIActionInvokePayload,
    before: UIStateSnapshot,
  ): Promise<UIActionExecutionResult> {
    const surface = action.surface || {};
    const requestedKind = surface.kind;
    let locator = normalizeText(surface.locator || action.target_locator || '');

    if (!locator && surface.title) {
      locator = `text:${surface.title}`;
    }
    if (!locator) {
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('uiOpenSurfaceRequiresLocator'),
        error_type: 'invalid_input',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    const resolved = this.locatorResolver.resolve(locator);
    if (resolved.candidate.disabled) {
      const target = resolved.candidate.label || locator;
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetDisabled', { target }),
        error_type: 'element_disabled',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    const security = evaluateAIActionSecurity({
      actionKind: 'ui_open_surface',
      element: resolved.element,
    });
    if (!security.allowed) {
      const target = resolved.candidate.label || locator;
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetBlockedByPolicy', { target }),
        error_type: security.reason || 'policy_blocked',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }
    if (security.requireConfirm && !action.confirm) {
      const target = resolved.candidate.label || locator;
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('targetRequiresConfirmation', { target }),
        error_type: 'confirmation_required',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    this.clickElement(resolved.element);
    const waitTimeout = Math.max(action.wait_timeout_ms ?? 600, 120);
    await this.waitForUI(waitTimeout);
    const after = this.snapshot();
    const diff = this.buildDiff(before, after, true);

    const added = diff.surfaces_added;
    const kindMatched = requestedKind
      ? added.some((item) => item.kind === requestedKind)
      : added.length > 0;
    if (!kindMatched) {
      return {
        diff,
        error: requestedKind
          ? tAiRuntime('noNewRequestedSurfaceDetected', {
              kind: tAiRuntimeSurfaceKind(requestedKind),
              locator,
            })
          : tAiRuntime('noNewSurfaceDetected', { locator }),
        error_type: 'surface_not_opened',
        message: tAiRuntime('actionExecutionFailed'),
        success: false,
      };
    }

    return {
      data: {
        opened_surface_ids: added.map((item) => item.surface_id),
      },
      diff,
      message: tAiRuntime('surfaceOpenedSuccessfully'),
      success: true,
    };
  }

  private snapshot(): UIStateSnapshot {
    const pageKey = this.getPageKey();
    const pageSurface = collectPageSurface(pageKey);
    const overlaySurfaces = collectOverlaySurfaces();
    const surfaces = [pageSurface, ...overlaySurfaces];
    const activeSurface = surfaces.at(-1) || pageSurface;
    return {
      activeSurfaceId: activeSurface.surface_id,
      pageKey,
      surfaces,
      uiEpoch: this.getUiEpoch(),
    };
  }

  private async waitForUI(timeoutMs = DEFAULT_WAIT_TIMEOUT_MS): Promise<void> {
    const wait = Math.max(timeoutMs, 16);
    await new Promise<void>((resolve) => {
      window.setTimeout(() => resolve(), wait);
    });
  }
}
