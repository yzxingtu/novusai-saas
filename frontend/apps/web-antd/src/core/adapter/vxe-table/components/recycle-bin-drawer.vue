<script lang="ts" setup>
import type { Key } from 'ant-design-vue/es/table/interface';

/**
 * RecycleBinDrawer - 回收站抽屉组件
 *
 * 展示已删除记录列表，支持恢复/永久删除/批量操作
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
});

// Emit for parent to know if restored
const emit = defineEmits<{
  (e: 'restored'): void;
}>();

interface Props {
  /** API 资源路径 (e.g. '/tenant/ai/agents') */
  resource: string;
  /** 名称字段 (默认 'name') */
  nameField?: string;
  /** 自定义列配置 */
  columns?: Array<{ dataIndex: string; title: string; width?: number }>;
}

const visible = ref(false);
const loading = ref(false);
const items = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const selectedRowKeys = ref<number[]>([]);
const deletedCount = ref(0);
const hasRestored = ref(false);

/** 打开抽屉 */
function open() {
  visible.value = true;
  hasRestored.value = false;
  fetchList();
}

/** 关闭抽屉 */
function close() {
  visible.value = false;
}

/** 刷新计数（供外部调用） */
async function refreshCount() {
  try {
    const res = await requestClient.get(`${props.resource}/recycle-bin/count`);
    deletedCount.value = res?.count ?? res?.data?.count ?? 0;
  } catch {
    deletedCount.value = 0;
  }
}

/** 获取回收站列表 */
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

/** 恢复单条记录 */
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

/** 永久删除单条记录 */
function handlePermanentDelete(record: Record<string, unknown>) {
  const displayName = String(record[props.nameField] || record.id);
  Modal.confirm({
    title: $t('common.recycleBin.permanentDelete'),
    content: $t('common.recycleBin.confirmPermanentDelete', {
      name: displayName,
    }),
    okType: 'danger',
    onOk: async () => {
      await requestClient.delete(`${props.resource}/recycle-bin/${record.id}`);
      message.success($t('common.recycleBin.deleteSuccess'));
      page.value = 1;
      await fetchList();
      await refreshCount();
    },
  });
}

/** 批量恢复 */
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

/** 批量永久删除 */
function handleBatchPermanentDelete() {
  if (selectedRowKeys.value.length === 0) return;
  Modal.confirm({
    title: $t('common.recycleBin.permanentDelete'),
    content: $t('common.recycleBin.confirmBatchPermanentDelete', {
      count: selectedRowKeys.value.length,
    }),
    okType: 'danger',
    onOk: async () => {
      await requestClient.delete(`${props.resource}/recycle-bin/batch`, {
        data: { ids: selectedRowKeys.value },
      });
      message.success($t('common.recycleBin.deleteSuccess'));
      page.value = 1;
      await fetchList();
      await refreshCount();
    },
  });
}

/** 表格列定义 */
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

/** 行选择配置 */
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Key[]) => {
    selectedRowKeys.value = keys as number[];
  },
}));

/** 分页配置 */
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

// 初始化获取计数（延迟到 mounted，避免 setup 阶段 API 调用出错）
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
    <!-- 批量操作栏 -->
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
        <Button size="small" danger @click="handleBatchPermanentDelete">
          <template #icon>
            <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
          </template>
          {{ $t('common.recycleBin.batchDelete') }}
        </Button>
      </Space>
    </div>

    <!-- 保留天数提示 -->
    <div class="mb-3 flex items-center gap-1 text-xs text-muted-foreground/70">
      <IconifyIcon icon="lucide:info" class="size-3.5" />
      <span>{{ $t('common.recycleBin.retentionDays', { days: 30 }) }}</span>
    </div>

    <!-- 表格 -->
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
              <Tooltip :title="$t('common.recycleBin.permanentDelete')">
                <Button
                  type="link"
                  size="small"
                  danger
                  @click="handlePermanentDelete(record)"
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

      <!-- 空状态 -->
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
