import type { LocatorResolver, LocatorResolverOptions } from './locator-resolver';
import type { UISurfaceKind } from './types';

export type UIActionType = 'ui_click' | 'ui_open_surface';

export type { UISurfaceKind };

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

export interface UIStateSnapshot {
  activeSurfaceId: null | string;
  pageKey: string;
  surfaces: UISurfaceSummary[];
  uiEpoch: number;
}
