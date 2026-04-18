import type { UIInteractableKind } from './locator-resolver';
import type {
  UIStateSnapshot,
  UISurfaceKind,
  UISurfaceSummary,
} from './ui-action-executor-contracts';

import { tAiRuntime } from './i18n';

export const DEFAULT_WAIT_TIMEOUT_MS = 220;

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
  return [...map.values()];
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
    (titleNode instanceof HTMLElement
      ? titleNode.innerText
      : titleNode?.textContent) || '',
  );
}

function buildSurfaceId(
  kind: UISurfaceKind,
  root: HTMLElement,
  index: number,
): string {
  const customId = root.dataset.aiSurfaceId || root.getAttribute('id');
  if (customId) {
    return `${kind}:${customId}`;
  }
  const title = resolveSurfaceTitle(root);
  if (title) {
    return `${kind}:${title}`;
  }
  return `${kind}:${index}`;
}

export function defaultPageKeyResolver(): string {
  const fromAttr = document.body.dataset.pageKey;
  if (fromAttr) {
    return normalizeKey(fromAttr.replaceAll('/', '.'));
  }
  return normalizeKey(
    window.location.pathname.replace(/^\//, '').replaceAll('/', '.'),
  );
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

  const drawerNodes = document.querySelectorAll<HTMLElement>(
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

  const modalNodes = document.querySelectorAll<HTMLElement>(
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

  const dropdownNodes = document.querySelectorAll<HTMLElement>(
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

  const popoverNodes = document.querySelectorAll<HTMLElement>(
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

export function shouldForceChanged(kind: UIInteractableKind): boolean {
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

export function buildDiff(args: {
  after: UIStateSnapshot;
  before: UIStateSnapshot;
  semanticChanged: boolean;
  setUiEpoch: (value: number) => void;
}) {
  const surfacesAdded = findAddedSurfaces(
    args.before.surfaces,
    args.after.surfaces,
  );
  const surfacesRemoved = findRemovedSurfaces(
    args.before.surfaces,
    args.after.surfaces,
  );
  const pageKeyChanged = args.before.pageKey !== args.after.pageKey;
  const changed =
    args.semanticChanged ||
    pageKeyChanged ||
    surfacesAdded.length > 0 ||
    surfacesRemoved.length > 0;
  const nextEpoch = changed
    ? Math.max(args.before.uiEpoch + 1, args.after.uiEpoch)
    : args.before.uiEpoch;
  args.setUiEpoch(nextEpoch);

  return {
    active_surface_id: args.after.activeSurfaceId,
    changed,
    page_key_changed: pageKeyChanged,
    surfaces_added: surfacesAdded,
    surfaces_removed: surfacesRemoved,
    ui_epoch: nextEpoch,
  };
}

export function snapshotUIState(args: {
  getPageKey: () => string;
  getUiEpoch: () => number;
}): UIStateSnapshot {
  const pageKey = args.getPageKey();
  const pageSurface = collectPageSurface(pageKey);
  const overlaySurfaces = collectOverlaySurfaces();
  const surfaces = [pageSurface, ...overlaySurfaces];
  const activeSurface = surfaces.at(-1) || pageSurface;
  return {
    activeSurfaceId: activeSurface.surface_id,
    pageKey,
    surfaces,
    uiEpoch: args.getUiEpoch(),
  };
}
