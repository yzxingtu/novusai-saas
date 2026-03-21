<script lang="ts" setup>
import type { MenuDeclItem } from './modules/PluginMenuConfigModal.vue';

/**
 * Platform plugin management page — card layout
 * 平台插件管理页面 — 卡片式布局
 */
import type { MenuOverrideItem, PluginInfo } from '#/api/admin/plugin';

import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Input,
  message,
  Modal,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  disablePluginApi,
  enablePluginApi,
  forceCleanupPluginApi,
  getPluginListApi,
  installPluginDependenciesApi,
  repairPluginApi,
  uninstallPluginApi,
  uninstallPluginDependenciesApi,
  updatePluginMenuConfigApi,
} from '#/api/admin/plugin';
import {
  usePageAIContext,
  usePageAIOperations,
} from '#/composables/use-page-ai-registration';
import {
  createOpenPageOperation,
  createOpenRecordPageOperation,
  createKeywordSearchPageOperation,
  createRefreshPageOperation,
} from '#/composables/use-page-ai-operation-helpers';
import {
  handleDisableError as _handleDisableError,
  refreshAdminMenusAndPluginRoutes as _refreshRoutes,
} from '#/composables/use-plugin-admin-refresh';
import { $t } from '#/locales';
import { usePluginInstallProgressStore } from '#/store';
import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import {
  derivePluginType,
  getStatusText,
  getTypeColor,
  getTypeIcon,
  getTypeText,
  PLUGIN_TYPES,
} from './data';
import PluginConfigDrawer from './modules/PluginConfigDrawer.vue';
import PluginInstallProgress from './modules/PluginInstallProgress.vue';
import PluginInstallWizard from './modules/PluginInstallWizard.vue';
import PluginMenuConfigModal from './modules/PluginMenuConfigModal.vue';

defineOptions({ name: 'AdminPluginList' });

const router = useRouter();
const progressStore = usePluginInstallProgressStore();
const plugins = ref<PluginInfo[]>([]);
const loading = ref(false);
const searchKeyword = ref('');
const filterType = ref('all');
const filterStatus = ref('all');
const processingIds = ref<Set<number>>(new Set());
const installWizardRef = ref<InstanceType<typeof PluginInstallWizard>>();
const configDrawerRef = ref<InstanceType<typeof PluginConfigDrawer>>();
const menuConfigModalRef = ref<InstanceType<typeof PluginMenuConfigModal>>();
let pendingEnablePlugin: null | PluginInfo = null;

const statusFilters = computed(() => [
  {
    value: 'all',
    label: $t('admin.plugin.type_options.all'),
    icon: 'lucide:layers',
  },
  {
    value: 'enabled',
    label: $t('admin.plugin.status_options.enabled'),
    icon: 'lucide:check-circle',
  },
  {
    value: 'installed',
    label: $t('admin.plugin.status_options.installed'),
    icon: 'lucide:download',
  },
  {
    value: 'disabled',
    label: $t('admin.plugin.status_options.disabled'),
    icon: 'lucide:pause-circle',
  },
  {
    value: 'error',
    label: $t('admin.plugin.status_options.error'),
    icon: 'lucide:alert-circle',
  },
]);

const typeFilters = computed(() => [
  {
    value: 'all',
    label: $t('admin.plugin.type_options.all'),
    icon: 'lucide:grid-2x2',
  },
  ...PLUGIN_TYPES.map((t) => ({
    value: t,
    label: getTypeText(t),
    icon: getTypeIcon(t),
  })),
]);

const filteredPlugins = computed(() => {
  let result = plugins.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (p) =>
        p.display_name.toLowerCase().includes(kw) ||
        p.name.toLowerCase().includes(kw) ||
        (p.description && p.description.toLowerCase().includes(kw)),
    );
  }
  if (filterType.value !== 'all') {
    result = result.filter(
      (p) => derivePluginType(p.manifest) === filterType.value,
    );
  }
  if (filterStatus.value !== 'all') {
    result = result.filter((p) => p.status === filterStatus.value);
  }
  return result;
});

