<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';

import { $t } from '#/locales';

import {
  Table,
  Tag,
  Button,
  Space,
  Input,
  Select,
  Card,
  Statistic,
  Row,
  Col,
  Popconfirm,
  message,
  Tooltip,
} from 'ant-design-vue';

import { IconifyIcon } from '@vben/icons';

import type { CrudRecordInfo, CrudRecordStatistics } from '#/api/admin/crud-records';

import {
  getCrudRecordListApi,
  getCrudRecordStatisticsApi,
  deleteCrudRecordApi,
} from '#/api/admin/crud-records';

import RecordDetailDrawer from './modules/record-detail-drawer.vue';

import {
  formatDuration,
  formatTime,
  getStatusColor,
  getStatusLabel,
  getTypeColor,
  getTypeLabel,
} from './utils';

const T = 'admin.dev.crudGenerator.records';

// ============================================================
// 状态
// ============================================================

const loading = ref(false);
const records = ref<CrudRecordInfo[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const statistics = ref<CrudRecordStatistics | null>(null);

// 筛选
const filterType = ref<string | undefined>(undefined);
const filterStatus = ref<string | undefined>(undefined);
const filterModule = ref('');

// 详情抽屉
const detailDrawerRef = ref<InstanceType<typeof RecordDetailDrawer> | null>(null);

// ============================================================
// 操作类型与状态配置
// ============================================================

const operationTypeOptions = [
  { value: 'preview', label: () => $t(`${T}.type.preview`) },
  { value: 'generate', label: () => $t(`${T}.type.generate`) },
  { value: 'rollback', label: () => $t(`${T}.type.rollback`) },
  { value: 'delete', label: () => $t(`${T}.type.delete`) },
];

const statusOptions = [
  { value: 'success', label: () => $t(`${T}.status.success`) },
  { value: 'partial_failure', label: () => $t(`${T}.status.partialFailure`) },
  { value: 'failed', label: () => $t(`${T}.status.failed`) },
  { value: 'rolled_back', label: () => $t(`${T}.status.rolledBack`) },
];


// ============================================================
// 表格列
// ============================================================

const columns = computed(() => [
  {
    title: 'ID',
    dataIndex: 'id',
    width: 70,
  },
  {
    title: $t(`${T}.column.operationType`),
    dataIndex: 'operation_type',
    width: 100,
  },
  {
    title: $t(`${T}.column.moduleName`),
    dataIndex: 'module_name',
    width: 130,
  },
  {
    title: $t(`${T}.column.tableName`),
    dataIndex: 'table_name',
    width: 130,
  },
  {
    title: $t(`${T}.column.fileCount`),
    dataIndex: 'file_count',
    width: 80,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.column.status`),
    dataIndex: 'status',
    width: 110,
  },
  {
    title: $t(`${T}.column.duration`),
    dataIndex: 'duration_ms',
    width: 100,
    align: 'right' as const,
  },
  {
    title: $t(`${T}.column.operator`),
    dataIndex: 'operator_name',
    width: 100,
  },
  {
    title: $t(`${T}.column.createdAt`),
    dataIndex: 'created_at',
    width: 170,
  },
  {
    title: $t(`${T}.column.actions`),
    key: 'actions',
    width: 120,
    fixed: 'right' as const,
  },
]);

// ============================================================
// 数据加载
// ============================================================

async function fetchRecords() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      'page[number]': page.value,
      'page[size]': pageSize.value,
      'sort': '-created_at',
    };
    if (filterType.value) {
      params['filter[operation_type][eq]'] = filterType.value;
    }
    if (filterStatus.value) {
      params['filter[status][eq]'] = filterStatus.value;
    }
    if (filterModule.value) {
      params['filter[module_name][ilike]'] = filterModule.value;
    }
    const res = await getCrudRecordListApi(params);
    records.value = res.items || [];
    total.value = res.total || 0;
  } finally {
    loading.value = false;
  }
}

async function fetchStatistics() {
  try {
    const res = await getCrudRecordStatisticsApi();
    statistics.value = res;
  } catch {
    // ignore
  }
}

// ============================================================
// 操作
// ============================================================

function handleSearch() {
  page.value = 1;
  fetchRecords();
}

function handleReset() {
  filterType.value = undefined;
  filterStatus.value = undefined;
  filterModule.value = '';
  page.value = 1;
  fetchRecords();
}

function handlePageChange(p: number, ps: number) {
  page.value = p;
  pageSize.value = ps;
  fetchRecords();
}

function handleViewDetail(record: CrudRecordInfo) {
  detailDrawerRef.value?.open(record.id);
}

async function handleDelete(record: CrudRecordInfo) {
  try {
    await deleteCrudRecordApi(record.id);
    message.success($t(`${T}.deleteSuccess`));
    fetchRecords();
    fetchStatistics();
  } catch {
    message.error($t(`${T}.deleteFailed`));
  }
}


// ============================================================
// 初始化
// ============================================================

onMounted(() => {
  fetchRecords();
  fetchStatistics();
});
</script>

<template>
  <div class="p-4">
    <!-- 统计卡片 -->
    <Row :gutter="16" class="mb-4">
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t(`${T}.stats.total`)"
            :value="statistics?.total ?? 0"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:history" class="text-primary mr-1" />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t(`${T}.stats.generates`)"
            :value="statistics?.by_type?.generate ?? 0"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:file-code" class="mr-1 text-green-500" />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t(`${T}.stats.previews`)"
            :value="statistics?.by_type?.preview ?? 0"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:eye" class="mr-1 text-blue-500" />
            </template>
          </Statistic>
        </Card>
      </Col>
      <Col :span="6">
        <Card size="small">
          <Statistic
            :title="$t(`${T}.stats.avgDuration`)"
            :value="statistics?.avg_duration_ms ?? 0"
            suffix="ms"
          >
            <template #prefix>
              <IconifyIcon icon="lucide:timer" class="mr-1 text-orange-500" />
            </template>
          </Statistic>
        </Card>
      </Col>
    </Row>

    <!-- 搜索栏 -->
    <Card size="small" class="mb-4">
      <Space wrap>
        <Input
          v-model:value="filterModule"
          :placeholder="$t(`${T}.filter.modulePlaceholder`)"
          allow-clear
          style="width: 180px"
          @press-enter="handleSearch"
        />
        <Select
          v-model:value="filterType"
          :placeholder="$t(`${T}.filter.operationType`)"
          allow-clear
          style="width: 140px"
        >
          <Select.Option
            v-for="opt in operationTypeOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label() }}
          </Select.Option>
        </Select>
        <Select
          v-model:value="filterStatus"
          :placeholder="$t(`${T}.filter.status`)"
          allow-clear
          style="width: 140px"
        >
          <Select.Option
            v-for="opt in statusOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label() }}
          </Select.Option>
        </Select>
        <Button type="primary" @click="handleSearch">
          <IconifyIcon icon="lucide:search" class="mr-1" />
          {{ $t(`${T}.filter.search`) }}
        </Button>
        <Button @click="handleReset">
          <IconifyIcon icon="lucide:rotate-ccw" class="mr-1" />
          {{ $t(`${T}.filter.reset`) }}
        </Button>
      </Space>
    </Card>

    <!-- 数据表格 -->
    <Card size="small">
      <Table
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t: number) => `${$t(`${T}.totalRecords`, { total: t })}`,
          onChange: handlePageChange,
        }"
        row-key="id"
        size="small"
        :scroll="{ x: 1200 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'operation_type'">
            <Tag :color="getTypeColor(record.operation_type)">
              {{ getTypeLabel(record.operation_type) }}
            </Tag>
          </template>
          <template v-else-if="column.dataIndex === 'module_name'">
            <span class="font-mono text-xs">{{ record.module_name || '-' }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'table_name'">
            <span class="font-mono text-xs">{{ record.table_name || '-' }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'status'">
            <Tag :color="getStatusColor(record.status)">
              {{ getStatusLabel(record.status) }}
            </Tag>
          </template>
          <template v-else-if="column.dataIndex === 'duration_ms'">
            {{ formatDuration(record.duration_ms) }}
          </template>
          <template v-else-if="column.dataIndex === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <Space>
              <Tooltip :title="$t(`${T}.action.viewDetail`)">
                <Button
                  type="link"
                  size="small"
                  @click="handleViewDetail(record as CrudRecordInfo)"
                >
                  <IconifyIcon icon="lucide:eye" />
                </Button>
              </Tooltip>
              <Popconfirm
                :title="$t(`${T}.action.deleteConfirm`)"
                @confirm="handleDelete(record as CrudRecordInfo)"
              >
                <Tooltip :title="$t(`${T}.action.delete`)">
                  <Button type="link" size="small" danger>
                    <IconifyIcon icon="lucide:trash-2" />
                  </Button>
                </Tooltip>
              </Popconfirm>
            </Space>
          </template>
        </template>
      </Table>
    </Card>

    <!-- 详情抽屉 -->
    <RecordDetailDrawer ref="detailDrawerRef" />
  </div>
</template>
