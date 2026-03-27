<script lang="ts" setup>
import type { adminApi } from '#/api';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  message,
  Select,
  Skeleton,
  Spin,
  Tag,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  formatDuration,
  getBindingContextText,
  getEffectiveContextText,
  getOwnerContextText,
  getResultSummary,
  getRunKindText,
  getStatusColor,
  getTaskShortName,
  getTriggerSourceText,
} from './data';

defineOptions({ name: 'SystemTaskLogList' });

type TaskLogDetailInfo = adminApi.TaskLogDetailInfo;
type TaskLogInfo = adminApi.TaskLogInfo;
type TaskLogListView = adminApi.TaskLogListView;

const PAGE_SIZE = 30;

const activeView = ref<TaskLogListView>('execution');
const loading = ref(false);
const detailLoading = ref(false);
const loadingMore = ref(false);
const dashboardLoading = ref(false);

const keyword = ref('');
const queueKeyword = ref('');
const statusFilter = ref<string | undefined>(undefined);

const runs = ref<TaskLogInfo[]>([]);
const total = ref(0);
const currentPage = ref(1);
const selectedRunId = ref<null | number>(null);
const selectedRun = ref<null | TaskLogDetailInfo>(null);
const dashboard = ref({
  activeNow: 0,
  failed: 0,
  success: 0,
  total: 0,
});

const viewOptions = computed<Array<{ label: string; value: TaskLogListView }>>(
  () => [
    {
      label: $t('admin.system.taskLog.viewModes.execution'),
      value: 'execution',
    },
    {
      label: $t('admin.system.taskLog.viewModes.internal'),
      value: 'internal',
    },
    {
      label: $t('admin.system.taskLog.viewModes.all'),
      value: 'all',
    },
  ],
);

const statusOptions = computed(() => [
  { label: $t('admin.system.taskLog.status.pending'), value: 'pending' },
  { label: $t('admin.system.taskLog.status.running'), value: 'running' },
  { label: $t('admin.system.taskLog.status.success'), value: 'success' },
  { label: $t('admin.system.taskLog.status.failed'), value: 'failed' },
  { label: $t('admin.system.taskLog.status.retrying'), value: 'retrying' },
]);

const toolbarMetrics = computed(() => [
  {
    key: 'total',
    label: $t('admin.system.taskLog.summary.total'),
    value: String(dashboard.value.total),
  },
  {
    key: 'active',
    label: $t('admin.system.taskLog.summary.activeNow'),
    value: String(dashboard.value.activeNow),
  },
  {
    key: 'failed',
    label: $t('admin.system.taskLog.summary.failed'),
    value: String(dashboard.value.failed),
  },
  {
    key: 'success',
    label: $t('admin.system.taskLog.summary.success'),
    value: String(dashboard.value.success),
  },
]);

const toolbarChips = computed(() => {
  const chips = [
    {
      key: 'view',
      icon: 'lucide:layout-list',
      className: 'bg-sky-50 text-sky-700',
      text: `${$t('admin.system.taskLog.viewLabel')}: ${viewOptions.value.find((item) => item.value === activeView.value)?.label ?? activeView.value}`,
    },
  ];

  if (selectedRun.value) {
    chips.push(
      {
        key: 'binding',
        icon: 'lucide:link-2',
        className: 'bg-cyan-50 text-cyan-700',
        text: getBindingContextText(selectedRun.value.bindingId),
      },
      {
        key: 'status',
        icon: 'lucide:badge-check',
        className: 'bg-emerald-50 text-emerald-700',
        text: $t(`admin.system.taskLog.status.${selectedRun.value.status}`),
      },
    );
  }

  return chips;
});

const hasMore = computed(() => runs.value.length < total.value);

const selectedResultSummary = computed(() => {
  if (!selectedRun.value) return null;
  return getResultSummary(selectedRun.value);
});

function buildListParams(page: number) {
  const params: Record<string, unknown> = {
    view: activeView.value,
    'page[number]': page,
    'page[size]': PAGE_SIZE,
    sort: '-created_at',
  };

  if (keyword.value.trim()) {
    params.task_name = keyword.value.trim();
  }
  if (queueKeyword.value.trim()) {
    params.queue = queueKeyword.value.trim();
  }
  if (statusFilter.value) {
    params['filter[status][eq]'] = statusFilter.value;
  }

  return params;
}

async function loadDashboard() {
  dashboardLoading.value = true;
  try {
    const [stats, activeTasks, latestRuns] = await Promise.all([
      admin.getTaskStatsApi(7),
      admin.getActiveTasksApi(),
      admin.getTaskLogListApi(buildListParams(1)),
    ]);
    const statsMap = new Map(stats.map((item) => [item.status, item.count]));
    dashboard.value = {
      activeNow: activeTasks.length,
      failed: statsMap.get('failed') ?? 0,
      success: statsMap.get('success') ?? 0,
      total: latestRuns.total,
    };
  } finally {
    dashboardLoading.value = false;
  }
}