const stats = computed(() => {
  const all = plugins.value;
  return {
    total: all.length,
    enabled: all.filter((p) => p.status === 'enabled').length,
    disabled: all.filter(
      (p) => p.status === 'disabled' || p.status === 'installed',
    ).length,
    error: all.filter((p) => p.status === 'error').length,
  };
});

const summaryCards = computed(() => [
  {
    key: 'total',
    label: $t('admin.plugin.overview.total'),
    value: stats.value.total,
    icon: 'lucide:blocks',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'enabled',
    label: $t('admin.plugin.overview.enabled'),
    value: stats.value.enabled,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
  {
    key: 'disabled',
    label: $t('admin.plugin.overview.disabled'),
    value: stats.value.disabled,
    icon: 'lucide:pause-circle',
    bgClass: 'bg-accent',
    iconClass: 'text-muted-foreground',
  },
  {
    key: 'error',
    label: $t('admin.plugin.overview.error'),
    value: stats.value.error,
    icon: 'lucide:alert-circle',
    bgClass: 'bg-destructive/10',
    iconClass: 'text-destructive',
  },
]);

async function loadPlugins() {
  loading.value = true;
  try {
    const res = (await getPluginListApi({
      'page[size]': 200,
      sort: '-created_at',
    })) as Record<string, unknown>;
    plugins.value = (res?.items as PluginInfo[]) || [];
  } catch {
    plugins.value = [];
  } finally {
    loading.value = false;
  }
}

async function refreshAdminMenusAndPluginRoutes() {
  await _refreshRoutes(router);
}

onMounted(() => {
  loadPlugins();
  progressStore.startListening();
});

function isProcessing(id: number): boolean {
  return processingIds.value.has(id);
}

async function withProcessing(id: number, fn: () => Promise<void>) {
  if (processingIds.value.has(id)) return;
  processingIds.value.add(id);
  try {
    await fn();
  } finally {
    processingIds.value.delete(id);
  }
}

function onDetail(plugin: PluginInfo) {
  openPluginConfigDrawer(plugin);
}

function findPluginById(pluginId: number): null | PluginInfo {
  return plugins.value.find((plugin) => plugin.id === pluginId) ?? null;
}

function getPluginMenuOverrides(plugin: PluginInfo) {
  return ((plugin.config || {}) as Record<string, unknown>).menu_overrides as
    | Record<string, { parent?: string; tenant_parent?: string }>
    | undefined;
}

function openInstallWizard() {
  installWizardRef.value?.open();
}

function openPluginConfigDrawer(plugin: PluginInfo) {
  configDrawerRef.value?.open(plugin);
}

function openPluginMenuConfig(plugin: PluginInfo) {
  const menus = getPluginMenus(plugin);
  if (menus.length === 0) {
    return {
      success: false,
      message: $t('admin.plugin.menu_config.no_menus'),
    };
  }

  menuConfigUpdatePlugin = plugin;
  menuConfigModalRef.value?.open(menus, getPluginMenuOverrides(plugin));
}

function getPluginMenus(plugin: PluginInfo): MenuDeclItem[] {
  const manifest = plugin.manifest || {};
  const extensions = (manifest.extensions || {}) as Record<string, unknown>;
  const frontend = (extensions.frontend || {}) as Record<string, unknown>;
  const pages = (frontend.pages || []) as Array<
    MenuDeclItem & { menu?: MenuDeclItem; path?: string; component?: string }
  >;
  return pages
    .filter((page) => page.menu)
    .map((page) => ({
      name: page.name,
      title: page.menu?.title || page.title,
      parent: page.menu?.parent,
      icon: page.menu?.icon || page.icon,
      scope: page.scope,
      hidden: page.menu?.hidden ?? false,
    }))
    .filter((m) => !m.hidden);
}

function onEnable(plugin: PluginInfo) {
  const menus = getPluginMenus(plugin);
  if (menus.length > 0) {
    // Has menu extensions → let admin choose mount position first / 有菜单扩展 → 先让管理员选择挂载位置
    pendingEnablePlugin = plugin;
    menuConfigModalRef.value?.open(menus, getPluginMenuOverrides(plugin));
  } else {
    doEnable(plugin);
  }
}

function doEnable(plugin: PluginInfo, menuOverrides?: MenuOverrideItem[]) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.enable', { name: plugin.display_name }),
    onOk() {
      // Don't return Promise, let Modal close immediately, progress tracked by progressStore (Socket.IO) / 不 return Promise，让 Modal 立即关闭，进度由 progressStore (Socket.IO) 跟踪
      progressStore.reset();
      progressStore.startOperation(plugin.display_name, 'enable');
      withProcessing(plugin.id, async () => {
        await enablePluginApi(plugin.id, menuOverrides);
        // SIO fallback: if no Socket.IO events arrived, mark complete via HTTP success / SIO 兜底：无 Socket.IO 事件时按 HTTP 成功标记完成
        progressStore.markComplete();
        message.success($t('admin.plugin.messages.enableSuccess'));
        await loadPlugins();
        await refreshAdminMenusAndPluginRoutes();
      }).catch((error: unknown) => {
        // SIO fallback: if no Socket.IO error event arrived, show error from HTTP / SIO 兜底：无 Socket.IO 错误事件时展示 HTTP 错误
        const msg =
          (error as { message?: string })?.message ||
          $t('admin.plugin.messages.enableFailed');
        progressStore.markError(msg);
      });
    },
  });
}

