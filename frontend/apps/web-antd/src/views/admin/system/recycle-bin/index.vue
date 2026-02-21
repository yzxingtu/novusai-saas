<script lang="ts" setup>
/**
 * 管理端总回收站页面
 *
 * - 高级搜索：继承原 CRUD 模块的声明式搜索 Schema（searchInput / statusSelect / select）
 * - 动态列：根据模块元数据渲染不同列
 * - 租户区分：租户级模块展示「所属租户」列
 */
import { computed, nextTick, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Empty,
  message,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';

import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
  RecycleBinModuleSummary,
} from '#/api/admin/recycle-bin';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getRecycleBinListApi,
  getRecycleBinModulesApi,
  getRecycleBinSummaryApi,
  permanentDeleteRecycleBinItemApi,
  restoreRecycleBinItemApi,
  triggerRecycleBinCleanupApi,
} from '#/api/admin/recycle-bin';

import { getColumnLabel, getModuleSearchSchema } from './data';

// ==================== 状态 ====================
const summaryLoading = ref(false);
const listLoading = ref(false);
const summary = ref<RecycleBinModuleSummary[]>([]);
const moduleMeta = ref<Record<string, RecycleBinModuleMeta>>({});
const activeModule = ref('');
const items = ref<RecycleBinItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);

// ==================== 搜索表单 ====================
const [SearchForm, searchFormApi] = useVbenForm({
  schema: [],
  commonConfig: {
    componentProps: {
      class: 'w-full',
    },
  },
  showDefaultActions: false,
  submitOnChange: true,
  handleSubmit: () => {
    currentPage.value = 1;
    loadList();
  },
  wrapperClass: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4',
});

// ==================== 总数 ====================
const totalDeletedCount = computed(() =>
  summary.value.reduce((sum, m) => sum + m.count, 0),
);

// ==================== 当前模块元数据 ====================
const currentMeta = computed(
  () => moduleMeta.value[activeModule.value] ?? null,
);

// ==================== 模块图标映射 ====================
const moduleIcons: Record<string, string> = {
  ai_providers: 'lucide:server',
  ai_models: 'lucide:brain',
  agents: 'lucide:bot',
  skill_packages: 'lucide:package',
  knowledge_bases: 'lucide:book-open',
  admin_roles: 'lucide:shield',
  tenant_plans: 'lucide:credit-card',
  tenants: 'lucide:building-2',
  tenant_domains: 'lucide:globe',
  table_policies: 'lucide:table',
};

// ==================== 加载 ====================
async function loadModuleMeta() {
  try {
    const res = await getRecycleBinModulesApi();
    moduleMeta.value = res ?? {};
  } catch {
    moduleMeta.value = {};
  }
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await getRecycleBinSummaryApi();
    summary.value = res ?? [];
    if (summary.value.length > 0 && !activeModule.value) {
      activeModule.value = summary.value[0]!.module;
    }
    if (activeModule.value) {
      await loadList();
    }
  } catch {
    summary.value = [];
  } finally {
    summaryLoading.value = false;
  }
}

async function loadList() {
  if (!activeModule.value) return;
  listLoading.value = true;
  try {
    const params: Record<string, unknown> = {
      'page[number]': currentPage.value,
      'page[size]': pageSize.value,
      sort: '-deleted_at',
    };
    // 从搜索表单获取过滤参数
    const formValues = await searchFormApi.getValues();
    for (const [key, val] of Object.entries(formValues)) {
      if (val !== undefined && val !== null && val !== '') {
        params[key] = val;
      }
    }
    const res = await getRecycleBinListApi(activeModule.value, params);
    items.value = res?.items ?? [];
    total.value = res?.total ?? 0;
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    listLoading.value = false;
  }
}

// ==================== 操作 ====================
async function handleRestore(record: RecycleBinItem) {
  try {
    await restoreRecycleBinItemApi(activeModule.value, record.id);
    message.success($t('common.recycleBin.restoreSuccess'));
    await loadList();
    await loadSummary();
  } catch {
    // handled by interceptor
  }
}

