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
  | 'pagination'
  | 'popover'
  | 'radio'
  | 'select'
  | 'tab'
  | 'table'
  | 'textarea';

export type UINodeSource = 'adapter' | 'dom-fallback';

export type UISurfaceKind =
  | 'drawer'
  | 'dropdown'
  | 'modal'
  | 'page'
  | 'popover';

export type UIEpochReason =
  | 'graph_rebuilt'
  | 'manual'
  | 'route_changed'
  | 'surface_closed'
  | 'surface_opened'
  | 'surface_synced';

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

export interface UIRuntimeIncrementalNodePatch {
  added?: UIGraphNode[];
  removedIds?: string[];
  removedLocators?: string[];
  updated?: Array<Partial<UIGraphNode> & Pick<UIGraphNode, 'id'>>;
}

export interface UIRuntimeIncrementalInput {
  mode?: UIGraphBuildMode;
  nodePatch?: UIRuntimeIncrementalNodePatch;
  route?: null | UIRouteLike;
  surfaceSync?: UISurfaceSyncInput;
}

export interface UIRuntimeState {
  surface_stack: UISurface[];
  ui_epoch: number;
  ui_graph: UIGraph;
}

export interface UIRuntimeSnapshot extends UIRuntimeState {
  active_surface: null | UISurface;
}

export interface UIRuntimeSurfaceNodeRead {
  children_count?: number;
  content?: string;
  disabled: boolean;
  interactable: boolean;
  kind: UINodeKind;
  label?: string;
  locator: string;
  node_id: string;
  role?: string;
  surface_id?: string;
  text?: string;
  title?: string;
}

export interface UIRuntimeSurfaceReadResult {
  active_surface: null | UISurface;
  mode: UIGraphBuildMode;
  nodes: UIRuntimeSurfaceNodeRead[];
  surface: null | UISurface;
  surface_stack: UISurface[];
  ui_epoch: number;
}
