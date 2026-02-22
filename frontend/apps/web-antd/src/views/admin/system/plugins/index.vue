<script lang="ts" setup>
/**
 * 平台插件管理页面 — 卡片式布局
 */
import type { PluginInfo } from '#/api/admin/plugins';
import type { UploadRequestOption } from 'ant-design-vue/es/vc-upload/interface';

defineOptions({ name: 'AdminPluginList' });

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { useAccessStore } from '@vben/stores';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Dropdown,
  Input,
  Menu,
  message,
  Modal,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import {
  disablePluginApi,
  enablePluginApi,
  getPluginListApi,
  installPluginApi,
  uninstallPluginApi,
  upgradePluginApi,
  uploadPluginApi,
  type UploadConflictResponse,
} from '#/api/admin/plugins';
import { $t } from '#/locales';

import {
  getPluginTypeColor,
  getPluginTypeText,
  getStatusText,
} from './data';
import PluginConfigDrawer from './PluginConfigDrawer.vue';

const accessStore = useAccessStore();

const configDrawerRef = ref<InstanceType<typeof PluginConfigDrawer>>();
const plugins = ref<PluginInfo[]>([]);
const loading = ref(false);
const uploadModalVisible = ref(false);
const uploading = ref(false);
const searchKeyword = ref('');
const filterType = ref('all');
const filterStatus = ref('all');
const installEntryVisible = ref(false);
const installEntryPoint = ref('');
const processingIds = ref<Set<number>>(new Set());

const statusFilters = computed(() => [
  { value: 'all', label: $t('admin.plugin.filterAll'), icon: 'lucide:layers' },
  { value: 'enabled', label: $t('admin.plugin.status_options.enabled'), icon: 'lucide:check-circle' },
  { value: 'installed', label: $t('admin.plugin.status_options.installed'), icon: 'lucide:download' },
  { value: 'disabled', label: $t('admin.plugin.status_options.disabled'), icon: 'lucide:pause-circle' },
  { value: 'error', label: $t('admin.plugin.status_options.error'), icon: 'lucide:alert-circle' },
]);

const typeFilters = computed(() => [
  { value: 'all', label: $t('admin.plugin.filterAll'), icon: 'lucide:grid-2x2' },
  { value: 'adapter', label: $t('admin.plugin.type_options.adapter'), icon: 'lucide:cpu' },
  { value: 'tool', label: $t('admin.plugin.type_options.tool'), icon: 'lucide:wrench' },
  { value: 'hook', label: $t('admin.plugin.type_options.hook'), icon: 'lucide:webhook' },
  { value: 'api', label: $t('admin.plugin.type_options.api'), icon: 'lucide:route' },
  { value: 'skill', label: $t('admin.plugin.type_options.skill'), icon: 'lucide:sparkles' },
  { value: 'composite', label: $t('admin.plugin.type_options.composite'), icon: 'lucide:blocks' },
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
    result = result.filter((p) => p.plugin_type === filterType.value);
  }
  if (filterStatus.value !== 'all') {
    result = result.filter((p) => p.status === filterStatus.value);
  }
  return result;
});

// ========== 统计摘要 ==========

interface PluginStats {
  total: number;
  enabled: number;
  disabled: number;
  error: number;
  system: number;
}

const stats = computed<PluginStats>(() => {
  const all = plugins.value;
  return {
    total: all.length,
    enabled: all.filter((p) => p.status === 'enabled').length,
    disabled: all.filter((p) => p.status === 'disabled' || p.status === 'installed').length,
    error: all.filter((p) => p.status === 'error').length,
    system: all.filter((p) => p.is_system).length,
  };
});

