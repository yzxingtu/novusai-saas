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
  side: undefined,
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
  /** Side: admin=permanent delete, tenant=escalate to admin / 端侧：admin=永久删除，tenant=升级到管理端 */
  side?: 'admin' | 'tenant';
}

// Auto-detect side from resource path when not explicitly set / 未显式设置时从资源路径自动检测端侧
const resolvedSide = computed(() => {
  if (props.side) return props.side;
  return props.resource.startsWith('/tenant') ? 'tenant' : 'admin';
});

const isTenantSide = computed(() => resolvedSide.value === 'tenant');

const visible = ref(false);
const loading = ref(false);
const items = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const selectedRowKeys = ref<number[]>([]);
const deletedCount = ref(0);
const hasRestored = ref(false);

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
    // error handled by interceptor
  }
}

/** Delete single record (permanent on admin side, escalate on tenant side) / 删除单条记录（管理端永久删除，租户端升级到管理端） */
function handleDelete(record: Record<string, unknown>) {
  const displayName = String(record[props.nameField] || record.id);
  const title = isTenantSide.value
    ? $t('common.recycleBin.escalate')
    : $t('common.recycleBin.permanentDelete');
  const content = isTenantSide.value
    ? $t('common.recycleBin.confirmEscalate', { name: displayName })
    : $t('common.recycleBin.confirmPermanentDelete', { name: displayName });
  const successMsg = isTenantSide.value
    ? $t('common.recycleBin.escalateSuccess')
    : $t('common.recycleBin.deleteSuccess');

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
    // error handled by interceptor
  }
}

/** Batch delete (permanent on admin side, escalate on tenant side) / 批量删除（管理端永久删除，租户端升级到管理端） */
function handleBatchDelete() {
  if (selectedRowKeys.value.length === 0) return;
  const title = isTenantSide.value
    ? $t('common.recycleBin.escalate')
    : $t('common.recycleBin.permanentDelete');
  const content = isTenantSide.value
    ? $t('common.recycleBin.confirmBatchEscalate', {
        count: selectedRowKeys.value.length,
      })
    : $t('common.recycleBin.confirmBatchPermanentDelete', {
        count: selectedRowKeys.value.length,
      });
  const successMsg = isTenantSide.value
    ? $t('common.recycleBin.escalateSuccess')
    : $t('common.recycleBin.deleteSuccess');

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
        width: 120,
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
      width: 120,
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
  showSizeChanger: false,
  showTotal: (t: number) => $t('common.recycleBin.itemCount', { count: t }),
  onChange: (p: number) => {
    page.value = p;
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
    :title="$t('common.recycleBin.title')"
    :width="640"
    placement="right"
    :destroy-on-close="false"
  >
    <!-- Batch operations bar / 批量操作栏 -->
    <div
      v-if="selectedRowKeys.length > 0"
      class="mb-3 flex items-center justify-between rounded-lg bg-primary/5 px-4 py-2"
    >
      <span class="text-sm text-muted-foreground">
        {{
          $t('common.recycleBin.itemCount', { count: selectedRowKeys.length })
        }}
      </span>
      <Space>
        <Button size="small" @click="handleBatchRestore">
          <template #icon>
            <IconifyIcon icon="lucide:rotate-ccw" class="size-3.5" />
          </template>
          {{ $t('common.recycleBin.batchRestore') }}
        </Button>
        <Button size="small" danger @click="handleBatchDelete">
          <template #icon>
            <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
          </template>
          {{ $t('common.recycleBin.batchDelete') }}
        </Button>
      </Space>
    </div>

    <!-- Retention days notice / 保留天数提示 -->
    <div class="mb-3 flex items-center gap-1 text-xs text-muted-foreground/70">
      <IconifyIcon icon="lucide:info" class="size-3.5" />
      <span>{{ $t('common.recycleBin.retentionDays', { days: 30 }) }}</span>
      <template v-if="isTenantSide">
        <span class="mx-1">·</span>
        <span>{{ $t('common.recycleBin.escalateHint') }}</span>
      </template>
    </div>

    <!-- Table / 表格 -->
    <Spin :spinning="loading">
      <Table
        v-if="items.length > 0"
        :columns="tableColumns"
        :data-source="items"
        :row-selection="rowSelection"
        :pagination="pagination"
        :row-key="(r: Record<string, unknown>) => r.id as number"
        size="small"
        :scroll="{ x: 500 }"
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
            <Space :size="4">
              <Tooltip :title="$t('common.recycleBin.restore')">
                <Button
                  type="link"
                  size="small"
                  class="text-primary"
                  @click="handleRestore(record)"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:rotate-ccw" class="size-4" />
                  </template>
                </Button>
              </Tooltip>
              <Tooltip
                :title="
                  isTenantSide
                    ? $t('common.recycleBin.escalate')
                    : $t('common.recycleBin.permanentDelete')
                "
              >
                <Button
                  type="link"
                  size="small"
                  danger
                  @click="handleDelete(record)"
                >
                  <template #icon>
                    <IconifyIcon icon="lucide:x" class="size-4" />
                  </template>
                </Button>
              </Tooltip>
            </Space>
          </template>
        </template>
      </Table>

      <!-- Empty state / 空状态 -->
      <div
        v-else-if="!loading"
        class="flex flex-col items-center justify-center py-16"
      >
        <IconifyIcon
          icon="lucide:trash-2"
          class="mb-4 size-12 text-muted-foreground/30"
        />
        <p class="text-sm text-muted-foreground">
          {{ $t('common.recycleBin.empty') }}
        </p>
        <p class="text-xs text-muted-foreground/60">
          {{ $t('common.recycleBin.emptyDesc') }}
        </p>
      </div>
    </Spin>
  </Drawer>
</template>
