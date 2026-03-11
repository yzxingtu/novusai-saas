/**
 * Storage migration plugin shared API / 存储迁移插件共享 API
 *
 * Only contains types/functions used by main system components
 * (e.g., StorageSwitchImpactModal). Plugin-specific API functions
 * are in backend/plugins/storage-migration/frontend/src/api.ts.
 *
 * 仅包含主系统组件使用的类型/函数（如 StorageSwitchImpactModal）。
 * 插件专属 API 函数位于 backend/plugins/storage-migration/frontend/src/api.ts。
 */
import { requestClient } from '#/utils/request';

const PLUGIN_API_BASE = '/admin/plugins/storage-migration/api';

/** Storage switch impact analysis / 存储切换影响分析 */
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
    file_count: number;
    size_bytes: number;
    tenant_id: null | number;
  }>;
  scope: string;
}

/** Impact analysis before switching storage / 切换存储前的影响分析 */
export function getImpactAnalysisApi(
  sourceDriver: string,
  targetDriver: string,
  scope = 'all',
) {
  return requestClient.get<ImpactAnalysis>(
    `${PLUGIN_API_BASE}/impact-analysis`,
    {
      params: {
        source_driver: sourceDriver,
        target_driver: targetDriver,
        scope,
      },
    },
  );
}
