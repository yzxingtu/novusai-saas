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

function createGraphSignature(state: UIRuntimeState['ui_graph']): string {
  const parts = state.nodes.map((node) => {
    const label = node.label ?? '';
    return `${node.kind}|${node.locator}|${node.disabled ? 1 : 0}|${node.visible ? 1 : 0}|${label}`;
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
    const buildResult = this.graphBuilder.build({
      activeSurfaceId: this.surfaceTracker.getActiveSurface()?.id ?? null,
      forceDomFallback: input.forceDomFallback,
      mode: input.mode,
      route: this.route,
    });
    const graphChanged =
      createGraphSignature(buildResult.graph) !== this.graphSignature;
    if (graphChanged) {
      this.graphSignature = createGraphSignature(buildResult.graph);
    }

    const surfaceDelta = this.surfaceTracker.sync({
      overlays: buildResult.overlays,
      page: buildResult.page,
    });
    if (graphChanged) {
      this.epochManager.bump('graph_rebuilt', {
        mode: buildResult.graph.mode,
      });
    } else if (surfaceDelta.changed) {
      this.epochManager.bump('surface_synced');
    } else if (routeChanged) {
      this.epochManager.bump('route_changed');
    }

    this.state = {
      surface_stack: this.surfaceTracker.getStack(),
      ui_epoch: this.epochManager.current(),
      ui_graph: buildResult.graph,
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