async function loadDetail(id: number) {
  detailLoading.value = true;
  try {
    selectedRun.value = await admin.getTaskLogDetailApi(id);
    selectedRunId.value = id;
  } finally {
    detailLoading.value = false;
  }
}

async function loadRuns(nextPage = false) {
  const targetPage = nextPage ? currentPage.value + 1 : 1;
  if (nextPage) {
    loadingMore.value = true;
  } else {
    loading.value = true;
  }

  try {
    const response = await admin.getTaskLogListApi(buildListParams(targetPage));
    runs.value = nextPage ? [...runs.value, ...response.items] : response.items;
    total.value = response.total;
    currentPage.value = targetPage;

    if (runs.value.length === 0) {
      selectedRunId.value = null;
      selectedRun.value = null;
      return;
    }

    const stillVisible = runs.value.some(
      (item) => item.id === selectedRunId.value,
    );
    const firstRun = runs.value[0];
    if (!stillVisible && firstRun) {
      await loadDetail(firstRun.id);
    }
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

async function onRefresh() {
  await Promise.all([loadDashboard(), loadRuns(false)]);
}

async function onLoadMore() {
  if (hasMore.value) {
    await loadRuns(true);
  }
}

async function onRetryTask() {
  if (!selectedRun.value) return;
  try {
    await admin.retryTaskApi(selectedRun.value.id);
    message.success($t('admin.system.taskLog.messages.retrySuccess'));
    await onRefresh();
  } catch {
    // handled by interceptor
  }
}

watch(activeView, () => {
  void onRefresh();
});

onMounted(() => {
  void onRefresh();
});
</script>

<template>
  <Page auto-content-height content-class="flex min-h-0 flex-col gap-4 !p-4">
    <section
      class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
    >
      <div
        class="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:list-checks" class="size-4" />
            </span>
            <h1 class="text-base font-semibold text-foreground">
              {{ $t('admin.system.taskLog.title') }}
            </h1>
            <span class="hidden text-xs text-muted-foreground xl:inline">
              {{ $t('admin.system.taskLog.heroDescription') }}
            </span>
          </div>

          <div class="mt-2 flex flex-wrap gap-2">
            <span
              v-for="chip in toolbarChips"
              :key="chip.key"
              class="inline-flex max-w-full items-center gap-2 rounded-full border border-transparent px-2.5 py-1 text-xs"
              :class="chip.className"
            >
              <IconifyIcon :icon="chip.icon" class="size-3.5 flex-shrink-0" />
              <span class="max-w-[220px] truncate">{{ chip.text }}</span>
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-3 xl:flex-row xl:items-center">
          <Spin :spinning="dashboardLoading">
            <div class="flex flex-wrap gap-2">
              <span
                v-for="metric in toolbarMetrics"
                :key="metric.key"
                class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
              >
                <span class="mr-1 font-semibold text-foreground">
                  {{ metric.value }}
                </span>
                {{ metric.label }}
              </span>
            </div>
          </Spin>

          <div class="flex flex-wrap items-center gap-2">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="view in viewOptions"
                :key="view.value"
                type="button"
                class="inline-flex h-9 items-center gap-2 rounded-full border px-3.5 text-[13px] font-medium transition-colors"
                :class="
                  activeView === view.value
                    ? 'border-primary/25 bg-primary/10 text-primary'
                    : 'border-border/60 bg-background/85 text-foreground hover:border-primary/20 hover:text-primary'
                "
                @click="activeView = view.value"
              >
                <IconifyIcon
                  :icon="
                    view.value === 'execution'
                      ? 'lucide:activity'
                      : view.value === 'internal'
                        ? 'lucide:cpu'
                        : 'lucide:layers-3'
                  "
                  class="size-4"
                />
                {{ view.label }}
              </button>
            </div>
            <button
              type="button"
              class="inline-flex h-9 items-center gap-2 rounded-full bg-primary px-3.5 text-[13px] font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              @click="void onRefresh()"
            >
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
              {{ $t('common.refresh') }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section
      class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]"
    >
      <aside
        class="flex min-h-0 flex-col rounded-[20px] border border-border/70 bg-card p-3 shadow-sm"
      >
        <div class="flex items-center justify-between gap-2">
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t('admin.system.taskLog.list') }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ total }}
            </div>
          </div>
        </div>

        <div class="mt-3 grid gap-2">
          <Input
            v-model:value="keyword"
            :placeholder="$t('admin.system.taskLog.placeholder.searchTaskName')"
            @press-enter="void onRefresh()"
          />
          <div class="grid gap-2 sm:grid-cols-2">
            <Select
              v-model:value="statusFilter"
              allow-clear
              :options="statusOptions"
              :placeholder="$t('admin.system.taskLog.placeholder.allStatus')"
              @change="() => void onRefresh()"
            />
            <Input
              v-model:value="queueKeyword"
              :placeholder="$t('admin.system.taskLog.placeholder.searchQueue')"
              @press-enter="void onRefresh()"
            />
          </div>
        </div>

        <div class="mt-3 min-h-0 flex-1 overflow-auto">
          <Spin :spinning="loading">
            <div v-if="loading && runs.length === 0" class="space-y-3">
              <div
                v-for="item in 4"
                :key="item"
                class="rounded-2xl border border-border/60 bg-background/80 p-4"
              >
                <Skeleton active :paragraph="{ rows: 2 }" :title="false" />
              </div>
            </div>

            <div
              v-else-if="runs.length === 0"
              class="flex h-full items-center justify-center"
            >
              <Empty :description="$t('admin.system.taskLog.list')" />
            </div>

            <div v-else class="space-y-3">
              <article
                v-for="run in runs"
                :key="run.id"
                class="cursor-pointer rounded-2xl border p-4 transition-colors"
                :class="
                  selectedRunId === run.id
                    ? 'border-primary/25 bg-primary/10'
                    : 'border-border/60 bg-background/80 hover:border-primary/20'
                "
                @click="void loadDetail(run.id)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold text-foreground">
                      {{ getTaskShortName(run.handlerPath || run.taskName) }}
                    </div>
                    <div class="mt-1 truncate text-xs text-muted-foreground">
                      {{ run.handlerPath || run.taskName }}
                    </div>
                  </div>
                  <Tag :color="getStatusColor(run.status)" class="!m-0">
                    {{ $t(`admin.system.taskLog.status.${run.status}`) }}
                  </Tag>
                </div>

                <div class="mt-3 flex flex-wrap gap-1">
                  <Tag v-if="run.runKind" color="blue" class="!m-0">
                    {{ getRunKindText(run.runKind) }}
                  </Tag>
                  <Tag v-if="run.triggerSource" color="cyan" class="!m-0">
                    {{ getTriggerSourceText(run.triggerSource) }}
                  </Tag>
                  <Tag v-if="run.bindingId" color="gold" class="!m-0">
                    {{ getBindingContextText(run.bindingId) }}
                  </Tag>
                </div>

                <div
                  class="mt-3 flex items-center justify-between text-xs text-muted-foreground"
                >
                  <span>{{ formatDuration(run.durationMs) }}</span>
                  <span>{{ formatDate(run.createdAt, 'MM-DD HH:mm') }}</span>
                </div>
              </article>

              <Button
                v-if="hasMore"
                block
                :loading="loadingMore"
                @click="void onLoadMore()"
              >
                {{ $t('common.loadMore') }}
              </Button>
            </div>
          </Spin>
        </div>
      </aside>

      <section
        class="flex min-h-0 flex-col rounded-[20px] border border-border/70 bg-card p-4 shadow-sm"
      >
        <Spin :spinning="detailLoading">
          <div
            v-if="!selectedRun"
            class="flex min-h-[360px] items-center justify-center"
          >
            <Empty :description="$t('admin.system.taskLog.detail')" />
          </div>

          <template v-else>
            <div
              class="rounded-2xl border border-border/70 bg-background/70 p-4"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-lg font-semibold text-foreground">
                    {{ selectedRun.taskName }}
                  </div>
                  <div class="mt-1 break-all text-xs text-muted-foreground">
                    {{ selectedRun.handlerPath || selectedRun.taskId }}
                  </div>
                </div>

                <div class="flex flex-wrap gap-2">
                  <Tag :color="getStatusColor(selectedRun.status)">
                    {{
                      $t(`admin.system.taskLog.status.${selectedRun.status}`)
                    }}
                  </Tag>
                  <Tag v-if="selectedRun.runKind" color="blue">
                    {{ getRunKindText(selectedRun.runKind) }}
                  </Tag>
                  <Tag v-if="selectedRun.triggerSource" color="cyan">
                    {{ getTriggerSourceText(selectedRun.triggerSource) }}
                  </Tag>
                  <Button
                    v-if="selectedRun.status === 'failed'"
                    size="small"
                    @click="void onRetryTask()"
                  >
                    {{ $t('admin.system.taskLog.retry') }}
                  </Button>
                </div>
              </div>
            </div>

            <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div class="space-y-4">
                <section
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-2 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.resultInfo') }}
                  </div>
                  <div
                    v-if="selectedResultSummary"
                    class="text-sm"
                    :class="
                      selectedResultSummary.type === 'error'
                        ? 'text-destructive'
                        : selectedResultSummary.type === 'success'
                          ? 'text-success'
                          : 'text-muted-foreground'
                    "
                  >
                    {{ selectedResultSummary.text }}
                  </div>
                  <div v-else class="text-sm text-muted-foreground">-</div>
                </section>

                <section
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-2 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.result') }}
                  </div>
                  <pre
                    class="m-0 max-h-[220px] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-accent p-3 text-xs"
                    >{{
                      selectedRun.result
                        ? JSON.stringify(selectedRun.result, null, 2)
                        : '-'
                    }}</pre
                  >
                </section>

                <section
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-2 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.paramsInfo') }}
                  </div>
                  <div class="grid gap-3 xl:grid-cols-2">
                    <div>
                      <div
                        class="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground"
                      >
                        {{ $t('admin.system.taskLog.args') }}
                      </div>
                      <pre
                        class="m-0 max-h-[180px] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-accent p-3 text-xs"
                        >{{
                          selectedRun.args
                            ? JSON.stringify(selectedRun.args, null, 2)
                            : '-'
                        }}</pre
                      >
                    </div>
                    <div>
                      <div
                        class="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground"
                      >
                        {{ $t('admin.system.taskLog.kwargs') }}
                      </div>
                      <pre
                        class="m-0 max-h-[180px] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-accent p-3 text-xs"
                        >{{
                          selectedRun.kwargs
                            ? JSON.stringify(selectedRun.kwargs, null, 2)
                            : '-'
                        }}</pre
                      >
                    </div>
                  </div>
                </section>

                <section
                  v-if="selectedRun.traceback"
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-2 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.traceback') }}
                  </div>
                  <pre
                    class="m-0 max-h-[260px] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-destructive/5 p-3 text-xs text-destructive"
                    >{{ selectedRun.traceback }}</pre
                  >
                </section>
              </div>

              <div class="space-y-4">
                <section
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-3 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.relationInfo') }}
                  </div>
                  <div class="space-y-2 text-sm text-muted-foreground">
                    <div>
                      {{ $t('admin.system.taskLog.taskDefinitionId') }}:
                      <span class="font-medium text-foreground">
                        {{ selectedRun.taskDefinitionId ?? '-' }}
                      </span>
                    </div>
                    <div>
                      {{ $t('admin.system.taskLog.bindingId') }}:
                      <span class="font-medium text-foreground">
                        {{ getBindingContextText(selectedRun.bindingId) }}
                      </span>
                    </div>
                    <div>
                      {{ $t('admin.system.taskLog.ownerTenantId') }}:
                      <span class="font-medium text-foreground">
                        {{ getOwnerContextText(selectedRun.ownerTenantId) }}
                      </span>
                    </div>
                    <div>
                      {{ $t('admin.system.taskLog.effectiveTenantId') }}:
                      <span class="font-medium text-foreground">
                        {{
                          getEffectiveContextText(selectedRun.effectiveTenantId)
                        }}
                      </span>
                    </div>
                  </div>
                </section>

                <section
                  class="rounded-2xl border border-border/70 bg-background/70 p-4"
                >
                  <div class="mb-3 text-sm font-medium text-foreground">
                    {{ $t('admin.system.taskLog.timeInfo') }}
                  </div>
                  <div class="space-y-2 text-sm text-muted-foreground">
                    <div>
                      {{ $t('admin.system.taskLog.createdAt') }}:
                      <span class="font-medium text-foreground">
                        {{ formatDate(selectedRun.createdAt) }}
                      </span>
                    </div>
                    <div>
                      {{ $t('admin.system.taskLog.startedAt') }}:
                      <span class="font-medium text-foreground">
                        {{
                          selectedRun.startedAt
                            ? formatDate(selectedRun.startedAt)
                            : '-'
                        }}
                      </span>
                    </div>
                    <div>
                      {{ $t('admin.system.taskLog.finishedAt') }}:
                      <span class="font-medium text-foreground">
                        {{
                          selectedRun.finishedAt
                            ? formatDate(selectedRun.finishedAt)
                            : '-'
                        }}
                      </span>
                    </div>
                    <div v-if="selectedRun.traceId">
                      {{ $t('admin.system.taskLog.traceId') }}:
                      <span class="break-all font-medium text-foreground">
                        {{ selectedRun.traceId }}
                      </span>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </template>
        </Spin>
      </section>
    </section>
  </Page>
</template>
