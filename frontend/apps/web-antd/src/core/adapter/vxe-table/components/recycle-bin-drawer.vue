<script lang="ts" setup>
import type { Key } from 'ant-design-vue/es/table/interface';

/**
 * RecycleBinDrawer - Recycle bin drawer component
 * RecycleBinDrawer - 回收站抽屉组件
 *
 * Displays deleted records list, supports restore/permanent delete/batch operations.
 * 展示已删除记录列表，支持恢复/永久删除/批量操作。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Drawer,
  message,
  Modal,
  Space,
  Spin,
  Table,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { requestClient } from '#/utils/request';

defineOptions({ name: 'RecycleBinDrawer' });

const props = withDefaults(defineProps<Props>(), {
  nameField: 'name',
  columns: undefined,
});

// Emit for parent to know if restored
const emit = defineEmits<{
  (e: 'restored'): void;
}>();

interface Props {
  /** API resource path (e.g. '/tenant/ai/agents') / API 资源路径 */
  resource: string;
  /** Name field (default 'name') / 名称字段 */
  nameField?: string;
  /** Custom column config / 自定义列配置 */
  columns?: Array<{ dataIndex: string; title: string; width?: number }>;
  /** Optional global recycle-bin route / 可选：总回收站路由 */
  globalBinPath?: string;
}

const router = useRouter();
const visible = ref(false);
const loading = ref(false);
const items = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const selectedRowKeys = ref<number[]>([]);
const deletedCount = ref(0);
const hasRestored = ref(false);
const hasItems = computed(() => items.value.length > 0);
const hasSelection = computed(() => selectedRowKeys.value.length > 0);
const globalBinPath = computed(() => {
  if (props.globalBinPath) return props.globalBinPath;
  if (props.resource.startsWith('/admin/')) return '/admin/system/recycle-bin';
  return '';
});
const canOpenGlobalBin = computed(() => globalBinPath.value.length > 0);
const moduleStageHintKey = computed(() =>
  canOpenGlobalBin.value
    ? 'common.recycleBin.moduleStageHintAdmin'
    : 'common.recycleBin.moduleStageHintManaged',
);
const globalRetentionHintKey = computed(() =>
  canOpenGlobalBin.value
    ? 'common.recycleBin.globalRetentionDays'
    : 'common.recycleBin.globalRetentionDaysManaged',
);
const moveToGlobalConfirmKey = computed(() =>
  canOpenGlobalBin.value
    ? 'common.recycleBin.confirmMoveToGlobal'
    : 'common.recycleBin.confirmMoveToGlobalManaged',
);
const batchMoveToGlobalConfirmKey = computed(() =>
  canOpenGlobalBin.value
    ? 'common.recycleBin.confirmBatchMoveToGlobal'
    : 'common.recycleBin.confirmBatchMoveToGlobalManaged',
);

/** Open drawer / 打开抽屉 */
function open() {
  visible.value = true;
  hasRestored.value = false;
  fetchList();
}

/** Close drawer / 关闭抽屉 */
function close() {
  visible.value = false;
}

function openGlobalBin() {
  if (!globalBinPath.value) return;
  visible.value = false;
  void router.push(globalBinPath.value);
}

/** Refresh count (for external calls) / 刷新计数（供外部调用） */
async function refreshCount() {
  try {
    const res = await requestClient.get(`${props.resource}/recycle-bin/count`);
    deletedCount.value = res?.count ?? res?.data?.count ?? 0;
  } catch {
    deletedCount.value = 0;
  }
}

