/**
 * Storage Migration Plugin - Shared API
 *
 * Only contains types/functions used by main system components
 * (e.g., StorageSwitchImpactModal). Plugin-specific API functions
 * are in backend/plugins/storage-migration/frontend/src/api.ts.
 */
import { requestClient } from '#/utils/request';

const PLUGIN_API_BASE = '/admin/plugins/storage-migration/api';

export interface ImpactAnalysis {
  source_driver: string;
  target_driver: string;
  source_available: boolean;
  target_available: boolean;
  total_files: number;
  total_size_bytes: number;
  private_files: number;
  private_size_bytes: number;
  public_files: number;
  public_size_bytes: number;
  tenant_breakdown: Array<{
    tenant_id: number | null;
    file_count: number;
    size_bytes: number;
  }>;
  scope: string;
}

/** Impact analysis before switching storage */
export function getImpactAnalysisApi(
  sourceDriver: string,
  targetDriver: string,
  scope = 'all',
) {
  return requestClient.get<ImpactAnalysis>(
    `${PLUGIN_API_BASE}/impact-analysis`,
    { params: { source_driver: sourceDriver, target_driver: targetDriver, scope } },
  );
}
