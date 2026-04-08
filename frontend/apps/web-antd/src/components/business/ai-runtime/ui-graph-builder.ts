import {
  createDefaultComponentAdapters,
  type CreateDefaultAdaptersOptions,
} from './component-adapters';
import { DOMScanner } from './dom-scanner';
import type {
  DOMScanMode,
  DOMScanResult,
  UIGraph,
  UIGraphBuildInput,
  UIGraphBuildResult,
  UIGraphBuilderOptions,
  UIGraphNode,
  UIComponentAdapter,
  UIOverlaySurfaceInput,
  UIPageSurfaceInput,
  UIRouteLike,
} from './types';

const EMPTY_ROUTE = '/';

function nowInMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function createPageFallback(
  route: null | UIRouteLike,
  document: Document,
): UIPageSurfaceInput {
  const pathFromRoute = route?.fullPath || EMPTY_ROUTE;
  const pageKey = pathFromRoute
    .replaceAll(/[?#].*$/g, '')
    .replaceAll(/\/+/g, '/')
    .replaceAll('/', ':')
    .replaceAll(/^:+|:+$/g, '') || 'root';
  const titleFromRoute = typeof route?.meta?.title === 'string' ? route.meta.title : '';
  const title = titleFromRoute.trim() || document.title || pageKey;
  return {
    key: `page:${pageKey}`,
    metadata: {
      source: 'fallback',
    },
    pageKey,
    routePath: pathFromRoute,
    title,
  };
}

function nodeKey(node: UIGraphNode): string {
  return `${node.kind}|${node.locator}`;
}

function sortAdapters(adapters: UIComponentAdapter[]): UIComponentAdapter[] {
  return [...adapters].sort((left, right) => right.priority - left.priority);
}

function sortNodes(nodes: UIGraphNode[]): UIGraphNode[] {
  return [...nodes].sort((left, right) => {
    if (left.kind !== right.kind) {
      return left.kind.localeCompare(right.kind);
    }
    return left.locator.localeCompare(right.locator);
  });
}

function cloneOverlay(input: UIOverlaySurfaceInput): UIOverlaySurfaceInput {
  return {
    ...input,
    ...(input.metadata ? { metadata: { ...input.metadata } } : {}),
  };
}

function cloneNode(input: UIGraphNode): UIGraphNode {
  return {
    ...input,
    ...(input.metadata ? { metadata: { ...input.metadata } } : {}),
    ...(input.extensions ? { extensions: { ...input.extensions } } : {}),
  };
}

export interface UIGraphBuilderConstructorOptions extends UIGraphBuilderOptions {
  defaultAdaptersOptions?: CreateDefaultAdaptersOptions;
}

export class UIGraphBuilder {
  private readonly document: Document;

  private readonly root: ParentNode;

  private readonly scanner: DOMScanner;

  private readonly includeDomFallbackInCompact: boolean;

  private adapters: UIComponentAdapter[];

  constructor(options: UIGraphBuilderConstructorOptions = {}) {
    this.document = options.document ?? document;
    this.root = options.root ?? this.document.body ?? this.document;
    this.scanner = new DOMScanner(options.domScannerOptions);
    this.includeDomFallbackInCompact = Boolean(
      options.includeDomFallbackInCompact,
    );
    const configuredAdapters =
      options.adapters ??
      createDefaultComponentAdapters(options.defaultAdaptersOptions);
    this.adapters = sortAdapters(configuredAdapters);
  }

  build(input: UIGraphBuildInput = {}): UIGraphBuildResult {
    const mode = input.mode ?? 'compact';
    const start = nowInMs();
    const overlayMap = new Map<string, UIOverlaySurfaceInput>();
    const nodeMap = new Map<string, UIGraphNode>();
    const route = input.route ?? null;
    const adapterContext = {
      activeSurfaceId: input.activeSurfaceId ?? null,
      document: this.document,
      mode,
      now: Date.now(),
      root: this.root,
      route,
    };
    let page: null | UIPageSurfaceInput = null;
    let adapterNodeCount = 0;

    this.adapters.forEach((adapter) => {
      const result = adapter.collect(adapterContext);
      if (!page && result.page) {
        page = result.page;
      }
      result.overlays?.forEach((overlay) => {
        if (overlayMap.has(overlay.key)) {
          return;
        }
        overlayMap.set(overlay.key, cloneOverlay(overlay));
      });
      result.nodes?.forEach((node) => {
        const key = nodeKey(node);
        const previous = nodeMap.get(key);
        if (!previous) {
          nodeMap.set(key, cloneNode(node));
          adapterNodeCount += 1;
          return;
        }
        const previousPriority = previous.priority ?? 0;
        const nextPriority = node.priority ?? 0;
        if (nextPriority > previousPriority) {
          nodeMap.set(key, cloneNode(node));
        }
      });
    });

    const shouldRunFullDomFallback =
      input.forceDomFallback === true ||
      mode === 'full' ||
      this.includeDomFallbackInCompact ||
      nodeMap.size === 0;
    const domMode: DOMScanMode = shouldRunFullDomFallback
      ? 'full'
      : 'surfaces-only';
    const domScanResult = this.scanner.scan(
      {
        activeSurfaceId: input.activeSurfaceId ?? null,
        document: this.document,
        mode,
        root: this.root,
      },
      domMode,
    );

    domScanResult.overlays.forEach((overlay) => {
      if (overlayMap.has(overlay.key)) {
        return;
      }
      overlayMap.set(overlay.key, cloneOverlay(overlay));
    });

    if (domMode === 'full') {
      domScanResult.nodes.forEach((node) => {
        const key = nodeKey(node);
        if (nodeMap.has(key)) {
          return;
        }
        nodeMap.set(key, cloneNode(node));
      });
    }

    const nodes = sortNodes(Array.from(nodeMap.values()));
    const graph: UIGraph = this.createGraph(
      mode,
      nodes,
      adapterNodeCount,
      domScanResult,
      start,
      shouldRunFullDomFallback,
    );
    return {
      graph,
      overlays: Array.from(overlayMap.values()),
      page: page ?? createPageFallback(route, this.document),
    };
  }

  getAdapters(): UIComponentAdapter[] {
    return [...this.adapters];
  }

  registerAdapter(adapter: UIComponentAdapter): void {
    this.adapters = sortAdapters(
      this.adapters.filter((item) => item.id !== adapter.id).concat(adapter),
    );
  }

  unregisterAdapter(adapterId: string): boolean {
    const before = this.adapters.length;
    this.adapters = this.adapters.filter((adapter) => adapter.id !== adapterId);
    return this.adapters.length !== before;
  }

  private createGraph(
    mode: UIGraph['mode'],
    nodes: UIGraphNode[],
    adapterNodeCount: number,
    domScanResult: DOMScanResult,
    startTime: number,
    usedDomFallback: boolean,
  ): UIGraph {
    return {
      builtAt: Date.now(),
      mode,
      nodes,
      stats: {
        adapterNodeCount,
        buildDurationMs: nowInMs() - startTime,
        domFallbackNodeCount: domScanResult.nodes.length,
        domScanDurationMs: domScanResult.durationMs,
        scannedElements: domScanResult.scannedElements,
        totalNodeCount: nodes.length,
        truncated: domScanResult.truncated,
        usedDomFallback,
      },
    };
  }
}