/** Fetch recycle bin list / 获取回收站列表 */
async function fetchList() {
  loading.value = true;
  try {
    const res = await requestClient.get(`${props.resource}/recycle-bin`, {
      params: {
        'page[number]': page.value,
        'page[size]': pageSize.value,
        sort: '-deleted_at',
      },
    });
    items.value = res?.items ?? [];
    total.value = res?.total ?? 0;
    selectedRowKeys.value = [];
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

/** Restore single record / 恢复单条记录 */
async function handleRestore(record: Record<string, unknown>) {
  try {
    await requestClient.post(
      `${props.resource}/recycle-bin/${record.id}/restore`,
    );
    message.success($t('common.recycleBin.restoreSuccess'));
    hasRestored.value = true;
    page.value = 1;
    await fetchList();
    await refreshCount();
  } catch {
    // error handled by interceptor / 错误由请求拦截器处理
  }
}

/** Move a single record into global recycle bin / 将单条记录推进到总回收站 */
function handleDelete(record: Record<string, unknown>) {
  const displayName = String(record[props.nameField] || record.id);
  const title = $t('common.recycleBin.moveToGlobal');
  const content = $t(moveToGlobalConfirmKey.value, {
    name: displayName,
  });
  const successMsg = $t('common.recycleBin.moveToGlobalSuccess');

  Modal.confirm({
    title,
    content,
    okType: 'danger',
    onOk: async () => {
      await requestClient.delete(`${props.resource}/recycle-bin/${record.id}`);
      message.success(successMsg);
      page.value = 1;
      await fetchList();
      await refreshCount();
    },
  });
}

/** Batch restore / 批量恢复 */
async function handleBatchRestore() {
  if (selectedRowKeys.value.length === 0) return;
  try {
    await requestClient.post(`${props.resource}/recycle-bin/batch-restore`, {
      ids: selectedRowKeys.value,
    });
    message.success($t('common.recycleBin.restoreSuccess'));
    hasRestored.value = true;
    page.value = 1;
    await fetchList();
    await refreshCount();
  } catch {
    // error handled by interceptor / 错误由请求拦截器处理
  }
}

/** Batch move records into global recycle bin / 批量推进到总回收站 */
function handleBatchDelete() {
  if (selectedRowKeys.value.length === 0) return;
  const title = $t('common.recycleBin.moveToGlobal');
  const content = $t(batchMoveToGlobalConfirmKey.value, {
    count: selectedRowKeys.value.length,
  });
  const successMsg = $t('common.recycleBin.moveToGlobalSuccess');

  Modal.confirm({
    title,
    content,
    okType: 'danger',
    onOk: async () => {
      await requestClient.delete(`${props.resource}/recycle-bin/batch`, {
        data: { ids: selectedRowKeys.value },
      });
      message.success(successMsg);
      page.value = 1;
      await fetchList();
      await refreshCount();
    },
  });
}

/** Table column definitions / 表格列定义 */
const tableColumns = computed(() => {
  if (props.columns) {
    return [
      ...props.columns,
      {
        title: $t('common.recycleBin.deletedAt'),
        dataIndex: 'deleted_at',
        key: 'deleted_at',
        width: 150,
      },
      {
        title: $t('common.operation'),
        key: 'action',
        width: 200,
        fixed: 'right' as const,
      },
    ];
  }

  return [
    {
      title:
        props.nameField === 'name' ? $t('common.basicInfo') : props.nameField,
      dataIndex: props.nameField,
      ellipsis: true,
    },
    {
      title: $t('common.recycleBin.deletedAt'),
      dataIndex: 'deleted_at',
      key: 'deleted_at',
      width: 150,
    },
    {
      title: $t('common.operation'),
      key: 'action',
      width: 200,
      fixed: 'right' as const,
    },
  ];
});

/** Row selection config / 行选择配置 */
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Key[]) => {
    selectedRowKeys.value = keys as number[];
  },
}));

/** Pagination config / 分页配置 */
const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showLessItems: true,
  showTotal: (t: number) => $t('common.recycleBin.itemCount', { count: t }),
  onChange: (p: number, size: number) => {
    page.value = p;
    pageSize.value = size;
    fetchList();
  },
}));

watch(visible, (val) => {
  if (!val && hasRestored.value) {
    emit('restored');
  }
});

// Initialize count on mount (delay to avoid API errors during setup) / 初始化获取计数（延迟到 mounted）
onMounted(() => refreshCount());

