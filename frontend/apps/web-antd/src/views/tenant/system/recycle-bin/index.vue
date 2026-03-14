<script lang="ts" setup>
import type {
  TenantRecycleBinItem,
  TenantRecycleBinModuleMeta,
  TenantRecycleBinModuleSummary,
} from '#/api/tenant/recycle-bin';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { message, Modal, Spin, Table, Tooltip } from 'ant-design-vue';

import {
  escalateTenantRecycleBinItemApi,
  getTenantRecycleBinListApi,
  getTenantRecycleBinModulesApi,
  getTenantRecycleBinSummaryApi,
  restoreTenantRecycleBinItemApi,
} from '#/api/tenant/recycle-bin';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

defineOptions({ name: 'TenantSystemRecycleBin' });

const summaryLoading = ref(false);
const listLoading = ref(false);
const summary = ref<TenantRecycleBinModuleSummary[]>([]);
const moduleMeta = ref<Record<string, TenantRecycleBinModuleMeta>>({});
const activeModule = ref('');
const items = ref<TenantRecycleBinItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);

const totalDeletedCount = computed(() =>
  summary.value.reduce((sum, m) => sum + m.count, 0),
);

const currentMeta = computed(
  () => moduleMeta.value[activeModule.value] ?? null,
);

const moduleIcons: Record<string, string> = {
  agents: 'lucide:bot',
  knowledge_bases: 'lucide:book-open',
  periodic_tasks: 'lucide:timer',
};

async function loadModuleMeta() {
  try {
    const res = await getTenantRecycleBinModulesApi();
    moduleMeta.value = res ?? {};
  } catch {
    moduleMeta.value = {};
  }
}

async function loadSummary() {
  summaryLoading.value = true;
  try {
    const res = await getTenantRecycleBinSummaryApi();
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
    const res = await getTenantRecycleBinListApi(activeModule.value, params);
    items.value = res?.items ?? [];
    total.value = res?.total ?? 0;
  } catch {
    items.value = [];
    total.value = 0;
  } finally {
    listLoading.value = false;
  }
}

async function handleRestore(record: TenantRecycleBinItem) {
  try {
    await restoreTenantRecycleBinItemApi(activeModule.value, record.id);
    message.success($t('common.recycleBin.restoreSuccess'));
    await loadList();
    await loadSummary();
  } catch {
    // handled by interceptor
  }
}

function handleEscalate(record: TenantRecycleBinItem) {
  const meta = currentMeta.value;
  const labelField = meta?.label_field ?? 'name';
  const displayName = String(record[labelField] ?? record.id);
  Modal.confirm({
    title: $t('common.recycleBin.escalate'),
    content: $t('common.recycleBin.confirmEscalate', { name: displayName }),
    okType: 'danger',
    onOk: async () => {
      await escalateTenantRecycleBinItemApi(activeModule.value, record.id);
      message.success($t('common.recycleBin.escalateSuccess'));
      await loadList();
      await loadSummary();
    },
  });
}

async function onTabChange(key: number | string) {
  activeModule.value = String(key);
  currentPage.value = 1;
  await loadList();
}

function onPageChange(p: number, ps: number) {
  currentPage.value = p;
  pageSize.value = ps;
  loadList();
}