function handlePermanentDelete(record: RecycleBinItem) {
  const meta = currentMeta.value;
  const labelField = meta?.label_field ?? 'name';
  const displayName = String(record[labelField] ?? record.id);
  Modal.confirm({
    title: $t('common.recycleBin.permanentDelete'),
    content: $t('common.recycleBin.confirmPermanentDelete', {
      name: displayName,
    }),
    okType: 'danger',
    onOk: async () => {
      await permanentDeleteRecycleBinItemApi(activeModule.value, record.id);
      message.success($t('common.recycleBin.deleteSuccess'));
      await loadList();
      await loadSummary();
    },
  });
}

async function handleCleanup() {
  try {
    await triggerRecycleBinCleanupApi(30);
    message.success($t('admin.system.recycleBin.cleanupTriggered'));
  } catch {
    // handled by interceptor
  }
}

async function onTabChange(key: string | number) {
  activeModule.value = String(key);
  currentPage.value = 1;
  // 切换搜索 Schema 并重置表单
  const schema = getModuleSearchSchema(activeModule.value);
  await searchFormApi.setState({ schema });
  await nextTick();
  await searchFormApi.resetForm();
  await loadList();
}

function onPageChange(p: number, ps: number) {
  currentPage.value = p;
  pageSize.value = ps;
  loadList();
}

// ==================== 动态列定义 ====================
const columns = computed(() => {
  const meta = currentMeta.value;
  const cols: Record<string, unknown>[] = [];

  if (meta) {
    for (const field of meta.columns) {
      cols.push({
        title: getColumnLabel(field, activeModule.value),
        dataIndex: field,
        key: field,
        ellipsis: true,
      });
    }
    if (meta.is_tenant) {
      cols.push({
        title: $t('admin.system.recycleBin.tenant'),
        dataIndex: 'tenant_name',
        key: 'tenant_name',
        width: 150,
      });
    }
  } else {
    cols.push({
      title: $t('common.basicInfo'),
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    });
  }

  cols.push({
    title: $t('admin.system.recycleBin.deleteLevel'),
    dataIndex: 'delete_level',
    key: 'delete_level',
    width: 100,
    align: 'center' as const,
  });

  cols.push({
    title: $t('common.recycleBin.deletedAt'),
    dataIndex: 'deleted_at',
    key: 'deleted_at',
    width: 180,
  });

  cols.push({
    title: $t('admin.common.operation'),
    key: 'action',
    width: 120,
    align: 'center' as const,
    fixed: 'right' as const,
  });

  return cols;
});

// ==================== 初始化 ====================
onMounted(async () => {
  await loadModuleMeta();
  await loadSummary();
  // 初始化第一个模块的搜索 Schema
  if (activeModule.value) {
    const schema = getModuleSearchSchema(activeModule.value);
    await searchFormApi.setState({ schema });
  }
});
</script>

