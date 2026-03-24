/**
 * Shared utilities for plugin admin operations:
 * - refreshAdminMenusAndPluginRoutes: refresh menus and routes after plugin state changes
 * - handleDisableError: classify and display disable API error with proper Modal feedback
 *
 * 插件管理端共用工具：
 * - refreshAdminMenusAndPluginRoutes: 插件状态变更后刷新菜单和路由
 * - handleDisableError: 分类并展示禁用 API 错误（依赖/存储驱动/其他）
 */

import type { Router } from 'vue-router';

import { useAccessStore, useUserStore } from '@vben/stores';

import { Modal } from 'ant-design-vue';

import { refreshPluginSlots } from '#/composables/use-plugin-frontend-init';
import { $t } from '#/locales';
import { generateAccess } from '#/router/access';
import { accessRoutes } from '#/router/routes';
import { showRequestError } from '#/utils/error-helpers';

export async function refreshAdminMenusAndPluginRoutes(router: Router) {
  const accessStore = useAccessStore();
  const userStore = useUserStore();

  try {
    await refreshPluginSlots('/admin', router, { reloadAssets: true });
  } catch (error) {
    console.warn('[PluginRefresh] Failed to refresh plugin slots:', error);
  }
  try {
    const userRoles = userStore.userInfo?.roles ?? [];
    const { accessibleMenus, accessibleRoutes: routes } = await generateAccess(
      {
        roles: userRoles,
        router,
        routes: accessRoutes,
      },
      'admin',
    );
    accessStore.setAccessMenus(accessibleMenus);
    accessStore.setAccessRoutes(routes);
    accessStore.setIsAccessChecked(true);
  } catch (error) {
    console.warn('[PluginRefresh] Failed to refresh admin menu/routes:', error);
    accessStore.setIsAccessChecked(false);
  }
}

/**
 * Classify and handle disable API errors with proper Modal feedback.
 * Centralizes the duplicate error-handling logic from index.vue and PluginConfigDrawer.vue.
 *
 * 分类并处理禁用 API 错误，统一 index.vue 与 PluginConfigDrawer.vue 中的重复逻辑。
 *
 * @param error - The caught error from disablePluginApi
 * @param pluginName - Display name for Modal titles
 * @param onForceDisable - Callback when user confirms force-disable
 */
export function handleDisableError(
  error: unknown,
  pluginName: string,
  onForceDisable: () => Promise<void> | void,
): void {
  type AxiosLike = {
    message?: string;
    response?: { data?: { message?: string } };
  };
  const apiMsg =
    (error as AxiosLike)?.response?.data?.message ??
    (error as AxiosLike)?.message ??
    '';

  if (apiMsg.includes('depend on it') || apiMsg.includes('plugins [')) {
    const match = apiMsg.match(/plugins \[([^\]]+)\]/);
    const deps = match ? match[1] : apiMsg;
    Modal.warning({
      title: $t('admin.plugin.confirm.dependency_error_title', {
        name: pluginName,
      }),
      content: $t('admin.plugin.confirm.dependency_error_content', { deps }),
    });
    return;
  }

  if (apiMsg.includes('storage driver') || apiMsg.includes('used by tenant')) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.force_disable_title', {
        name: pluginName,
      }),
      content: $t('admin.plugin.confirm.force_disable_content'),
      okType: 'danger',
      okText: $t('admin.plugin.confirm.force_disable_ok'),
      onOk: onForceDisable,
    });
    return;
  }

  showRequestError(error, 'admin.common.operationFailed');
}
