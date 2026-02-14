<script lang="ts" setup>
/**
 * 平台插件管理页面 — 卡片式布局
 */
import type { PluginInfo } from '#/api/admin/plugins';
import type { UploadRequestOption } from 'ant-design-vue/es/vc-upload/interface';

defineOptions({ name: 'AdminPluginList' });

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Dropdown,
  Empty,
  Input,
  Menu,
  message,
  Modal,
  Segmented,
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
} from '#/api/admin/plugins';
import { $t } from '#/locales';

import {
  getPluginTypeColor,
  getPluginTypeText,
  getStatusColor,
  getStatusText,
} from './data';
import PluginConfigDrawer from './PluginConfigDrawer.vue';

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
  { value: 'all', label: $t('admin.plugin.filterAll') },
  { value: 'enabled', label: $t('admin.plugin.status_options.enabled') },
  { value: 'installed', label: $t('admin.plugin.status_options.installed') },
  { value: 'disabled', label: $t('admin.plugin.status_options.disabled') },
  { value: 'error', label: $t('admin.plugin.status_options.error') },
]);

const typeFilters = computed(() => [
  { value: 'all', label: $t('admin.plugin.filterAll') },
  { value: 'adapter', label: $t('admin.plugin.type_options.adapter') },
  { value: 'tool', label: $t('admin.plugin.type_options.tool') },
  { value: 'hook', label: $t('admin.plugin.type_options.hook') },
  { value: 'api', label: $t('admin.plugin.type_options.api') },
  { value: 'skill', label: $t('admin.plugin.type_options.skill') },
  { value: 'composite', label: $t('admin.plugin.type_options.composite') },
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
    await uploadPluginApi(file);
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
    :title="$t('admin.plugin.pageTitle')"
    :description="$t('admin.plugin.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 统计摘要 -->
    <Spin :spinning="loading">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card
          v-for="stat in summaryCards"
          :key="stat.key"
          :body-style="{ padding: '16px' }"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-10 items-center justify-center rounded-lg"
              :class="stat.bgClass"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="size-5"
                :class="stat.iconClass"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-lg font-semibold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- 顶部工具栏 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-1 flex-wrap items-center gap-3">
        <Input.Search
          v-model:value="searchKeyword"
          :placeholder="$t('admin.plugin.placeholder.searchName')"
          allow-clear
          class="w-64"
        />
        <Segmented
          v-model:value="filterStatus"
          :options="statusFilters"
          size="small"
        />
        <Segmented
          v-model:value="filterType"
          :options="typeFilters"
          size="small"
        />
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.plugin.totalPlugins', { count: filteredPlugins.length }) }}
        </span>
        <Dropdown>
          <Button type="primary">
            <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
            {{ $t('admin.plugin.install') }}
          </Button>
          <template #overlay>
            <Menu>
              <Menu.Item key="entry" @click="onInstallByEntryClick">
                <div class="flex items-center gap-2">
                  <IconifyIcon icon="lucide:terminal" class="size-4" />
                  {{ $t('admin.plugin.installByEntry') }}
                </div>
              </Menu.Item>
              <Menu.Item key="upload" @click="onUploadClick">
                <div class="flex items-center gap-2">
                  <IconifyIcon icon="lucide:upload" class="size-4" />
                  {{ $t('admin.plugin.uploadZip') }}
                </div>
              </Menu.Item>
            </Menu>
          </template>
        </Dropdown>
      </div>
    </div>

    <!-- 插件卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="filteredPlugins.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="plugin in filteredPlugins"
          :key="plugin.id"
          class="group relative cursor-pointer rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/40 hover:shadow-md"
          :class="{ 'opacity-60': isProcessing(plugin.id) }"
          @click="onDetail(plugin)"
        >
          <!-- 系统插件角标 -->
          <Tooltip
            v-if="plugin.is_system"
            :title="$t('admin.plugin.messages.systemPluginTip')"
          >
            <div class="absolute right-3 top-3">
              <IconifyIcon
                icon="lucide:shield-check"
                class="size-4 text-warning"
              />
            </div>
          </Tooltip>

          <!-- 头部：图标 + 名称 + 版本 -->
          <div class="mb-3 flex items-start gap-3">
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-xl transition-colors"
              :class="plugin.status === 'enabled' ? 'bg-primary/10' : plugin.status === 'error' ? 'bg-destructive/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="plugin.icon || 'lucide:plug'"
                class="size-5"
                :class="plugin.status === 'enabled' ? 'text-primary' : plugin.status === 'error' ? 'text-destructive' : 'text-muted-foreground'"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-semibold text-foreground">
                  {{ plugin.display_name }}
                </span>
                <span class="shrink-0 text-xs text-muted-foreground">
                  v{{ plugin.version }}
                </span>
              </div>
              <div
                v-if="plugin.author"
                class="mt-0.5 text-xs text-muted-foreground"
              >
                {{ $t('admin.plugin.by') }} {{ plugin.author }}
              </div>
            </div>
          </div>

          <!-- 描述 -->
          <p
            class="mb-3 line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-muted-foreground"
          >
            {{ plugin.description || '-' }}
          </p>

          <!-- 底部：标签 + 开关 + 操作 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <Tag :color="getPluginTypeColor(plugin.plugin_type)" class="!m-0">
                {{ getPluginTypeText(plugin.plugin_type) }}
              </Tag>
              <Tag
                v-if="plugin.plugin_type === 'skill' || plugin.plugin_type === 'composite'"
                color="cyan"
                class="!m-0"
                style="font-size: 10px; line-height: 14px; padding: 0 4px;"
              >
                <IconifyIcon icon="lucide:sparkles" class="mr-0.5 inline size-2.5" />
                {{ $t('admin.plugin.providesSkill') }}
              </Tag>
              <Tag v-if="plugin.status === 'error'" :color="getStatusColor(plugin.status)" class="!m-0">
                {{ getStatusText(plugin.status) }}
              </Tag>
            </div>
            <div class="flex items-center gap-1" @click.stop>
              <!-- 启用/禁用开关 -->
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
              <!-- 操作按钮 -->
              <div class="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <template v-if="!plugin.is_system">
                  <Tooltip :title="$t('admin.plugin.upgrade')">
                    <Button
                      v-access:code="['plugin:upgrade']"
                      type="text"
                      size="small"
                      :loading="isProcessing(plugin.id)"
                      class="!size-7 !p-0"
                      @click="onUpgrade(plugin)"
                    >
                      <IconifyIcon
                        icon="lucide:arrow-up-circle"
                        class="size-3.5 text-primary"
                      />
                    </Button>
                  </Tooltip>
                  <Tooltip :title="$t('admin.plugin.uninstall')">
                    <Button
                      v-access:code="['plugin:uninstall']"
                      type="text"
                      size="small"
                      danger
                      :loading="isProcessing(plugin.id)"
                      class="!size-7 !p-0"
                      @click="onUninstall(plugin)"
                    >
                      <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                    </Button>
                  </Tooltip>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading" class="flex items-center justify-center py-20">
        <Empty
          :description="
            searchKeyword || filterType !== 'all' || filterStatus !== 'all'
              ? $t('admin.plugin.noResults')
              : $t('admin.plugin.noPlugins')
          "
        />
      </div>
    </Spin>

    <!-- 通过入口安装弹窗（替代 h() 渲染） -->
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

    <!-- 上传插件弹窗 -->
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
          <div class="flex flex-col items-center gap-4 py-8">
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
            <div class="flex flex-col items-center gap-1">
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
