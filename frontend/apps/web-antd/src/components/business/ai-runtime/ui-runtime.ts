import {
  createDefaultComponentAdapters,
  createVueRouterAdapter,
} from './component-adapters';
import { UIGraphBuilder } from './ui-graph-builder';
import { UIEpochManager } from './ui-epoch-manager';
import { UISurfaceTracker } from './surface-tracker';
import type {
  UIComponentAdapter,
  UIOverlaySurfaceInput,
  UIRouteLike,
  UIRuntimeOptions,
  UIRuntimeRebuildInput,
  UIRuntimeSnapshot,
  UIRuntimeState,
  UISurface,
  UISurfaceSyncInput,
} from './types';

const EMPTY_GRAPH: UIRuntimeState['ui_graph'] = {
  builtAt: 0,
  mode: 'compact',
  nodes: [],
  stats: {
    adapterNodeCount: 0,
    buildDurationMs: 0,
    domFallbackNodeCount: 0,
    domScanDurationMs: 0,
    scannedElements: 0,
    totalNodeCount: 0,
    truncated: false,
    usedDomFallback: false,
  },
};
const AI_PANEL_SELECTOR = '[data-ai-panel]';

interface LocatorCandidates {
  allowedVisible: HTMLElement[];
  allVisible: HTMLElement[];
}

function createGraphSignature(state: UIRuntimeState['ui_graph']): string {
  const parts = state.nodes.map((node) => {
    const label = node.label ?? '';
    return `${node.kind}|${node.locator}|${node.surfaceId ?? ''}|${node.disabled ? 1 : 0}|${node.visible ? 1 : 0}|${label}`;
  });
  return `${state.mode}|${parts.join(';')}`;
}

function routeFingerprint(route: null | UIRouteLike): string {
  if (!route) {
    return '';
  }
  const title = typeof route.meta?.title === 'string' ? route.meta.title : '';
  return `${route.fullPath}|${route.name ?? ''}|${title}`;
}

function cloneSurface(surface: UISurface): UISurface {
  return {
    ...surface,
    ...(surface.metadata ? { metadata: { ...surface.metadata } } : {}),
  };
}

function normalizeText(value: string): string {
  return value.replaceAll(/\s+/g, ' ').trim();
}

function escapeSelectorValue(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replaceAll('"', '\\"');
}

function isElementVisible(element: HTMLElement): boolean {
  if (element.hidden) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (style.display === 'none' || style.visibility === 'hidden') {
    return false;
  }
  return element.getClientRects().length > 0 || style.opacity !== '0';
}

function isAIExcludedElement(element: Element): boolean {
  let cursor: null | Element = element;
  while (cursor) {
    if (cursor.matches(AI_PANEL_SELECTOR)) {
      return true;
    }
    const dataAI = cursor.getAttribute('data-ai');
    if (typeof dataAI === 'string') {
      const hasOffDirective = dataAI
        .split(/\s+/)
        .some((token) => token.trim().toLocaleLowerCase() === 'off');
      if (hasOffDirective) {
        return true;
      }
    }
    cursor = cursor.parentElement;
  }
  return false;
}

function classifyCandidates(candidates: HTMLElement[]): LocatorCandidates {
  const allVisible = candidates.filter((element) => isElementVisible(element));
  return {
    allowedVisible: allVisible.filter(
      (element) => !isAIExcludedElement(element),
    ),
    allVisible,
  };
}

function queryLocatorCandidates(locator: string): LocatorCandidates {
  const normalized = normalizeText(locator);
  if (!normalized) {
    return {
      allowedVisible: [],
      allVisible: [],
    };
  }

  const prefixed = [
    ['ai-id:', `[data-ai-id="${escapeSelectorValue(normalized.slice(6))}"]`],
    ['testid:', `[data-testid="${escapeSelectorValue(normalized.slice(7))}"]`],
    ['id:', `#${escapeSelectorValue(normalized.slice(3))}`],
    ['name:', `[name="${escapeSelectorValue(normalized.slice(5))}"]`],
    ['href:', `a[href="${escapeSelectorValue(normalized.slice(5))}"]`],
  ] as const;
  for (const [prefix, selector] of prefixed) {
    if (!normalized.startsWith(prefix)) {
      continue;
    }
    try {
      return classifyCandidates(
        Array.from(document.querySelectorAll<HTMLElement>(selector)),
      );
    } catch {
      return {
        allowedVisible: [],
        allVisible: [],
      };
    }
  }

  if (normalized.startsWith('text:')) {
    const query = normalizeText(normalized.slice(5)).toLocaleLowerCase();
    if (!query) {
      return {
        allowedVisible: [],
        allVisible: [],
      };
    }
    return classifyCandidates(
      Array.from(document.querySelectorAll<HTMLElement>('body *')).filter(
        (element) =>
          normalizeText(element.innerText || element.textContent || '')
            .toLocaleLowerCase()
            .includes(query),
      ),
    );
  }

  const cssSelector = normalized.startsWith('css:')
    ? normalized.slice(4)
    : normalized;
  try {
    return classifyCandidates(
      Array.from(document.querySelectorAll<HTMLElement>(cssSelector)),
    );
  } catch {
    return {
      allowedVisible: [],
      allVisible: [],
    };
  }
}

