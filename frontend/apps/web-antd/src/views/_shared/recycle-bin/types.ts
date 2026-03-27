import type { VbenFormSchema } from '#/adapter/form';
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
  RecycleBinModuleSummary,
  TriggerRecycleBinCleanupParams,
} from '#/api/shared/recycle-bin';

export interface RecycleBinColumnPreset {
  field: string;
  title: string;
  width?: number;
  minWidth?: number;
  align?: 'center' | 'left' | 'right';
  slot?: string;
}

export interface RecycleBinSortOption {
  label: string;
  value: string;
}

export interface RecycleBinModuleAdapter {
  columns?: () => RecycleBinColumnPreset[];
  defaultSort?: string;
  searchSchema?: () => VbenFormSchema[];
  sortOptions?: () => RecycleBinSortOption[];
}

export interface RecycleBinPageApi {
  clearModule: (module: string) => Promise<undefined | { count?: number }>;
  getList: (
    module: string,
    params?: Record<string, unknown>,
  ) => Promise<{ items: RecycleBinItem[]; total: number }>;
  getModules: () => Promise<Record<string, RecycleBinModuleMeta>>;
  getSummary: () => Promise<RecycleBinModuleSummary[]>;
  permanentDelete: (module: string, id: number) => Promise<unknown>;
  restore: (module: string, id: number) => Promise<unknown>;
  triggerCleanup?: (
    params?: TriggerRecycleBinCleanupParams,
  ) => Promise<unknown>;
}