const summaryCards = computed(() => [
  {
    key: 'total',
    label: $t('admin.plugin.summary.total'),
    value: stats.value.total,
    icon: 'lucide:blocks',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'enabled',
    label: $t('admin.plugin.summary.enabled'),
    value: stats.value.enabled,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
  {
    key: 'disabled',
    label: $t('admin.plugin.summary.disabled'),
    value: stats.value.disabled,
    icon: 'lucide:pause-circle',
    bgClass: 'bg-accent',
    iconClass: 'text-muted-foreground',
  },
  {
    key: 'error',
    label: $t('admin.plugin.summary.error'),
    value: stats.value.error,
    icon: 'lucide:alert-circle',
    bgClass: 'bg-destructive/10',
    iconClass: 'text-destructive',
  },
]);

async function loadPlugins() {
  loading.value = true;
  try {
    const res = await getPluginListApi({ 'page[size]': 200, sort: '-created_at' });
    plugins.value = res.items || [];
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

function onDetail(row: PluginInfo) {
  configDrawerRef.value?.open(row);
}

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

function onEnable(row: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.messages.confirmEnable'),
    onOk: () => withProcessing(row.id, async () => {
      await enablePluginApi(row.id);
      message.success($t('admin.plugin.messages.enableSuccess'));
      accessStore.setIsAccessChecked(false);
      await loadPlugins();
    }),
  });
}

function onDisable(row: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.messages.confirmDisable'),
    onOk: () => withProcessing(row.id, async () => {
      await disablePluginApi(row.id);
      message.success($t('admin.plugin.messages.disableSuccess'));
      accessStore.setIsAccessChecked(false);
      await loadPlugins();
    }),
  });
}

function onUninstall(row: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.messages.confirmUninstall'),
    okType: 'danger',
    onOk: () => withProcessing(row.id, async () => {
      await uninstallPluginApi(row.id);
      message.success($t('admin.plugin.messages.uninstallSuccess'));
      accessStore.setIsAccessChecked(false);
      await loadPlugins();
    }),
  });
}

function onUpgrade(row: PluginInfo) {
  Modal.confirm({
    title: $t('admin.plugin.messages.confirmUpgrade'),
    onOk: () => withProcessing(row.id, async () => {
      await upgradePluginApi(row.id);
      message.success($t('admin.plugin.messages.upgradeSuccess'));
      await loadPlugins();
    }),
  });
}

function onInstallByEntryClick() {
  installEntryPoint.value = '';
  installEntryVisible.value = true;
}

async function onInstallByEntryConfirm() {
  const ep = installEntryPoint.value.trim();
  if (!ep) return;
  try {
    await installPluginApi({ entry_point: ep });
    message.success($t('admin.plugin.messages.installSuccess'));
    installEntryVisible.value = false;
    await loadPlugins();
  } catch {
    // handled by interceptor
  }
}

function onUploadClick() {
  uploadModalVisible.value = true;
}

async function handleCustomUpload(options: UploadRequestOption) {
  const file = options.file as File;
  uploading.value = true;
  try {
    const res = await uploadPluginApi(file);
    if ('conflict' in res && (res as UploadConflictResponse).conflict) {
      const conflictRes = res as UploadConflictResponse;
      Modal.confirm({
        title: $t('admin.plugin.messages.uploadConflict'),
        content: $t('admin.plugin.messages.uploadConflictDesc', {
          name: conflictRes.plugin_name,
          oldVersion: conflictRes.existing_version ?? '-',
          newVersion: conflictRes.new_version,
        }),
        okText: $t('admin.plugin.messages.overwrite'),
        cancelText: $t('common.cancel'),
        onOk: async () => {
          uploading.value = true;
          try {
            await uploadPluginApi(file, true);
            message.success($t('admin.plugin.messages.upgradeSuccess'));
            uploadModalVisible.value = false;
            await loadPlugins();
          } finally {
            uploading.value = false;
          }
        },
      });
      options.onSuccess?.({});
      return;
    }
    message.success($t('admin.plugin.messages.installSuccess'));
    uploadModalVisible.value = false;
    await loadPlugins();
    options.onSuccess?.({});
  } catch {
    options.onError?.(new Error('upload failed'));
  } finally {
    uploading.value = false;
  }
}

onMounted(loadPlugins);
</script>

