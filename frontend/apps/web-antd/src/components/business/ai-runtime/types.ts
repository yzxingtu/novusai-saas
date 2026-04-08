export type UIGraphBuildMode = 'compact' | 'full';

export type UINodeKind =
  | 'button'
  | 'checkbox'
  | 'drawer'
  | 'dropdown-item'
  | 'input'
  | 'link'
  | 'menu-item'
  | 'modal'
  | 'popover'
  | 'radio'
  | 'select'
  | 'tab'
  | 'table'
  | 'textarea';

export type UINodeSource = 'adapter' | 'dom-fallback';

export type UISurfaceKind = 'page' | 'drawer' | 'modal' | 'dropdown' | 'popover';

export type UIEpochReason =
  | 'graph_rebuilt'
  | 'route_changed'
  | 'surface_closed'
  | 'surface_opened'
  | 'surface_synced'
  | 'manual';

export type DOMScanMode = 'full' | 'surfaces-only';

export interface UIRouteLike {
  fullPath: string;
  name?: null | string;
  meta?: Record<string, unknown> & {
    title?: string;
  };
}

export interface UIGraphNode {
  id: string;
  kind: UINodeKind;
  locator: string;
  source: UINodeSource;
  adapterId?: string;
  disabled: boolean;
  visible: boolean;
  label?: string;
  priority?: number;
  surfaceId?: string;
  metadata?: Record<string, unknown>;
  extensions?: Record<string, unknown>;
}

export interface UIGraphStats {
  adapterNodeCount: number;
  buildDurationMs: number;
  domFallbackNodeCount: number;
  domScanDurationMs: number;
  scannedElements: number;
  totalNodeCount: number;
  truncated: boolean;
  usedDomFallback: boolean;
}

export interface UIGraph {
  builtAt: number;
  mode: UIGraphBuildMode;
  nodes: UIGraphNode[];
  stats: UIGraphStats;
}

export interface UIPageSurfaceInput {
  key: string;
  pageKey: string;
  title: string;
  routePath?: string;
  metadata?: Record<string, unknown>;
}

export interface UIOverlaySurfaceInput {
  key: string;
  kind: Exclude<UISurfaceKind, 'page'>;
  title: string;
  parentKey?: string;
  metadata?: Record<string, unknown>;
}

export interface UISurface {
  id: string;
  key: string;
  kind: UISurfaceKind;
  title: string;
  openedAt: number;
  updatedAt: number;
  pageKey?: string;
  routePath?: string;
  parentId?: string;
  metadata?: Record<string, unknown>;
  extensions?: Record<string, unknown>;
}

export interface UISurfaceSyncInput {
  page: UIPageSurfaceInput;
  overlays: UIOverlaySurfaceInput[];
}

export interface UISurfaceDelta {
  added: UISurface[];
  changed: boolean;
  removed: UISurface[];
  updated: UISurface[];
}

export interface UIEpochRecord {
  epoch: number;
  reason: UIEpochReason;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

export interface UIAdapterContext {
  root: ParentNode;
  document: Document;
  mode: UIGraphBuildMode;
  now: number;
  activeSurfaceId: null | string;
  route: null | UIRouteLike;
}

export interface UIAdapterResult {
  nodes?: UIGraphNode[];
  overlays?: UIOverlaySurfaceInput[];
  page?: null | UIPageSurfaceInput;
}

export interface UIComponentAdapter {
  id: string;
  priority: number;
  collect: (context: UIAdapterContext) => UIAdapterResult;
}

export interface DOMScannerOptions {
  maxDepth: number;
  maxNodes: number;
  textMaxLength: number;
  visibleOnly: boolean;
}

export interface DOMScanInput {
  activeSurfaceId?: null | string;
  document: Document;
  mode: UIGraphBuildMode;
  root: ParentNode;
}

export interface DOMScanResult {
  durationMs: number;
  mode: DOMScanMode;
  nodes: UIGraphNode[];
  overlays: UIOverlaySurfaceInput[];
  scannedElements: number;
  truncated: boolean;
}

export interface UIGraphBuildInput {
  activeSurfaceId?: null | string;
  forceDomFallback?: boolean;
  mode?: UIGraphBuildMode;
  route?: null | UIRouteLike;
}

export interface UIGraphBuildResult {
  graph: UIGraph;
  overlays: UIOverlaySurfaceInput[];
  page: UIPageSurfaceInput;
}

export interface UIGraphBuilderOptions {
  adapters?: UIComponentAdapter[];
  document?: Document;
  domScannerOptions?: Partial<DOMScannerOptions>;
  includeDomFallbackInCompact?: boolean;
  root?: ParentNode;
}

export interface UIRuntimeOptions {
  adapters?: UIComponentAdapter[];
  document?: Document;
  domScannerOptions?: Partial<DOMScannerOptions>;
  getRoute?: () => null | UIRouteLike;
  includeDomFallbackInCompact?: boolean;
  root?: ParentNode;
  route?: null | UIRouteLike;
}

export interface UIRuntimeRebuildInput {
  forceDomFallback?: boolean;
  mode?: UIGraphBuildMode;
  route?: null | UIRouteLike;
}

export interface UIRuntimeState {
  surface_stack: UISurface[];
  ui_epoch: number;
  ui_graph: UIGraph;
}

export interface UIRuntimeSnapshot extends UIRuntimeState {
  active_surface: null | UISurface;
}