let menuConfigUpdatePlugin: null | PluginInfo = null;

async function onMenuConfigConfirm(overrides: MenuOverrideItem[]) {
  if (pendingEnablePlugin) {
    const plugin = pendingEnablePlugin;
    pendingEnablePlugin = null;
    doEnable(plugin, overrides);
  } else if (menuConfigUpdatePlugin) {
    const plugin = menuConfigUpdatePlugin;
    menuConfigUpdatePlugin = null;
    await updatePluginMenuConfigApi(plugin.id, overrides);
    message.success($t('admin.plugin.menu_config.save_success'));
    await loadPlugins();
    await refreshAdminMenusAndPluginRoutes();
  }
}

function onMenuConfigCancel() {
  pendingEnablePlugin = null;
  menuConfigUpdatePlugin = null;
}

function onMenuLocation(plugin: PluginInfo) {
  openPluginMenuConfig(plugin);
}

function onDisable(plugin: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.disable', { name: plugin.display_name }),
    onOk: () => {
      progressStore.reset();
      progressStore.startOperation(plugin.display_name, 'disable');
      return withProcessing(plugin.id, async () => {
        try {
          await disablePluginApi(plugin.id);
        } catch (error: unknown) {
          _handleDisableError(error, plugin.display_name, () =>
            withProcessing(plugin.id, async () => {
              await disablePluginApi(plugin.id, true);
              message.success($t('admin.plugin.messages.disableSuccess'));
              await loadPlugins();
              await refreshAdminMenusAndPluginRoutes();
            }),
          );
          return;
        }
        progressStore.markComplete();
        message.success($t('admin.plugin.messages.disableSuccess'));
        await loadPlugins();
        await refreshAdminMenusAndPluginRoutes();
      });
    },
  });
}

function onUninstall(plugin: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.uninstall', { name: plugin.display_name }),
    okType: 'danger',
    onOk() {
      // Don't return Promise, let Modal close immediately / 不 return Promise，让 Modal 立即关闭
      progressStore.reset();
      progressStore.startOperation(plugin.display_name, 'uninstall');
      withProcessing(plugin.id, async () => {
        await uninstallPluginApi(plugin.id);
        progressStore.markComplete();
        message.success($t('admin.plugin.messages.uninstallSuccess'));
        await loadPlugins();
        await refreshAdminMenusAndPluginRoutes();
      }).catch((error: unknown) => {
        const msg =
          (error as { message?: string })?.message ||
          $t('admin.plugin.messages.uninstallFailed');
        progressStore.markError(msg);
      });
    },
  });
}

