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
  Button,
  message,
  Modal,
  Popconfirm,
  Spin,
  Table,
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
  <Page auto-content-height content-class="flex flex-col gap-5">
    <!-- ===== Hero 头部 ===== -->
    <div class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-destructive/5 via-background to-warning/3 p-6">
      <div class="relative z-10 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <div class="flex size-12 items-center justify-center rounded-xl bg-destructive/10">
            <IconifyIcon icon="lucide:trash-2" class="size-6 text-destructive" />
          </div>
          <div>
            <h1 class="text-xl font-bold text-foreground">{{ $t('admin.system.recycleBin.title') }}</h1>
            <p class="mt-0.5 text-sm text-muted-foreground">{{ $t('admin.system.recycleBin.description') }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div v-if="totalDeletedCount > 0" class="flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-1.5">
            <IconifyIcon icon="lucide:archive" class="size-4 text-warning" />
            <span class="text-sm font-medium text-warning">
              {{ $t('common.recycleBin.itemCount', { count: totalDeletedCount }) }}
            </span>
          </div>
          <Popconfirm
            :title="$t('admin.system.recycleBin.cleanupConfirm')"
            @confirm="handleCleanup"
          >
            <Button type="primary" danger class="!rounded-lg">
              <IconifyIcon icon="lucide:flame" class="mr-1.5 size-4" />
              {{ $t('admin.system.recycleBin.cleanup') }}
            </Button>
          </Popconfirm>
        </div>
      </div>
      <div class="absolute -right-12 -top-12 size-40 rounded-full bg-destructive/5 blur-3xl" />
    </div>

    <Spin :spinning="summaryLoading">
      <!-- 空状态 -->
      <div v-if="!summaryLoading && summary.length === 0" class="flex flex-col items-center justify-center gap-4 py-24">
        <div class="flex size-20 items-center justify-center rounded-2xl bg-muted">
          <IconifyIcon icon="lucide:check-circle" class="size-10 text-success/50" />
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-foreground">{{ $t('common.recycleBin.empty') }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ $t('common.recycleBin.emptyDesc') }}</p>
        </div>
      </div>

      <!-- ===== 主内容：左侧模块导航 + 右侧列表 ===== -->
      <div v-else class="flex gap-5" style="min-height: 500px;">
        <!-- 左侧模块导航 -->
        <div class="flex w-56 shrink-0 flex-col gap-1 rounded-2xl border border-border/50 bg-card p-3">
          <div class="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {{ $t('admin.system.recycleBin.modules') || 'Modules' }}
          </div>
          <button
            v-for="mod in summary"
            :key="mod.module"
            class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-200"
            :class="activeModule === mod.module
              ? 'bg-primary/10 text-primary shadow-sm'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="onTabChange(mod.module)"
          >
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="activeModule === mod.module ? 'bg-primary/15' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="moduleIcons[mod.module] || 'lucide:box'"
                class="size-4"
              />
            </div>
            <div class="min-w-0 flex-1">
              <span class="block truncate text-[13px] font-medium">{{ mod.label }}</span>
            </div>
            <span
              class="flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
              :class="activeModule === mod.module
                ? 'bg-primary/20 text-primary'
                : 'bg-muted text-muted-foreground'"
            >
              {{ mod.count }}
            </span>
          </button>
        </div>

        <!-- 右侧内容区 -->
        <div class="recycle-table-wrap min-w-0 flex-1">
          <!-- 搜索 + 提示（紧凑单行） -->
          <div class="mb-3 flex flex-wrap items-center gap-3">
            <div class="flex-1">
              <SearchForm />
            </div>
            <div class="flex shrink-0 items-center gap-1.5 text-[11px] text-muted-foreground">
              <IconifyIcon icon="lucide:clock" class="size-3" />
              <span>{{ $t('common.recycleBin.retentionDays', { days: 30 }) }}</span>
            </div>
          </div>

          <!-- 表格 -->
          <div class="overflow-hidden rounded-xl border border-border/40 bg-card">
            <Table
              :columns="columns"
              :data-source="items"
              :loading="listLoading"
              :pagination="{
                current: currentPage,
                pageSize,
                total,
                showSizeChanger: true,
                size: 'small',
                showTotal: (t: number) => `${$t('admin.common.total')} ${t}`,
                onChange: onPageChange,
              }"
              row-key="id"
              size="middle"
              :scroll="{ x: 800 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'tenant_name'">
                  <Tag v-if="record.tenant_name" color="blue" class="!rounded-md !border-0">
                    {{ record.tenant_name }}
                  </Tag>
                  <span v-else class="text-muted-foreground">—</span>
                </template>

                <template v-else-if="column.key === 'delete_level'">
                  <span
                    v-if="record.delete_level === 'admin'"
                    class="inline-flex items-center gap-1 rounded-md bg-destructive/10 px-2 py-0.5 text-[11px] font-medium text-destructive"
                  >
                    <IconifyIcon icon="lucide:shield" class="size-3" />
                    {{ $t('admin.system.recycleBin.levelAdmin') }}
                  </span>
                  <span
                    v-else-if="record.delete_level === 'tenant'"
                    class="inline-flex items-center gap-1 rounded-md bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning"
                  >
                    <IconifyIcon icon="lucide:building-2" class="size-3" />
                    {{ $t('admin.system.recycleBin.levelTenant') }}
                  </span>
                  <span v-else class="text-muted-foreground">—</span>
                </template>

                <template v-else-if="column.key === 'deleted_at'">
                  <Tooltip :title="formatDate(record.deleted_at)">
                    <span class="text-xs text-muted-foreground">
                      {{ formatRelativeTime(record.deleted_at) }}
                    </span>
                  </Tooltip>
                </template>

                <template v-else-if="column.key === 'action'">
                  <div class="flex items-center justify-center gap-1">
                    <Tooltip :title="$t('common.recycleBin.restore')">
                      <button
                        class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                        @click="handleRestore(record as RecycleBinItem)"
                      >
                        <IconifyIcon icon="lucide:rotate-ccw" class="size-4" />
                      </button>
                    </Tooltip>
                    <Tooltip :title="$t('common.recycleBin.permanentDelete')">
                      <button
                        class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        @click="handlePermanentDelete(record as RecycleBinItem)"
                      >
                        <IconifyIcon icon="lucide:x" class="size-4" />
                      </button>
                    </Tooltip>
                  </div>
                </template>
              </template>

              <template #emptyText>
                <div class="flex flex-col items-center gap-3 py-12">
                  <IconifyIcon icon="lucide:inbox" class="size-10 text-muted-foreground/30" />
                  <span class="text-sm text-muted-foreground">{{ $t('common.recycleBin.empty') }}</span>
                </div>
              </template>
            </Table>
          </div>
        </div>
      </div>
    </Spin>
  </Page>
</template>

<style scoped>
.recycle-table-wrap :deep(.ant-table-thead > tr > th) {
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  background: var(--ant-color-bg-layout);
}

.recycle-table-wrap :deep(.ant-table-tbody > tr > td) {
  padding: 10px 12px;
  font-size: 13px;
}

.recycle-table-wrap :deep(.ant-table-tbody > tr:hover > td) {
  background: hsl(var(--primary) / 0.03);
}

.recycle-table-wrap :deep(.ant-pagination) {
  padding: 10px 12px;
  margin: 0;
}
</style>