function bindGraphSurfaceIds(
  graph: UIRuntimeState['ui_graph'],
  surfaces: UISurface[],
): UIRuntimeState['ui_graph'] {
  if (graph.nodes.length === 0 || surfaces.length === 0) {
    return graph;
  }

  const validIds = new Set(surfaces.map((surface) => surface.id));
  const pageSurfaceId = surfaces.find((surface) => surface.kind === 'page')?.id;
  const lastSurfaceIdByKind = new Map<UISurface['kind'], string>();
  surfaces.forEach((surface) => {
    lastSurfaceIdByKind.set(surface.kind, surface.id);
  });

  const overlaySelectors: Array<[UISurface['kind'], string]> = [
    ['popover', '.ant-popover'],
    ['dropdown', '.ant-dropdown, .ant-select-dropdown'],
    ['modal', '.ant-modal, .ant-modal-wrap, [role="dialog"]'],
    ['drawer', '.ant-drawer, .ant-drawer-content-wrapper, .ant-drawer-content'],
  ];

  let changed = false;
  const nextNodes: UIRuntimeState['ui_graph']['nodes'] = [];
  graph.nodes.forEach((node) => {
    const candidates = queryLocatorCandidates(node.locator);
    if (
      candidates.allVisible.length > 0 &&
      candidates.allowedVisible.length === 0
    ) {
      changed = true;
      return;
    }

    let nextSurfaceId = validIds.has(node.surfaceId ?? '') ? node.surfaceId : undefined;
    if (!nextSurfaceId) {
      const element = candidates.allowedVisible[0] ?? null;
      if (element) {
        for (const [kind, selector] of overlaySelectors) {
          if (element.closest(selector)) {
            const overlaySurfaceId = lastSurfaceIdByKind.get(kind);
            if (overlaySurfaceId) {
              nextSurfaceId = overlaySurfaceId;
            }
            break;
          }
        }
      }
    }
    if (!nextSurfaceId && pageSurfaceId) {
      nextSurfaceId = pageSurfaceId;
    }
    if (nextSurfaceId !== node.surfaceId) {
      changed = true;
      nextNodes.push({
        ...node,
        surfaceId: nextSurfaceId,
      });
      return;
    }
    nextNodes.push(node);
  });

  if (!changed) {
    return graph;
  }
  return {
    ...graph,
    nodes: nextNodes,
    stats: {
      ...graph.stats,
      totalNodeCount: nextNodes.length,
    },
  };
}

export class UIRuntime {
  private readonly epochManager = new UIEpochManager();

  private readonly graphBuilder: UIGraphBuilder;

  private readonly surfaceTracker = new UISurfaceTracker();

  private readonly getRoute?: () => null | UIRouteLike;

  private graphSignature = createGraphSignature(EMPTY_GRAPH);

  private routeFingerprintValue = '';

  private route: null | UIRouteLike = null;

  private state: UIRuntimeState = {
    surface_stack: [],
    ui_epoch: 0,
    ui_graph: EMPTY_GRAPH,
  };

  constructor(options: UIRuntimeOptions = {}) {
    const baseAdapters =
      options.adapters ??
      createDefaultComponentAdapters({
        router: {
          getRoute: options.getRoute,
        },
      });
    const hasRouterAdapter = baseAdapters.some((adapter) => adapter.id === 'vue-router');
    const adapters = hasRouterAdapter
      ? baseAdapters
      : [createVueRouterAdapter({ getRoute: options.getRoute }), ...baseAdapters];
    this.graphBuilder = new UIGraphBuilder({
      adapters,
      document: options.document,
      domScannerOptions: options.domScannerOptions,
      includeDomFallbackInCompact: options.includeDomFallbackInCompact,
      root: options.root,
    });
    this.getRoute = options.getRoute;
    this.route = options.route ?? options.getRoute?.() ?? null;
    this.routeFingerprintValue = routeFingerprint(this.route);
  }