function onInstallDependencies(plugin: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.installDependencies', {
      name: plugin.display_name,
    }),
    onOk: () =>
      withProcessing(plugin.id, async () => {
        await installPluginDependenciesApi(plugin.id, {
          python: true,
        });
        message.success($t('admin.plugin.messages.installDepsSuccess'));
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
      withProcessing(plugin.id, async () => {
        try {
          await uninstallPluginDependenciesApi(plugin.id, {
            python: true,
          });
          message.success($t('admin.plugin.messages.uninstallDepsSuccess'));
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

function onRepair(plugin: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.repair', { name: plugin.display_name }),
    onOk() {
      progressStore.reset();
      progressStore.startOperation(plugin.display_name, 'enable');
      withProcessing(plugin.id, async () => {
        await repairPluginApi(plugin.id);
        progressStore.markComplete();
        message.success($t('admin.plugin.messages.repairSuccess'));
        await loadPlugins();
        await refreshAdminMenusAndPluginRoutes();
      }).catch((error: unknown) => {
        const msg =
          (error as { message?: string })?.message ||
          $t('admin.plugin.messages.repairFailed');
        progressStore.markError(msg);
      });
    },
  });
}

function onForceCleanup(plugin: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.confirm.forceCleanup', {
      name: plugin.display_name,
    }),
    okType: 'danger',
    onOk: () =>
      withProcessing(plugin.id, async () => {
        await forceCleanupPluginApi(plugin.id);
        message.success($t('admin.plugin.messages.forceCleanupSuccess'));
        await loadPlugins();
        await refreshAdminMenusAndPluginRoutes();
      }),
  });
}

function onUploadClick() {
  openInstallWizard();
}

async function onWizardInstalled() {
  progressStore.reset();
  progressStore.show();
  await loadPlugins();
}

function getPluginMetadataIcon(plugin: PluginInfo) {
  return resolvePluginMetadataIcon(plugin.name, plugin.icon, {
    endpoint: 'admin',
  });
}

function isDependencyInstalled(plugin: PluginInfo): boolean {
  return plugin.dependency_status?.overall === 'installed';
}

function getDependencyStatusColor(plugin: PluginInfo): string {
  return isDependencyInstalled(plugin) ? 'success' : 'error';
}

function getDependencyStatusText(plugin: PluginInfo): string {
  return isDependencyInstalled(plugin)
    ? $t('admin.plugin.dependency.installed')
    : $t('admin.plugin.dependency.missing');
}

usePageAIContext({
  resource: '/admin/plugins',
  data: () => ({
    total_plugins: plugins.value.length,
    enabled_plugins: plugins.value.filter((p) => p.status === 'enabled').length,
  }),
});

usePageAIOperations({
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      name: 'refresh_plugins',
      action: loadPlugins,
      description: 'Reload the plugin list',
    }),
    createKeywordSearchPageOperation({
      label: $t('shared.pageOperation.searchPlugins'),
      description: 'Search plugins by keyword',
      keywordDescription: 'Plugin name keyword',
      setKeyword: (keyword) => {
        searchKeyword.value = keyword;
      },
    }),
    createOpenPageOperation({
      name: 'open_plugin_install_wizard',
      label: $t('admin.plugin.upload'),
      description:
        'Open the plugin install wizard / 打开插件安装向导',
      open: async () => {
        openInstallWizard();
      },
      successMessage: () => $t('shared.pageOperation.msg.createFormOpenedEmpty'),
    }),
    createOpenRecordPageOperation({
      name: 'open_plugin_config',
      label: $t('admin.plugin.action.detail'),
      description:
        'Open the plugin configuration drawer by plugin ID / 按插件 ID 打开插件配置抽屉',
      params: {
        id: {
          type: 'number',
          description: 'Plugin ID / 插件 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findPluginById(params.id),
      resolveRecordId: (params) => params.id,
      open: async (plugin) => {
        openPluginConfigDrawer(plugin);
      },
    }),
    createOpenRecordPageOperation({
      name: 'open_plugin_menu_config',
      label: $t('admin.plugin.menu_config.title'),
      description:
        'Open the plugin menu location modal by plugin ID / 按插件 ID 打开插件菜单挂载配置弹窗',
      params: {
        id: {
          type: 'number',
          description: 'Plugin ID / 插件 ID',
          required: true,
        },
      },
      normalizeParams: (params) => ({
        id: Number(params.id ?? 0),
      }),
      resolveRecord: (params) => findPluginById(params.id),
      resolveRecordId: (params) => params.id,
      open: async (plugin) => openPluginMenuConfig(plugin),
    }),
  ],
});