defineExpose({ open, close, refreshCount, deletedCount });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :width="760"
    placement="right"
    :destroy-on-close="false"
  >
    <template #title>
      <div class="flex items-center gap-3">
        <div class="rounded-3xl bg-primary/10 p-3 text-primary">
          <IconifyIcon icon="lucide:archive-restore" class="size-5" />
        </div>
        <div class="min-w-0">
          <div class="text-base font-semibold text-foreground">
            {{ $t('common.recycleBin.moduleStageLabel') }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ $t(moduleStageHintKey, { days: 30 }) }}
          </div>
        </div>
      </div>
    </template>

    <template #extra>
      <Button
        v-if="globalBinPath"
        v-access:code="['recycle_bin:read']"
        size="small"
        class="!rounded-xl"
        @click="openGlobalBin"
      >
        <template #icon>
          <IconifyIcon icon="lucide:external-link" class="size-3.5" />
        </template>
        {{ $t('common.recycleBin.openGlobalBin') }}
      </Button>
    </template>

    <div class="space-y-4">
      <div class="relative overflow-hidden rounded-3xl border border-primary/15 bg-gradient-to-br from-primary/15 via-primary/5 to-background p-4 shadow-sm">
        <div class="absolute -right-10 top-0 size-28 rounded-full bg-primary/10 blur-3xl"></div>
        <div class="relative flex flex-wrap items-start justify-between gap-4">
          <div class="max-w-[420px]">
            <div class="inline-flex rounded-full bg-background/80 px-3 py-1 text-[11px] font-medium text-foreground/80">
              {{ $t('common.recycleBin.moduleStageLabel') }}
            </div>
            <div class="mt-3 text-sm font-semibold text-foreground">
              {{ $t('common.recycleBin.title') }}
            </div>
            <div class="mt-1 text-xs leading-6 text-muted-foreground">
              {{ $t(moduleStageHintKey, { days: 30 }) }}
            </div>
            <div class="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span class="rounded-full bg-background/80 px-3 py-1">
                {{ $t('common.recycleBin.moduleRetentionDays', { days: 30 }) }}
              </span>
              <span class="rounded-full bg-background/80 px-3 py-1">
                {{ $t(globalRetentionHintKey, { days: 30 }) }}
              </span>
            </div>
          </div>

          <div class="grid min-w-[220px] flex-1 gap-3 sm:grid-cols-2">
            <div class="rounded-2xl border border-border/60 bg-background/85 p-3">
              <div class="text-[11px] uppercase tracking-[0.2em] text-muted-foreground/80">
                {{ $t('common.recycleBin.itemCountLabel') }}
              </div>
              <div class="mt-2 text-2xl font-semibold text-foreground">
                {{ total }}
              </div>
            </div>
            <div class="rounded-2xl border border-border/60 bg-background/85 p-3">
              <div class="text-[11px] uppercase tracking-[0.2em] text-muted-foreground/80">
                {{ $t('common.recycleBin.selectedCountLabel', { count: selectedRowKeys.length }) }}
              </div>
              <div class="mt-2 text-2xl font-semibold text-foreground">
                {{ selectedRowKeys.length }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="hasSelection"
        class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3"
      >
        <span class="text-sm text-foreground">
          {{
            $t('common.recycleBin.itemCount', { count: selectedRowKeys.length })
          }}
        </span>
        <Space :size="8">
          <Button size="small" class="!rounded-xl" @click="handleBatchRestore">
            <template #icon>
              <IconifyIcon icon="lucide:rotate-ccw" class="size-3.5" />
            </template>
            {{ $t('common.recycleBin.batchRestore') }}
          </Button>
          <Button
            size="small"
            danger
            class="!rounded-xl"
            @click="handleBatchDelete"
          >
            <template #icon>
              <IconifyIcon icon="lucide:move-right" class="size-3.5" />
            </template>
            {{ $t('common.recycleBin.batchMoveToGlobal') }}
          </Button>
        </Space>
      </div>

      <div class="overflow-hidden rounded-3xl border border-border/60 bg-card/80 shadow-sm">
        <Spin :spinning="loading">
          <Table
            v-if="hasItems"
            :columns="tableColumns"
            :data-source="items"
            :row-selection="rowSelection"
            :pagination="pagination"
            :row-key="(r: Record<string, unknown>) => r.id as number"
            size="middle"
            :scroll="{ x: 600 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'deleted_at'">
                <Tooltip :title="formatDate(record.deleted_at)">
                  <span class="text-muted-foreground">{{
                    formatRelativeTime(record.deleted_at)
                  }}</span>
                </Tooltip>
              </template>
              <template v-else-if="column.key === 'action'">
                <Space :size="8">
                  <Button
                    type="text"
                    size="small"
                    class="!rounded-xl !px-2 !text-primary hover:!bg-primary/10"
                    @click="handleRestore(record)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:rotate-ccw" class="size-4" />
                    </template>
                    {{ $t('common.recycleBin.restore') }}
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    danger
                    class="!rounded-xl !px-2 hover:!bg-destructive/10"
                    @click="handleDelete(record)"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:move-right" class="size-4" />
                    </template>
                    {{ $t('common.recycleBin.moveToGlobal') }}
                  </Button>
                </Space>
              </template>
            </template>
          </Table>

          <div
            v-else-if="!loading"
            class="flex flex-col items-center justify-center px-6 py-16 text-center"
          >
            <div class="rounded-3xl bg-primary/10 p-4 text-primary">
              <IconifyIcon icon="lucide:trash-2" class="size-8" />
            </div>
            <p class="mt-4 text-base font-medium text-foreground">
              {{ $t('common.recycleBin.empty') }}
            </p>
            <p class="mt-2 max-w-sm text-sm leading-7 text-muted-foreground">
              {{ $t('common.recycleBin.emptyDesc') }}
            </p>
            <Button
              v-if="globalBinPath"
              v-access:code="['recycle_bin:read']"
              class="mt-5 !rounded-xl"
              @click="openGlobalBin"
            >
              <template #icon>
                <IconifyIcon icon="lucide:external-link" class="size-4" />
              </template>
              {{ $t('common.recycleBin.openGlobalBin') }}
            </Button>
          </div>
        </Spin>
      </div>
    </div>
  </Drawer>
</template>