const columns = computed(() => {
  const meta = currentMeta.value;
  const cols: Record<string, unknown>[] = [];

  if (meta) {
    for (const field of meta.columns) {
      cols.push({
        title: field,
        dataIndex: field,
        key: field,
        ellipsis: true,
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

  cols.push(
    {
      title: $t('common.recycleBin.deletedAt'),
      dataIndex: 'deleted_at',
      key: 'deleted_at',
      width: 180,
    },
    {
      title: $t('common.operation'),
      key: 'action',
      width: 120,
      align: 'center' as const,
      fixed: 'right' as const,
    },
  );

  return cols;
});

onMounted(async () => {
  await loadModuleMeta();
  await loadSummary();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-5">
    <!-- Hero header -->
    <div
      class="to-warning/3 relative overflow-hidden rounded-2xl bg-gradient-to-br from-destructive/5 via-background p-6"
    >
      <div
        class="relative z-10 flex flex-wrap items-center justify-between gap-4"
      >
        <div class="flex items-center gap-4">
          <div
            class="flex size-12 items-center justify-center rounded-xl bg-destructive/10"
          >
            <IconifyIcon
              icon="lucide:trash-2"
              class="size-6 text-destructive"
            />
          </div>
          <div>
            <h1 class="text-xl font-bold text-foreground">
              {{ $t('common.recycleBin.title') }}
            </h1>
            <p class="mt-0.5 text-sm text-muted-foreground">
              {{ $t('common.recycleBin.retentionDays', { days: 30 }) }}
              · {{ $t('common.recycleBin.escalateHint') }}
            </p>
          </div>
        </div>
        <div
          v-if="totalDeletedCount > 0"
          class="flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-1.5"
        >
          <IconifyIcon icon="lucide:archive" class="size-4 text-warning" />
          <span class="text-sm font-medium text-warning">
            {{
              $t('common.recycleBin.itemCount', { count: totalDeletedCount })
            }}
          </span>
        </div>
      </div>
      <div
        class="absolute -right-12 -top-12 size-40 rounded-full bg-destructive/5 blur-3xl"
      ></div>
    </div>

    <Spin :spinning="summaryLoading">
      <div
        v-if="!summaryLoading && summary.length === 0"
        class="flex flex-col items-center justify-center gap-4 py-24"
      >
        <div
          class="flex size-20 items-center justify-center rounded-2xl bg-muted"
        >
          <IconifyIcon
            icon="lucide:check-circle"
            class="size-10 text-success/50"
          />
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-foreground">
            {{ $t('common.recycleBin.empty') }}
          </p>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ $t('common.recycleBin.emptyDesc') }}
          </p>
        </div>
      </div>

      <div v-else class="flex gap-5" style="min-height: 500px">
        <!-- Left module nav -->
        <div
          class="flex w-56 shrink-0 flex-col gap-1 rounded-2xl border border-border/50 bg-card p-3"
        >
          <button
            v-for="mod in summary"
            :key="mod.module"
            class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-200"
            :class="
              activeModule === mod.module
                ? 'bg-primary/10 text-primary shadow-sm'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            "
            @click="onTabChange(mod.module)"
          >
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="
                activeModule === mod.module ? 'bg-primary/15' : 'bg-muted'
              "
            >
              <IconifyIcon
                :icon="moduleIcons[mod.module] || 'lucide:box'"
                class="size-4"
              />
            </div>
            <div class="min-w-0 flex-1">
              <span class="block truncate text-[13px] font-medium">{{
                mod.label
              }}</span>
            </div>
            <span
              class="flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
              :class="
                activeModule === mod.module
                  ? 'bg-primary/20 text-primary'
                  : 'bg-muted text-muted-foreground'
              "
            >
              {{ mod.count }}
            </span>
          </button>
        </div>

        <!-- Right content area -->
        <div class="recycle-table-wrap min-w-0 flex-1">
          <div
            class="overflow-hidden rounded-xl border border-border/40 bg-card"
          >
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
                onChange: onPageChange,
              }"
              row-key="id"
              size="middle"
              :scroll="{ x: 600 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'deleted_at'">
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
                        @click="
                          handleRestore(record as TenantRecycleBinItem)
                        "
                      >
                        <IconifyIcon icon="lucide:rotate-ccw" class="size-4" />
                      </button>
                    </Tooltip>
                    <Tooltip :title="$t('common.recycleBin.escalate')">
                      <button
                        class="flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        @click="
                          handleEscalate(record as TenantRecycleBinItem)
                        "
                      >
                        <IconifyIcon icon="lucide:x" class="size-4" />
                      </button>
                    </Tooltip>
                  </div>
                </template>
              </template>

              <template #emptyText>
                <div class="flex flex-col items-center gap-3 py-12">
                  <IconifyIcon
                    icon="lucide:inbox"
                    class="size-10 text-muted-foreground/30"
                  />
                  <span class="text-sm text-muted-foreground">{{
                    $t('common.recycleBin.empty')
                  }}</span>
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
  background: hsl(var(--primary) / 3%);
}

.recycle-table-wrap :deep(.ant-pagination) {
  padding: 10px 12px;
  margin: 0;
}
</style>