  closeSurface(surfaceId: string): UIRuntimeSnapshot {
    const removed = this.surfaceTracker.closeSurfaceById(surfaceId);
    if (removed.length > 0) {
      this.epochManager.bump('surface_closed', {
        count: removed.length,
      });
      this.refreshStateEpochOnly();
    }
    return this.getSnapshot();
  }

  getEpoch(): number {
    return this.epochManager.current();
  }

  getSnapshot(): UIRuntimeSnapshot {
    return {
      active_surface: this.surfaceTracker.getActiveSurface(),
      surface_stack: this.state.surface_stack.map((surface) => cloneSurface(surface)),
      ui_epoch: this.state.ui_epoch,
      ui_graph: {
        ...this.state.ui_graph,
        nodes: this.state.ui_graph.nodes.map((node) => ({ ...node })),
        stats: { ...this.state.ui_graph.stats },
      },
    };
  }

  initialize(): UIRuntimeSnapshot {
    return this.rebuildGraph({
      mode: 'compact',
    });
  }

  listAdapters(): UIComponentAdapter[] {
    return this.graphBuilder.getAdapters();
  }

  openSurface(input: UIOverlaySurfaceInput): UIRuntimeSnapshot {
    this.surfaceTracker.openOverlay(input);
    this.epochManager.bump('surface_opened', {
      kind: input.kind,
      key: input.key,
    });
    this.refreshStateEpochOnly();
    return this.getSnapshot();
  }

  rebuildGraph(input: UIRuntimeRebuildInput = {}): UIRuntimeSnapshot {
    const nextRoute = input.route ?? this.getRoute?.() ?? this.route;
    const routeChanged = this.applyRoute(nextRoute ?? null);
    const built = this.graphBuilder.build({
      activeSurfaceId: this.surfaceTracker.getActiveSurface()?.id ?? null,
      forceDomFallback: input.forceDomFallback,
      mode: input.mode,
      route: this.route,
    });

    const surfaceDelta = this.surfaceTracker.sync({
      overlays: built.overlays,
      page: built.page,
    });
    const nextSurfaceStack = this.surfaceTracker.getStack();
    const boundGraph = bindGraphSurfaceIds(built.graph, nextSurfaceStack);
    const nextGraphSignature = createGraphSignature(boundGraph);
    const graphChanged = nextGraphSignature !== this.graphSignature;
    if (graphChanged) {
      this.graphSignature = nextGraphSignature;
    }

    if (graphChanged) {
      this.epochManager.bump('graph_rebuilt', {
        mode: boundGraph.mode,
      });
    } else if (surfaceDelta.changed) {
      this.epochManager.bump('surface_synced');
    } else if (routeChanged) {
      this.epochManager.bump('route_changed');
    }

    this.state = {
      surface_stack: nextSurfaceStack,
      ui_epoch: this.epochManager.current(),
      ui_graph: boundGraph,
    };
    return this.getSnapshot();
  }

  registerAdapter(adapter: UIComponentAdapter): void {
    this.graphBuilder.registerAdapter(adapter);
  }

  syncRoute(route: null | UIRouteLike): UIRuntimeSnapshot {
    this.route = route;
    return this.rebuildGraph({
      mode: 'compact',
      route,
    });
  }

  syncSurfaces(input: UISurfaceSyncInput): UIRuntimeSnapshot {
    const delta = this.surfaceTracker.sync(input);
    if (delta.changed) {
      this.epochManager.bump('surface_synced', {
        added: delta.added.length,
        removed: delta.removed.length,
        updated: delta.updated.length,
      });
      this.refreshStateEpochOnly();
    }
    return this.getSnapshot();
  }

  unregisterAdapter(adapterId: string): boolean {
    return this.graphBuilder.unregisterAdapter(adapterId);
  }

  private applyRoute(nextRoute: null | UIRouteLike): boolean {
    const nextFingerprint = routeFingerprint(nextRoute);
    const changed = nextFingerprint !== this.routeFingerprintValue;
    if (changed) {
      this.routeFingerprintValue = nextFingerprint;
      this.route = nextRoute;
    }
    return changed;
  }

  private refreshStateEpochOnly(): void {
    this.state = {
      ...this.state,
      surface_stack: this.surfaceTracker.getStack(),
      ui_epoch: this.epochManager.current(),
    };
  }
}

export function createUIRuntime(options: UIRuntimeOptions = {}): UIRuntime {
  return new UIRuntime(options);
}
