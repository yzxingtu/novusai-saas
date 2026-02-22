/**
 * 租户端插件管理 API
 */
import type { PluginFrontendConfig } from '../admin/plugins';
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const PREFIX = '/tenant/plugins';

/** 获取当前租户可用的已启用插件前端配置（路由+菜单+i18n） */
export async function getTenantPluginFrontendConfigApi(
  options?: ApiRequestOptions,
): Promise<PluginFrontendConfig[]> {
  return requestClient.get<PluginFrontendConfig[]>(
    `${PREFIX}/frontend-config`,
    options,
  );
}