<template>
  <Page
    auto-content-height
    :title="$t('admin.system.recycleBin.title')"
    :description="$t('admin.system.recycleBin.description')"
  >
    <template #extra>
      <Space>
        <Tag v-if="totalDeletedCount > 0" color="orange">
          {{ $t('common.recycleBin.itemCount', { count: totalDeletedCount }) }}
        </Tag>
        <Popconfirm
          :title="$t('admin.system.recycleBin.cleanupConfirm')"
          @confirm="handleCleanup"
        >
          <Button type="primary" danger>
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
            {{ $t('admin.system.recycleBin.cleanup') }}
          </Button>
        </Popconfirm>
      </Space>
    </template>

    <Spin :spinning="summaryLoading">
      <!-- 无数据 -->
      <div
        v-if="!summaryLoading && summary.length === 0"
        class="flex flex-col items-center justify-center py-20"
      >
        <IconifyIcon
          icon="lucide:trash-2"
          class="mb-4 size-16 text-muted-foreground/20"
        />
        <p class="text-base text-muted-foreground">
          {{ $t('common.recycleBin.empty') }}
        </p>
        <p class="text-sm text-muted-foreground/60">
          {{ $t('common.recycleBin.emptyDesc') }}
        </p>
      </div>

      <!-- 有数据：Tab 切换模块 -->
      <Card v-else :bordered="false" class="h-full">
        <Tabs
          v-model:activeKey="activeModule"
          tab-position="left"
          :style="{ minHeight: '400px' }"
          @change="onTabChange"
        >
          <Tabs.TabPane
            v-for="mod in summary"
            :key="mod.module"
            :tab="mod.label"
          >
            <template #tab>
              <div class="flex items-center gap-2">
                <IconifyIcon
                  :icon="moduleIcons[mod.module] || 'lucide:box'"
                  class="size-4"
                />
                <span>{{ mod.label }}</span>
                <Badge
                  :count="mod.count"
                  :number-style="{ backgroundColor: '#faad14' }"
                  :overflow-count="999"
                />
              </div>
            </template>

            <!-- 高级搜索表单 -->
            <div class="mb-3">
              <SearchForm />
            </div>

            <!-- 保留天数提示 -->
            <div
              class="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground/70"
            >
              <IconifyIcon icon="lucide:info" class="size-3.5" />
              <span>{{
                $t('common.recycleBin.retentionDays', { days: 30 })
              }}</span>
            </div>

            <!-- 列表 -->
            <Table
              :columns="columns"
              :data-source="items"
              :loading="listLoading"
              :pagination="{
                current: currentPage,
                pageSize,
                total,
                showSizeChanger: true,
                showTotal: (t: number) => `${$t('admin.common.total')} ${t}`,
                onChange: onPageChange,
              }"
              row-key="id"
              size="small"
              :scroll="{ x: 800 }"
            >
              <template #bodyCell="{ column, record }">
                <!-- 租户名称 -->
                <template v-if="column.key === 'tenant_name'">
                  <Tag v-if="record.tenant_name" color="blue">
                    {{ record.tenant_name }}
                  </Tag>
                  <span v-else class="text-muted-foreground">—</span>
                </template>

                <!-- 删除层级 -->
                <template v-else-if="column.key === 'delete_level'">
                  <Tag
                    v-if="record.delete_level === 'admin'"
                    color="red"
                  >
                    {{ $t('admin.system.recycleBin.levelAdmin') }}
                  </Tag>
                  <Tag
                    v-else-if="record.delete_level === 'tenant'"
                    color="orange"
                  >
                    {{ $t('admin.system.recycleBin.levelTenant') }}
                  </Tag>
                  <span v-else class="text-muted-foreground">—</span>
                </template>

                <!-- 删除时间 -->
                <template v-else-if="column.key === 'deleted_at'">
                  <Tooltip :title="formatDate(record.deleted_at)">
                    <span class="text-muted-foreground">
                      {{ formatRelativeTime(record.deleted_at) }}
                    </span>
                  </Tooltip>
                </template>

                <!-- 操作 -->
                <template v-else-if="column.key === 'action'">
                  <Space>
                    <Tooltip :title="$t('common.recycleBin.restore')">
                      <Button
                        type="link"
                        size="small"
                        class="text-primary"
                        @click="handleRestore(record as RecycleBinItem)"
                      >
                        <template #icon>
                          <IconifyIcon
                            icon="lucide:rotate-ccw"
                            class="size-4"
                          />
                        </template>
                      </Button>
                    </Tooltip>
                    <Tooltip :title="$t('common.recycleBin.permanentDelete')">
                      <Button
                        type="link"
                        size="small"
                        danger
                        @click="
                          handlePermanentDelete(record as RecycleBinItem)
                        "
                      >
                        <template #icon>
                          <IconifyIcon icon="lucide:x" class="size-4" />
                        </template>
                      </Button>
                    </Tooltip>
                  </Space>
                </template>
              </template>

              <template #emptyText>
                <Empty :description="$t('common.recycleBin.empty')" />
              </template>
            </Table>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </Spin>
  </Page>
</template>
