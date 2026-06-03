import type { MenuOverrideItem, PluginInfo } from '#/api/admin/plugin';

import { message, Modal } from 'ant-design-vue';

import {
  disablePluginApi,
  enablePluginApi,
  forceCleanupPluginApi,
  installPluginDependenciesApi,
  refreshPluginSchedulesApi,
  repairPluginApi,
  uninstallPluginApi,
  uninstallPluginDependenciesApi,
} from '#/api/admin/plugin';
import { handleDisableError } from '#/composables/use-plugin-admin-refresh';
import { $t } from '#/locales';
import { usePluginInstallProgressStore } from '#/store';

import { hasPluginScheduledTasks } from './plugin-recovery';

type MutationRunner = (
  pluginId: number,
  run: () => Promise<void>,
) => Promise<void>;

interface UsePluginAdminActionsOptions {
  afterMutation?: () => Promise<void> | void;
  afterUninstall?: () => Promise<void> | void;
  withProcessing?: MutationRunner;
}

function resolveErrorMessage(error: unknown, fallbackKey: string): string {
  return (error as { message?: string })?.message || $t(fallbackKey);
}

export function usePluginAdminActions(
  options: UsePluginAdminActionsOptions = {},
) {
  const progressStore = usePluginInstallProgressStore();

  async function runMutation(pluginId: number, run: () => Promise<void>) {
    if (options.withProcessing) {
      await options.withProcessing(pluginId, run);
      return;
    }
    await run();
  }

  async function afterMutation() {
    await options.afterMutation?.();
  }

  async function afterUninstall() {
    if (options.afterUninstall) {
      await options.afterUninstall();
      return;
    }
    await afterMutation();
  }

  function onEnable(plugin: PluginInfo, menuOverrides?: MenuOverrideItem[]) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.enable', { name: plugin.display_name }),
      onOk() {
        progressStore.reset();
        progressStore.startOperation(plugin.display_name, 'enable');
        return runMutation(plugin.id, async () => {
          await enablePluginApi(plugin.id, menuOverrides);
          progressStore.markComplete();
          message.success($t('admin.plugin.messages.enableSuccess'));
          await afterMutation();
        }).catch((error: unknown) => {
          progressStore.markError(
            resolveErrorMessage(error, 'admin.plugin.messages.enableFailed'),
          );
        });
      },
    });
  }

  function onDisable(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.disable', { name: plugin.display_name }),
      onOk: () => {
        progressStore.reset();
        progressStore.startOperation(plugin.display_name, 'disable');
        return runMutation(plugin.id, async () => {
          try {
            await disablePluginApi(plugin.id);
          } catch (error: unknown) {
            handleDisableError(error, plugin.display_name, () =>
              runMutation(plugin.id, async () => {
                await disablePluginApi(plugin.id, true);
                message.success($t('admin.plugin.messages.disableSuccess'));
                await afterMutation();
              }),
            );
            return;
          }
          progressStore.markComplete();
          message.success($t('admin.plugin.messages.disableSuccess'));
          await afterMutation();
        });
      },
    });
  }

  function onUninstall(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.uninstall', {
        name: plugin.display_name,
      }),
      okType: 'danger',
      onOk() {
        progressStore.reset();
        progressStore.startOperation(plugin.display_name, 'uninstall');
        void runMutation(plugin.id, async () => {
          await uninstallPluginApi(plugin.id);
          progressStore.markComplete();
          message.success($t('admin.plugin.messages.uninstallSuccess'));
          await afterUninstall();
        }).catch((error: unknown) => {
          progressStore.markError(
            resolveErrorMessage(error, 'admin.plugin.messages.uninstallFailed'),
          );
        });
      },
    });
  }

  function onRepair(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.repair', { name: plugin.display_name }),
      onOk() {
        progressStore.reset();
        progressStore.startOperation(plugin.display_name, 'enable');
        void runMutation(plugin.id, async () => {
          await repairPluginApi(plugin.id);
          progressStore.markComplete();
          message.success($t('admin.plugin.messages.repairSuccess'));
          await afterMutation();
        }).catch((error: unknown) => {
          progressStore.markError(
            resolveErrorMessage(error, 'admin.plugin.messages.repairFailed'),
          );
        });
      },
    });
  }

  function onRefreshSchedules(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.refreshSchedules', {
        name: plugin.display_name,
      }),
      onOk: () =>
        runMutation(plugin.id, async () => {
          await refreshPluginSchedulesApi(plugin.id);
          message.success($t('admin.plugin.messages.refreshSchedulesSuccess'));
          await afterMutation();
        }).catch(() => {
          message.error($t('admin.plugin.messages.refreshSchedulesFailed'));
        }),
    });
  }

  function onInstallDependencies(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.installDependencies', {
        name: plugin.display_name,
      }),
      onOk: () =>
        runMutation(plugin.id, async () => {
          await installPluginDependenciesApi(plugin.id, {
            python: true,
          });
          message.success($t('admin.plugin.messages.installDepsSuccess'));
          await afterMutation();
        }),
    });
  }

  function onUninstallDependencies(plugin: PluginInfo) {
    if (plugin.status === 'enabled') {
      message.warning($t('admin.plugin.messages.disableBeforeUninstallDeps'));
      return;
    }

    Modal.confirm({
      title: $t('admin.plugin.confirm.uninstallDependencies', {
        name: plugin.display_name,
      }),
      content: $t('admin.plugin.confirm.uninstallDependenciesContent'),
      okType: 'danger',
      onOk: () =>
        runMutation(plugin.id, async () => {
          try {
            await uninstallPluginDependenciesApi(plugin.id, {
              python: true,
            });
            message.success($t('admin.plugin.messages.uninstallDepsSuccess'));
            await afterMutation();
          } catch (error: unknown) {
            type AxiosLike = {
              message?: string;
              response?: { data?: { message?: string } };
            };
            const apiMsg =
              (error as AxiosLike)?.response?.data?.message ??
              (error as AxiosLike)?.message ??
              '';
            message.error(
              apiMsg || $t('admin.plugin.messages.uninstallDepsFailed'),
            );
          }
        }),
    });
  }

  function onForceCleanup(plugin: PluginInfo) {
    Modal.confirm({
      title: $t('admin.plugin.confirm.forceCleanup', {
        name: plugin.display_name,
      }),
      okType: 'danger',
      onOk: () =>
        runMutation(plugin.id, async () => {
          await forceCleanupPluginApi(plugin.id);
          message.success($t('admin.plugin.messages.forceCleanupSuccess'));
          await afterUninstall();
        }),
    });
  }

  return {
    hasPluginScheduledTasks,
    onDisable,
    onEnable,
    onForceCleanup,
    onInstallDependencies,
    onRefreshSchedules,
    onRepair,
    onUninstallDependencies,
    onUninstall,
  };
}