<template>
  <Page
    auto-content-height
    content-class="flex flex-col gap-5"
  >
    <!-- ===== 顶部 Hero 区域 ===== -->
    <div class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/5 via-background to-primary/3 p-6">
      <div class="relative z-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="text-xl font-bold text-foreground">{{ $t('admin.plugin.pageTitle') }}</h1>
          <p class="mt-1 text-sm text-muted-foreground">{{ $t('admin.plugin.pageDesc') }}</p>
          <!-- 统计摘要（内联） -->
          <div class="mt-4 flex flex-wrap items-center gap-5">
            <div v-for="stat in summaryCards" :key="stat.key" class="flex items-center gap-2">
              <div class="flex size-8 items-center justify-center rounded-lg" :class="stat.bgClass">
                <IconifyIcon :icon="stat.icon" class="size-4" :class="stat.iconClass" />
              </div>
              <div class="flex flex-col">
                <span class="text-lg font-bold leading-tight text-foreground">{{ stat.value }}</span>
                <span class="text-[11px] leading-tight text-muted-foreground">{{ stat.label }}</span>
              </div>
            </div>
          </div>
        </div>
        <!-- 操作按钮组 -->
        <div class="flex items-center gap-2">
          <Button
            size="large"
            class="!rounded-xl"
            @click="$router.push('/admin/system/marketplace')"
          >
            <IconifyIcon icon="lucide:store" class="mr-1.5 size-4" />
            {{ $t('admin.system.marketplace.goToMarketplace') }}
          </Button>
          <Dropdown>
          <Button type="primary" size="large" class="!rounded-xl !px-5 !shadow-lg !shadow-primary/20">
            <IconifyIcon icon="lucide:plus" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.install') }}
          </Button>
          <template #overlay>
            <Menu>
              <Menu.Item key="entry" @click="onInstallByEntryClick">
                <div class="flex items-center gap-2.5 py-0.5">
                  <IconifyIcon icon="lucide:terminal" class="size-4 text-muted-foreground" />
                  <span>{{ $t('admin.plugin.installByEntry') }}</span>
                </div>
              </Menu.Item>
              <Menu.Item key="upload" @click="onUploadClick">
                <div class="flex items-center gap-2.5 py-0.5">
                  <IconifyIcon icon="lucide:upload" class="size-4 text-muted-foreground" />
                  <span>{{ $t('admin.plugin.uploadZip') }}</span>
                </div>
              </Menu.Item>
            </Menu>
          </template>
        </Dropdown>
        </div>
      </div>
      <!-- 装饰背景 -->
      <div class="absolute -right-12 -top-12 size-48 rounded-full bg-primary/5 blur-3xl" />
      <div class="absolute -bottom-8 -left-8 size-32 rounded-full bg-primary/3 blur-2xl" />
    </div>

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
        <div class="h-6 w-px bg-border/50" />
        <div class="flex items-center gap-1 rounded-xl bg-muted/50 p-1">
          <button
            v-for="opt in statusFilters"
            :key="opt.value"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200"
            :class="filterStatus === opt.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'"
            @click="filterStatus = opt.value"
          >
            <IconifyIcon :icon="opt.icon" class="size-3.5" />
            <span>{{ opt.label }}</span>
          </button>
        </div>
        <span class="ml-auto text-xs text-muted-foreground">
          {{ $t('admin.plugin.totalPlugins', { count: filteredPlugins.length }) }}
        </span>
      </div>
      <!-- 类型筛选 -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="opt in typeFilters"
          :key="opt.value"
          class="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all duration-200"
          :class="filterType === opt.value
            ? 'border-primary/30 bg-primary/10 text-primary'
            : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'"
          @click="filterType = opt.value"
        >
          <IconifyIcon :icon="opt.icon" class="size-3" />
          <span>{{ opt.label }}</span>
        </button>
      </div>
    </div>

    <!-- ===== 插件卡片网格 ===== -->
    <Spin :spinning="loading">
      <div
        v-if="filteredPlugins.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
      >
        <div
          v-for="plugin in filteredPlugins"
          :key="plugin.id"
          class="plugin-card group relative cursor-pointer overflow-hidden rounded-2xl border border-border/60 bg-card transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
          :class="{ 'pointer-events-none opacity-50': isProcessing(plugin.id) }"
          @click="onDetail(plugin)"
        >
          <!-- 顶部状态条 -->
          <div
            class="h-1 w-full"
            :class="
              plugin.status === 'enabled' ? 'bg-gradient-to-r from-emerald-400 to-emerald-500'
              : plugin.status === 'error' ? 'bg-gradient-to-r from-red-400 to-red-500'
              : 'bg-gradient-to-r from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600'
            "
          />

          <div class="p-5">
            <!-- 头部：图标 + 名称 + 版本 + 系统角标 -->
            <div class="mb-3.5 flex items-start gap-3.5">
              <div
                class="flex size-12 shrink-0 items-center justify-center rounded-xl shadow-sm transition-all duration-200 group-hover:shadow-md"
                :class="
                  plugin.status === 'enabled' ? 'bg-gradient-to-br from-primary/15 to-primary/5'
                  : plugin.status === 'error' ? 'bg-gradient-to-br from-destructive/15 to-destructive/5'
                  : 'bg-muted'
                "
              >
                <IconifyIcon
                  :icon="plugin.icon || 'lucide:plug'"
                  class="size-5.5"
                  :class="
                    plugin.status === 'enabled' ? 'text-primary'
                    : plugin.status === 'error' ? 'text-destructive'
                    : 'text-muted-foreground'
                  "
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="truncate text-[15px] font-semibold leading-snug text-foreground">
                    {{ plugin.display_name }}
                  </span>
                  <Tooltip v-if="plugin.is_system" :title="$t('admin.plugin.messages.systemPluginTip')">
                    <IconifyIcon icon="lucide:shield-check" class="size-3.5 shrink-0 text-warning" />
                  </Tooltip>
                </div>
                <div class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <span class="font-mono">v{{ plugin.version }}</span>
                  <template v-if="plugin.author">
                    <span class="text-border">·</span>
                    <span>{{ plugin.author }}</span>
                  </template>
                </div>
              </div>
            </div>

            <!-- 描述 -->
            <p class="mb-4 line-clamp-2 min-h-[2.25rem] text-[13px] leading-relaxed text-muted-foreground/80">
              {{ plugin.description || '-' }}
            </p>

            <!-- 标签行 -->
            <div class="mb-4 flex flex-wrap items-center gap-1.5">
              <Tag :color="getPluginTypeColor(plugin.plugin_type)" class="!m-0 !rounded-md !border-0 !text-[11px]">
                {{ getPluginTypeText(plugin.plugin_type) }}
              </Tag>
              <Tag
                v-if="plugin.scope && plugin.scope !== 'all_tenants'"
                :color="plugin.scope === 'platform_only' ? 'orange' : plugin.scope === 'global' ? 'green' : 'purple'"
                class="!m-0 !rounded-md !border-0 !text-[11px]"
              >
                {{ $t(`admin.plugin.scope_options.${plugin.scope}`) }}
              </Tag>
              <Tag
                v-if="plugin.plugin_type === 'skill' || plugin.plugin_type === 'composite'"
                color="cyan"
                class="!m-0 !rounded-md !border-0 !text-[11px]"
              >
                <IconifyIcon icon="lucide:sparkles" class="mr-0.5 inline size-2.5" />
                {{ $t('admin.plugin.providesSkill') }}
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
            <div class="flex items-center justify-between border-t border-border/40 pt-3.5" @click.stop>
              <!-- 开关 -->
              <Tooltip v-if="plugin.is_system" :title="$t('admin.plugin.messages.systemPluginTip')">
                <Switch
                  :checked="plugin.status === 'enabled'"
                  :checked-children="$t('admin.common.enabled')"
                  :un-checked-children="$t('admin.common.disabled')"
                  size="small"
                  disabled
                />
              </Tooltip>
              <Switch
                v-else
                v-access:code="['plugin:enable']"
                :checked="plugin.status === 'enabled'"
                :checked-children="$t('admin.common.enabled')"
                :un-checked-children="$t('admin.common.disabled')"
                :disabled="plugin.status === 'error' || isProcessing(plugin.id)"
                size="small"
                @change="() => plugin.status === 'enabled' ? onDisable(plugin) : onEnable(plugin)"
              />
              <!-- 操作按钮组 -->
              <div class="flex items-center gap-0.5 opacity-0 transition-all duration-200 group-hover:opacity-100">
                <template v-if="!plugin.is_system">
                  <Tooltip :title="$t('admin.plugin.upgrade')">
                    <button
                      v-access:code="['plugin:upgrade']"
                      class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                      @click="onUpgrade(plugin)"
                    >
                      <IconifyIcon icon="lucide:arrow-up-circle" class="size-4" />
                    </button>
                  </Tooltip>
                  <Tooltip :title="$t('admin.plugin.uninstall')">
                    <button
                      v-access:code="['plugin:uninstall']"
                      class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      @click="onUninstall(plugin)"
                    >
                      <IconifyIcon icon="lucide:trash-2" class="size-4" />
                    </button>
                  </Tooltip>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading" class="flex flex-col items-center justify-center gap-4 py-24">
        <div class="flex size-20 items-center justify-center rounded-2xl bg-muted">
          <IconifyIcon icon="lucide:puzzle" class="size-10 text-muted-foreground/50" />
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-foreground">
            {{
              searchKeyword || filterType !== 'all' || filterStatus !== 'all'
                ? $t('admin.plugin.noResults')
                : $t('admin.plugin.noPlugins')
            }}
          </p>
          <p v-if="!searchKeyword && filterType === 'all' && filterStatus === 'all'" class="mt-1 text-xs text-muted-foreground">
            {{ $t('admin.plugin.noPluginsDesc') }}
          </p>
        </div>
      </div>
    </Spin>

    <!-- ===== 通过入口安装弹窗 ===== -->
    <Modal
      v-model:open="installEntryVisible"
      :title="$t('admin.plugin.installByEntry')"
      :ok-text="$t('admin.plugin.install')"
      :destroy-on-close="true"
      @ok="onInstallByEntryConfirm"
    >
      <div class="py-4">
        <Input
          v-model:value="installEntryPoint"
          :placeholder="$t('admin.plugin.placeholder.inputEntryPoint')"
          allow-clear
          @press-enter="onInstallByEntryConfirm"
        />
      </div>
    </Modal>

    <!-- ===== 上传插件弹窗 ===== -->
    <Modal
      v-model:open="uploadModalVisible"
      :title="$t('admin.plugin.uploadZip')"
      :footer="null"
      :destroy-on-close="true"
      width="520px"
    >
      <div class="py-2">
        <Upload.Dragger
          :custom-request="handleCustomUpload"
          accept=".zip,.nap"
          :multiple="false"
          :show-upload-list="false"
          :disabled="uploading"
        >
          <div class="flex flex-col items-center gap-4 py-10">
            <div
              class="flex size-16 items-center justify-center rounded-2xl shadow-lg"
              :style="{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%)' }"
            >
              <IconifyIcon
                :icon="uploading ? 'lucide:loader-2' : 'lucide:cloud-upload'"
                class="size-8 text-white"
                :class="{ 'animate-spin': uploading }"
              />
            </div>
            <div class="flex flex-col items-center gap-1.5">
              <span class="text-sm font-semibold text-foreground">
                {{ uploading ? $t('admin.plugin.messages.uploading') : $t('admin.plugin.uploadDragText') }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{ $t('admin.plugin.uploadDesc') }}
              </span>
            </div>
          </div>
        </Upload.Dragger>
      </div>
    </Modal>

    <PluginConfigDrawer ref="configDrawerRef" @saved="loadPlugins" />
  </Page>
</template>