onUnmounted(() => {
  progressStore.stopListening();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-5">
    <!-- ===== 顶部 Hero 区域 ===== -->
    <div
      class="relative !h-auto min-h-[180px] overflow-hidden rounded-2xl bg-gradient-to-br from-primary/5 via-background to-primary/5 p-6"
    >
      <div
        class="relative z-10 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start"
      >
        <div class="min-w-0">
          <h1 class="text-xl font-bold text-foreground">
            {{ $t('admin.plugin.title') }}
          </h1>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('admin.plugin.heroSubtitle') }}
          </p>
          <!-- 统计摘要（内联） -->
          <div class="mt-4 flex flex-wrap items-center gap-5">
            <div
              v-for="stat in summaryCards"
              :key="stat.key"
              class="flex items-center gap-2"
            >
              <div
                class="flex size-8 items-center justify-center rounded-lg"
                :class="stat.bgClass"
              >
                <IconifyIcon
                  :icon="stat.icon"
                  class="size-4"
                  :class="stat.iconClass"
                />
              </div>
              <div class="flex flex-col">
                <span class="text-lg font-bold leading-tight text-foreground">{{
                  stat.value
                }}</span>
                <span class="text-[11px] leading-tight text-muted-foreground">{{
                  stat.label
                }}</span>
              </div>
            </div>
          </div>
        </div>
        <!-- 操作按钮组 -->
        <div class="flex items-center gap-2 lg:justify-end">
          <Button
            size="large"
            class="!rounded-xl"
            @click="router.push('/admin/plugins/marketplace')"
          >
            <IconifyIcon icon="lucide:store" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.marketplaceBtn') }}
          </Button>
          <Button
            type="primary"
            size="large"
            class="!rounded-xl !px-5 !shadow-lg !shadow-primary/20"
            @click="onUploadClick"
          >
            <IconifyIcon icon="lucide:upload" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.upload') }}
          </Button>
        </div>
      </div>
      <!-- 装饰背景 -->
      <div
        class="absolute -right-12 -top-12 size-48 rounded-full bg-primary/5 blur-3xl"
      ></div>
      <div
        class="absolute -bottom-8 -left-8 size-32 rounded-full bg-primary/10 blur-2xl"
      ></div>
    </div>

    <PluginInstallWizard
      ref="installWizardRef"
      @installed="onWizardInstalled"
    />
    <PluginConfigDrawer ref="configDrawerRef" @saved="loadPlugins" />

    <!-- ===== 筛选工具栏 ===== -->
    <div class="flex flex-col gap-3">
      <!-- 搜索 + 状态筛选 -->
      <div class="flex flex-wrap items-center gap-3">
        <Input.Search
          v-model:value="searchKeyword"
          :placeholder="$t('admin.plugin.placeholder.searchName')"
          allow-clear
          class="!w-56 !rounded-lg"
        />
        <div class="h-6 w-px bg-border/50"></div>
        <div class="flex items-center gap-1 rounded-xl bg-muted/50 p-1">
          <button
            v-for="opt in statusFilters"
            :key="opt.value"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200"
            :class="
              filterStatus === opt.value
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            "
            @click="filterStatus = opt.value"
          >
            <IconifyIcon :icon="opt.icon" class="size-3.5" />
            <span>{{ opt.label }}</span>
          </button>
        </div>
        <span class="ml-auto text-xs text-muted-foreground">
          {{ filteredPlugins.length }} / {{ plugins.length }}
        </span>
      </div>
      <!-- 类型筛选 -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="opt in typeFilters"
          :key="opt.value"
          class="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all duration-200"
          :class="
            filterType === opt.value
              ? 'border-primary/30 bg-primary/10 text-primary'
              : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
          "
          @click="filterType = opt.value"
        >
          <IconifyIcon :icon="opt.icon" class="size-3" />
          <span>{{ opt.label }}</span>
        </button>
      </div>
    </div>

    <!-- ===== 插件卡片网格 ===== -->
    <div
      v-if="loading"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
    >
      <div
        v-for="n in 8"
        :key="n"
        class="overflow-hidden rounded-2xl border border-border/60 bg-card p-5"
      >
        <div class="h-1 w-full rounded bg-muted/70"></div>
        <div class="mt-4 flex items-start gap-3.5">
          <div class="size-12 rounded-xl bg-muted"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 w-2/3 rounded bg-muted"></div>
            <div class="h-3 w-1/2 rounded bg-muted/70"></div>
          </div>
        </div>
        <div class="mt-5 space-y-2">
          <div class="h-3 w-full rounded bg-muted/70"></div>
          <div class="h-3 w-5/6 rounded bg-muted/70"></div>
        </div>
        <div class="mt-5 flex gap-2">
          <div class="h-6 w-14 rounded bg-muted/70"></div>
          <div class="h-6 w-24 rounded bg-muted/70"></div>
        </div>
      </div>
    </div>

    <div
      v-else-if="filteredPlugins.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
    >
      <div
        v-for="plugin in filteredPlugins"
        :key="plugin.id"
        class="group relative cursor-pointer overflow-hidden rounded-2xl border border-border/60 bg-card transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
        :class="{ 'pointer-events-none opacity-50': isProcessing(plugin.id) }"
        @click="onDetail(plugin)"
      >
        <!-- 顶部状态条 -->
        <div
          class="h-1 w-full"
          :class="
            plugin.status === 'enabled'
              ? 'bg-gradient-to-r from-emerald-400 to-emerald-500'
              : plugin.status === 'error'
                ? 'bg-gradient-to-r from-red-400 to-red-500'
                : 'bg-gradient-to-r from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600'
          "
        ></div>

        <div class="p-5">
          <!-- 头部：图标 + 名称 + 版本 -->
          <div class="mb-3.5 flex items-start gap-3.5">
            <div
              class="flex size-12 shrink-0 items-center justify-center rounded-xl shadow-sm transition-all duration-200 group-hover:shadow-md"
              :class="
                plugin.status === 'enabled'
                  ? 'bg-gradient-to-br from-primary/15 to-primary/5'
                  : plugin.status === 'error'
                    ? 'bg-gradient-to-br from-destructive/15 to-destructive/5'
                    : 'bg-gradient-to-br from-primary/10 to-primary/5'
              "
            >
              <img
                v-if="getPluginMetadataIcon(plugin).kind === 'image'"
                :src="getPluginMetadataIcon(plugin).src"
                class="size-5.5 rounded"
                :alt="plugin.display_name"
              />
              <IconifyIcon
                v-else
                :icon="getPluginMetadataIcon(plugin).icon"
                class="size-5.5"
                :class="
                  plugin.status === 'enabled'
                    ? 'text-primary'
                    : plugin.status === 'error'
                      ? 'text-destructive'
                      : 'text-primary/60'
                "
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span
                  class="truncate text-[15px] font-semibold leading-snug text-foreground"
                >
                  {{ plugin.display_name }}
                </span>
              </div>
              <div
                class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground"
              >
                <span class="font-mono">v{{ plugin.version }}</span>
                <template v-if="plugin.author">
                  <span class="text-border">·</span>
                  <span>{{ plugin.author }}</span>
                </template>
              </div>
            </div>
          </div>

          <!-- 描述 -->
          <p
            class="mb-4 line-clamp-2 min-h-[2.25rem] text-[13px] leading-relaxed text-muted-foreground/80"
          >
            {{ plugin.description || '-' }}
          </p>

          <!-- 标签行 -->
          <div class="mb-4 flex flex-wrap items-center gap-1.5">
            <Tag
              :color="getTypeColor(derivePluginType(plugin.manifest))"
              class="!m-0 !rounded-md !border-0 !text-[11px]"
            >
              {{ getTypeText(derivePluginType(plugin.manifest)) }}
            </Tag>
            <Tag
              v-if="plugin.scope && plugin.scope !== 'all_tenants'"
              :color="getScopeColor(plugin.scope)"
              class="!m-0 !rounded-md !border-0 !text-[11px]"
            >
              {{ getScopeText(plugin.scope) }}
            </Tag>
            <Tag
              :color="getDependencyStatusColor(plugin)"
              class="!m-0 !rounded-md !border-0 !text-[11px]"
            >
              {{ getDependencyStatusText(plugin) }}
            </Tag>
            <Tag
              v-if="plugin.status === 'error'"
              color="error"
              class="!m-0 !rounded-md !border-0 !text-[11px]"
            >
              {{ getStatusText(plugin.status) }}
            </Tag>
          </div>

          <!-- 底部操作栏 -->
          <div
            class="flex items-center justify-between border-t border-border/40 pt-3.5"
            @click.stop
          >
            <!-- 开关 -->
            <Switch
              :checked="plugin.status === 'enabled'"
              :checked-children="$t('admin.plugin.status_options.enabled')"
              :un-checked-children="$t('admin.plugin.status_options.disabled')"
              :disabled="plugin.status === 'error' || isProcessing(plugin.id)"
              size="small"
              @change="
                () =>
                  plugin.status === 'enabled'
                    ? onDisable(plugin)
                    : onEnable(plugin)
              "
            />
            <!-- 操作按钮组 -->
            <div class="flex items-center gap-0.5">
              <Tooltip
                v-if="
                  plugin.status !== 'error' && getPluginMenus(plugin).length > 0
                "
                :title="$t('admin.plugin.menu_config.menu_location')"
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                  @click="onMenuLocation(plugin)"
                >
                  <IconifyIcon icon="lucide:layout-list" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip :title="$t('admin.plugin.action.settings')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                  @click="onDetail(plugin)"
                >
                  <IconifyIcon icon="lucide:settings" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip :title="$t('admin.plugin.action.installDependencies')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                  @click="onInstallDependencies(plugin)"
                >
                  <IconifyIcon icon="lucide:package-plus" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip
                :title="
                  plugin.status === 'enabled'
                    ? $t('admin.plugin.messages.disableBeforeUninstallDeps')
                    : $t('admin.plugin.action.uninstallDependencies')
                "
              >
                <button
                  :disabled="plugin.status === 'enabled'"
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-warning/10 hover:text-warning disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted-foreground"
                  @click="onUninstallDependencies(plugin)"
                >
                  <IconifyIcon icon="lucide:package-minus" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip
                v-if="
                  plugin.status === 'error' &&
                  !plugin.error_message?.includes('missing from disk')
                "
                :title="$t('admin.plugin.action.repair')"
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-warning/10 hover:text-warning"
                  @click="onRepair(plugin)"
                >
                  <IconifyIcon icon="lucide:wrench" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip
                v-if="
                  plugin.status === 'error' &&
                  plugin.error_message?.includes('missing from disk')
                "
                :title="$t('admin.plugin.action.forceCleanup')"
              >
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  @click="onForceCleanup(plugin)"
                >
                  <IconifyIcon icon="lucide:eraser" class="size-4" />
                </button>
              </Tooltip>
              <Tooltip v-else :title="$t('admin.plugin.action.uninstall')">
                <button
                  class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  @click="onUninstall(plugin)"
                >
                  <IconifyIcon icon="lucide:trash-2" class="size-4" />
                </button>
              </Tooltip>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="flex flex-col items-center justify-center gap-4 py-24">
      <div
        class="flex size-20 items-center justify-center rounded-2xl bg-muted"
      >
        <IconifyIcon
          icon="lucide:puzzle"
          class="size-10 text-muted-foreground/50"
        />
      </div>
      <div class="text-center">
        <p class="text-sm font-medium text-foreground">
          {{ $t('admin.plugin.emptyList') }}
        </p>
      </div>
    </div>

    <!-- 安装/卸载进度抽屉 -->
    <PluginInstallProgress />

    <!-- 插件菜单位置配置弹窗 -->
    <PluginMenuConfigModal
      ref="menuConfigModalRef"
      @confirm="onMenuConfigConfirm"
      @cancel="onMenuConfigCancel"
    />
  </Page>
</template>
