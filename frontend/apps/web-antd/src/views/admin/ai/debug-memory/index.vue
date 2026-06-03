<script lang="ts" setup>
import type { TableColumnsType } from 'ant-design-vue';

import type {
  AdminMemoryRecordItem,
  AdminProfileSnapshotItem,
} from '#/api/admin/long-term-memory';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';

import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Spin,
  Table,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  getAdminMemoryRecordListApi,
  getAdminProfileSnapshotDetailApi,
  getAdminProfileSnapshotListApi,
} from '#/api/admin/long-term-memory';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

defineOptions({ name: 'AdminDebugMemoryPage' });

type DebugTab = 'profiles' | 'records';
const LIST_REQUEST_OPTIONS = {
  showCodeMessage: false,
  showErrorMessage: false,
} as const;

const activeTab = ref<DebugTab>('records');
const loading = ref(false);
const loadError = ref('');
const detailOpen = ref(false);
const detailLoading = ref(false);
const detailPayload = ref<null | Record<string, unknown>>(null);
const detailTitle = ref('');

const records = ref<AdminMemoryRecordItem[]>([]);
const profiles = ref<AdminProfileSnapshotItem[]>([]);

const heroChips = computed(() => [
  { key: 'memory', text: $t('admin.ai.memoryDebug.pageDesc') },
]);

const metrics = computed(() => [
  {
    key: 'records',
    label: $t('admin.ai.memoryDebug.tabs.records'),
    value: records.value.length,
  },
  {
    key: 'profiles',
    label: $t('admin.ai.memoryDebug.tabs.profiles'),
    value: profiles.value.length,
  },
]);

const recordColumns = computed<TableColumnsType<AdminMemoryRecordItem>>(() => [
  {
    title: $t('admin.ai.memoryDebug.id'),
    dataIndex: 'id',
    key: 'id',
    width: 90,
  },
  {
    title: $t('admin.ai.memoryDebug.scopeType'),
    dataIndex: 'scope_type',
    key: 'scope_type',
    width: 180,
  },
  {
    title: $t('admin.ai.memoryDebug.memoryType'),
    dataIndex: 'memory_type',
    key: 'memory_type',
    width: 140,
  },
  {
    title: $t('admin.ai.memoryDebug.status'),
    dataIndex: 'status',
    key: 'status',
    width: 120,
  },
  {
    title: $t('admin.ai.memoryDebug.summary'),
    dataIndex: 'summary',
    key: 'summary',
  },
  { title: $t('admin.common.operation'), key: 'op', width: 120 },
]);

const profileColumns = computed<TableColumnsType<AdminProfileSnapshotItem>>(
  () => [
    {
      title: $t('admin.ai.memoryDebug.id'),
      dataIndex: 'id',
      key: 'id',
      width: 90,
    },
    {
      title: $t('admin.ai.memoryDebug.scopeType'),
      dataIndex: 'scope_type',
      key: 'scope_type',
      width: 180,
    },
    {
      title: $t('admin.ai.memoryDebug.recordCount'),
      dataIndex: 'record_count',
      key: 'record_count',
      width: 120,
    },
    {
      title: $t('admin.ai.memoryDebug.summary'),
      dataIndex: 'summary',
      key: 'summary',
    },
    { title: $t('admin.common.operation'), key: 'op', width: 120 },
  ],
);

async function loadCurrentTab() {
  loading.value = true;
  loadError.value = '';
  try {
    if (activeTab.value === 'records') {
      const res = await getAdminMemoryRecordListApi(
        { 'page[number]': 1, 'page[size]': 50 },
        LIST_REQUEST_OPTIONS,
      );
      records.value = res.items ?? [];
      profiles.value = [];
      return;
    }
    const res = await getAdminProfileSnapshotListApi(
      { 'page[number]': 1, 'page[size]': 50 },
      LIST_REQUEST_OPTIONS,
    );
    profiles.value = res.items ?? [];
    records.value = [];
  } catch (error) {
    records.value = [];
    profiles.value = [];
    loadError.value = showRequestError(error, 'common.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function openRecordDetail(item: AdminMemoryRecordItem) {
  detailOpen.value = true;
  detailLoading.value = false;
  detailTitle.value = `${$t('admin.ai.memoryDebug.tabs.records')} #${item.id}`;
  detailPayload.value = item as unknown as Record<string, unknown>;
}

function openRecordDetailFromTable(record: Record<string, unknown>) {
  return openRecordDetail(record as unknown as AdminMemoryRecordItem);
}

async function openProfileDetail(item: AdminProfileSnapshotItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  detailTitle.value = `${$t('admin.ai.memoryDebug.tabs.profiles')} #${item.id}`;
  detailPayload.value = null;
  try {
    const detail = await getAdminProfileSnapshotDetailApi(
      item.id,
      LIST_REQUEST_OPTIONS,
    );
    detailPayload.value = (detail || {}) as Record<string, unknown>;
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
  } finally {
    detailLoading.value = false;
  }
}

function openProfileDetailFromTable(record: Record<string, unknown>) {
  return openProfileDetail(record as unknown as AdminProfileSnapshotItem);
}

watch(activeTab, loadCurrentTab);

onMounted(async () => {
  await loadCurrentTab();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.ai.memoryDebug.pageDesc')"
      icon="lucide:brain-circuit"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="metrics"
      :title="$t('admin.ai.memoryDebug.title')"
    />

    <Tabs v-model:active-key="activeTab">
      <Tabs.TabPane
        key="records"
        :tab="$t('admin.ai.memoryDebug.tabs.records')"
      />
      <Tabs.TabPane
        key="profiles"
        :tab="$t('admin.ai.memoryDebug.tabs.profiles')"
      />
    </Tabs>

    <Alert v-if="loadError" :message="loadError" show-icon type="error" />

    <div v-if="loading" class="flex items-center justify-center py-16">
      <Spin />
    </div>

    <Table
      v-else-if="activeTab === 'records'"
      :columns="recordColumns"
      :data-source="records"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'status'">
          <Tag>{{ record.status }}</Tag>
        </template>
        <template v-else-if="column.key === 'op'">
          <Button type="link" @click="openRecordDetailFromTable(record)">
            {{ $t('shared.common.viewDetail') }}
          </Button>
        </template>
      </template>
    </Table>

    <Table
      v-else-if="activeTab === 'profiles'"
      :columns="profileColumns"
      :data-source="profiles"
      :pagination="false"
      row-key="id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'op'">
          <Button type="link" @click="openProfileDetailFromTable(record)">
            {{ $t('shared.common.viewDetail') }}
          </Button>
        </template>
      </template>
    </Table>

    <Empty
      v-if="
        !loading &&
        ((activeTab === 'records' && records.length === 0) ||
          (activeTab === 'profiles' && profiles.length === 0))
      "
      :description="$t('admin.common.noData')"
    />

    <Drawer v-model:open="detailOpen" width="760">
      <template #title>{{ detailTitle }}</template>
      <div v-if="detailLoading" class="flex items-center justify-center py-16">
        <Spin />
      </div>
      <Descriptions v-else-if="detailPayload" bordered :column="1" size="small">
        <Descriptions.Item
          v-for="(value, key) in detailPayload"
          :key="String(key)"
          :label="String(key)"
        >
          <pre class="whitespace-pre-wrap break-all">{{
            typeof value === 'string' ? value : JSON.stringify(value, null, 2)
          }}</pre>
        </Descriptions.Item>
      </Descriptions>
      <Empty v-else :description="$t('admin.common.noData')" />
    </Drawer>
  </Page>
</template>
