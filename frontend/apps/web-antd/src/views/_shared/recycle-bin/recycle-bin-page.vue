<script lang="ts" setup>
import type { RecycleBinModuleAdapter, RecycleBinPageApi } from './types';

import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickParams } from '#/adapter/vxe-table';
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
  RecycleBinModuleSummary,
} from '#/api/shared/recycle-bin';

import { computed, nextTick, onMounted, ref, toRaw } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  message,
  Modal,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useGridSearchFormOptions, useVbenVxeGrid } from '#/adapter/vxe-table';
import { useExportModal } from '#/core/adapter/vxe-table/components';
import CrudGrid from '#/core/adapter/vxe-table/components/crud-grid.vue';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import {
  buildDynamicFilterSchema,
  buildRecycleColumns,
  buildSortOptions,
} from './data';

defineOptions({ name: 'SharedRecycleBinPage' });

const props = withDefaults(defineProps<Props>(), {
  moduleAdapters: () => ({}),
  showCleanup: false,
  tenantFieldSchema: null,
});

interface Props {
  api: RecycleBinPageApi;
  i18nPrefix: string;
  moduleAdapters?: Record<string, RecycleBinModuleAdapter>;
  showCleanup?: boolean;
  tenantFieldSchema?: ((fieldName: string) => VbenFormSchema) | null;
}

const configFetching = ref(true);
const summary = ref<RecycleBinModuleSummary[]>([]);
const moduleMeta = ref<Record<string, RecycleBinModuleMeta>>({});
const activeListModule = ref('');
const syncingModule = ref(false);
const lastSyncedRecycleModule = ref('');

const totalDeletedCount = computed(() =>
  summary.value.reduce((sum, item) => sum + item.count, 0),
);
const hasDeletedItems = computed(() => totalDeletedCount.value > 0);
const availableModuleCount = computed(
  () => Object.keys(moduleMeta.value).length,
);
const hasModuleConfig = computed(() => availableModuleCount.value > 0);
const activeModuleMeta = computed(
  () => moduleMeta.value[activeListModule.value] ?? null,
);
const activeModuleLabel = computed(
  () => activeModuleMeta.value?.label ?? activeListModule.value,
);
const activeModuleDeletedCount = computed(() => {
  const moduleCode = activeListModule.value;
  if (!moduleCode) return 0;
  return summary.value.find((item) => item.module === moduleCode)?.count ?? 0;
});
const moduleOptions = computed(() => {
  const countByModule = new Map(
    summary.value.map((item) => [item.module, item.count] as const),
  );
  return Object.keys(moduleMeta.value)
    .map((moduleCode) => {
      const meta = moduleMeta.value[moduleCode];
      return {
        label: meta?.label ?? moduleCode,
        module: moduleCode,
        count: countByModule.get(moduleCode) ?? 0,
      };
    })
    .toSorted(
      (left, right) =>
        right.count - left.count || left.label.localeCompare(right.label),
    );
});

function resolveAdapter(moduleCode: string) {
  return props.moduleAdapters?.[moduleCode];
}

function resolveDefaultSort(moduleCode: string) {
  return resolveAdapter(moduleCode)?.defaultSort ?? '-promoted_to_global_at';
}

function buildModuleSelectOptions() {
  return moduleOptions.value.map((item) => ({
    label: `${item.label} (${item.count})`,
    value: item.module,
  }));
}

function defaultModuleCode() {
  for (const item of summary.value) {
    if (item.module && moduleMeta.value[item.module]) {
      return item.module;
    }
  }
  return moduleOptions.value[0]?.module ?? '';
}

function moduleSelectProps() {
  return {
    allowClear: false,
    class: 'w-full',
    onChange: onModuleFieldChange,
    optionFilterProp: 'label',
    options: buildModuleSelectOptions(),
    showSearch: true,
  };
}

function sortSelectProps(moduleCode: string) {
  const options = buildSortOptions(
    moduleMeta.value[moduleCode] ?? null,
    resolveAdapter(moduleCode),
  );
  return {
    allowClear: false,
    class: 'w-full',
    options,
  };
}

function resolveSortValue(moduleCode: string, candidate?: string) {
  const options = buildSortOptions(
    moduleMeta.value[moduleCode] ?? null,
    resolveAdapter(moduleCode),
  );
  const values = new Set(options.map((item) => item.value));
  if (candidate && values.has(candidate)) {
    return candidate;
  }
  return resolveDefaultSort(moduleCode);
}

function buildFullSchema(moduleCode: string): VbenFormSchema[] {
  const meta = moduleCode ? (moduleMeta.value[moduleCode] ?? null) : null;
  return [
    {
      component: 'Select',
      componentProps: moduleSelectProps(),
      fieldName: 'module',
      formItemClass: 'hidden',
      label: $t(`${props.i18nPrefix}.modules`),
    },
    {
      component: 'Select',
      componentProps: sortSelectProps(moduleCode),
      fieldName: 'sort',
      label: $t(`${props.i18nPrefix}.sort`),
    },
    ...buildDynamicFilterSchema(meta, resolveAdapter(moduleCode), {
      includeTenantFilter: props.showCleanup,
      tenantFieldSchema: props.tenantFieldSchema,
    }),
  ];
}

async function syncSubmissionAndReload(page?: Record<string, unknown>) {
  const values = await gridApi.formApi?.getValues();
  if (values && gridApi.formApi?.setLatestSubmissionValues) {
    gridApi.formApi.setLatestSubmissionValues(toRaw(values));
  }
  await gridApi.reload(page ?? {});
}

function handleActionClick(e: OnActionClickParams<RecycleBinItem>) {
  const moduleCode = activeListModule.value;
  if (!moduleCode) return;
  if (e.code === 'restore') {
    void handleRestore(e.row, moduleCode);
    return;
  }
  if (e.code === 'delete') {
    handlePermanentDelete(e.row, moduleCode);
  }
}

async function handleRestore(row: RecycleBinItem, moduleCode: string) {
  try {
    await props.api.restore(moduleCode, row.id);
    message.success($t('common.recycleBin.restoreSuccess'));
    await refreshSummaryOnly();
    await patchModuleSelectOptions();
    await gridApi.query();
  } catch {
    //
  }
}

function handlePermanentDelete(row: RecycleBinItem, moduleCode: string) {
  const meta = moduleMeta.value[moduleCode];
  const labelField = meta?.label_field ?? 'name';
  const displayName = String(row[labelField] ?? row.id);
  Modal.confirm({
    title: $t('common.recycleBin.permanentDelete'),
    content: $t('common.recycleBin.confirmPermanentDelete', {
      name: displayName,
    }),
    okType: 'danger',
    onOk: async () => {
      await props.api.permanentDelete(moduleCode, row.id);
      message.success($t('common.recycleBin.deleteSuccess'));
      await refreshSummaryOnly();
      await patchModuleSelectOptions();
      await gridApi.query();
    },
  });
}

async function handleCleanup() {
  if (!props.api.triggerCleanup) return;
  try {
    await props.api.triggerCleanup();
    message.success($t(`${props.i18nPrefix}.cleanupTriggered`));
    await refreshSummaryOnly();
    await patchModuleSelectOptions();
    await gridApi.query();
  } catch {
    //
  }
}

function handleClearModule() {
  const moduleCode = activeListModule.value;
  if (!moduleCode) return;
  Modal.confirm({
    title: $t(`${props.i18nPrefix}.clearModule`),
    content: $t(`${props.i18nPrefix}.clearModuleConfirm`, {
      module: activeModuleLabel.value,
    }),
    okType: 'danger',
    onOk: async () => {
      const result = await props.api.clearModule(moduleCode);
      const count = result?.count ?? 0;
      message.success($t(`${props.i18nPrefix}.clearModuleSuccess`, { count }));
      await refreshSummaryOnly();
      await patchModuleSelectOptions();
      await syncSubmissionAndReload();
    },
  });
}

function onModuleFieldChange(moduleCode: string) {
  void applyModuleChange(moduleCode);
}

async function applyModuleChange(moduleCode: string) {
  if (!moduleCode || syncingModule.value) return;
  if (lastSyncedRecycleModule.value === moduleCode) return;
  syncingModule.value = true;
  try {
    const currentValues = await gridApi.formApi?.getValues();
    const currentSort = String(currentValues?.sort ?? '');
    const nextSort = resolveSortValue(moduleCode, currentSort || undefined);
    await gridApi.formApi?.setState({
      schema: buildFullSchema(moduleCode),
    });
    await nextTick();
    await gridApi.formApi?.setValues({
      module: moduleCode,
      sort: nextSort,
    });
    gridApi.setGridOptions({
      columns: buildRecycleColumns(
        moduleMeta.value[moduleCode] ?? null,
        resolveAdapter(moduleCode),
        handleActionClick,
        { includeTenantColumn: props.showCleanup },
      ),
    });
    lastSyncedRecycleModule.value = moduleCode;
    await syncSubmissionAndReload({ page: 1 });
  } finally {
    syncingModule.value = false;
  }
}

async function loadModuleMeta() {
  try {
    const result = await props.api.getModules();
    moduleMeta.value = result ?? {};
  } catch {
    moduleMeta.value = {};
  }
}

async function refreshSummaryOnly() {
  try {
    const result = await props.api.getSummary();
    summary.value = result ?? [];
  } catch {
    summary.value = [];
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: useGridSearchFormOptions(buildFullSchema('')),
  gridOptions: {
    cellConfig: { height: 56 },
    columns: buildRecycleColumns(null, null, handleActionClick, {
      includeTenantColumn: props.showCleanup,
    }),
    keepSource: true,
    pagerConfig: { enabled: true },
    proxyConfig: {
      ajax: {
        query: async (
          { page }: { page: { currentPage: number; pageSize: number } },
          formValues: Record<string, unknown>,
        ) => {
          const moduleCode = String(formValues?.module ?? '');
          activeListModule.value = moduleCode;
          if (!moduleCode) {
            return { items: [], total: 0 };
          }

          const params: Record<string, unknown> = {
            'page[number]': page.currentPage,
            'page[size]': page.pageSize,
            sort:
              String(formValues?.sort ?? '') || resolveDefaultSort(moduleCode),
          };
          for (const [key, value] of Object.entries(formValues ?? {})) {
            if (key === 'module' || key === 'sort') continue;
            if (value !== undefined && value !== null && value !== '') {
              params[key] = value;
            }
          }

          return props.api.getList(moduleCode, params);
        },
      },
    },
    rowConfig: { keyField: 'id' },
    stripe: true,
    toolbarConfig: {
      custom: true,
      export: false,
      refresh: false,
      search: true,
      zoom: true,
    },
  },
});

const { ExportModal, openExportModal } = useExportModal(() => gridApi?.grid);

async function patchModuleSelectOptions() {
  await gridApi.formApi?.updateSchema([
    {
      componentProps: {
        options: buildModuleSelectOptions(),
      },
      fieldName: 'module',
    },
  ]);
}

async function onToolbarRefresh() {
  await refreshSummaryOnly();
  await patchModuleSelectOptions();
  const values = await gridApi.formApi?.getValues();
  if (values && gridApi.formApi?.setLatestSubmissionValues) {
    gridApi.formApi.setLatestSubmissionValues(toRaw(values));
  }
  await gridApi.query();
}

async function bootstrapGridForm() {
  const first = defaultModuleCode();
  if (!first) return;
  await nextTick();
  await nextTick();
  await gridApi.formApi?.setState({
    schema: buildFullSchema(first),
  });
  await nextTick();
  await gridApi.formApi?.setValues({
    module: first,
    sort: resolveSortValue(first),
  });
  gridApi.setGridOptions({
    columns: buildRecycleColumns(
      moduleMeta.value[first] ?? null,
      resolveAdapter(first),
      handleActionClick,
      { includeTenantColumn: props.showCleanup },
    ),
  });
  lastSyncedRecycleModule.value = first;
  await syncSubmissionAndReload();
}

onMounted(async () => {
  try {
    await loadModuleMeta();
    await refreshSummaryOnly();
  } finally {
    configFetching.value = false;
  }
  if (!hasModuleConfig.value) return;
  await nextTick();
  await nextTick();
  await bootstrapGridForm();
});

function isActiveModule(moduleCode: string) {
  return activeListModule.value === moduleCode;
}

function formatEnumValue(value: unknown) {
  if (value === undefined || value === null || value === '') return '—';
  return String(value).replaceAll('_', ' ');
}

function getEnumTagColor(value: unknown) {
  const normalized = String(value ?? '').toLowerCase();
  if (
    normalized === 'active' ||
    normalized === 'enabled' ||
    normalized === 'published' ||
    normalized === 'public' ||
    normalized === 'success'
  ) {
    return 'success';
  }
  if (
    normalized === 'disabled' ||
    normalized === 'failed' ||
    normalized === 'error' ||
    normalized === 'private'
  ) {
    return 'error';
  }
  if (
    normalized === 'draft' ||
    normalized === 'pending' ||
    normalized === 'processing'
  ) {
    return 'warning';
  }
  return 'default';
}

function formatScheduleDisplay(row: RecycleBinItem) {
  if (row.schedule_type === 'cron') {
    return String(row.cron_expression || '—');
  }
  if (row.schedule_type === 'interval') {
    const seconds = Number(row.interval_seconds ?? 0);
    if (!seconds) return '—';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86_400)}d`;
  }
  return '—';
}

function hasDateValue(value: unknown) {
  return typeof value === 'string' && value.length > 0;
}
</script>

<template>
  <Page
    auto-content-height
    content-class="flex flex-col gap-4"
    :description="$t(`${i18nPrefix}.description`)"
  >
    <Card
      v-if="!configFetching && !hasModuleConfig"
      class="flex-1"
      :body-style="{ padding: '48px 16px' }"
    >
      <Empty :description="$t(`${i18nPrefix}.configUnavailable`)" />
    </Card>

    <Spin v-else-if="configFetching" class="block py-24" />

    <template v-else>
      <div
        class="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_repeat(2,minmax(0,0.8fr))]"
      >
        <Card
          class="relative overflow-hidden border-0 bg-gradient-to-br from-primary/15 via-primary/5 to-background shadow-none"
        >
          <div
            class="absolute -right-10 top-0 size-28 rounded-full bg-primary/10 blur-3xl"
          ></div>
          <div class="relative flex items-start gap-4">
            <div
              class="rounded-3xl bg-background/80 p-3 text-primary shadow-sm"
            >
              <IconifyIcon icon="lucide:archive" class="size-6" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="rounded-full bg-background/80 px-3 py-1 text-[11px] font-medium text-foreground/80"
                >
                  {{ $t('common.recycleBin.globalStageLabel') }}
                </span>
                <span
                  v-if="activeListModule"
                  class="rounded-full bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary"
                >
                  {{ activeModuleLabel }}
                </span>
              </div>
              <div class="mt-4 text-lg font-semibold text-foreground">
                {{ $t('common.recycleBin.globalTitle') }}
              </div>
              <div
                class="mt-2 max-w-3xl text-sm leading-7 text-muted-foreground"
              >
                {{ $t('common.recycleBin.twoStageHint', { days: 30 }) }}
              </div>
              <div
                class="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground"
              >
                <span class="rounded-full bg-background/80 px-3 py-1">
                  {{ $t('common.recycleBin.moduleStageLabel') }}
                </span>
                <span class="rounded-full bg-background/80 px-3 py-1">
                  {{ $t('common.recycleBin.globalStageLabel') }}
                </span>
              </div>
            </div>
          </div>
        </Card>

        <Card class="shadow-none">
          <div
            class="text-xs uppercase tracking-[0.24em] text-muted-foreground/80"
          >
            {{ $t('common.recycleBin.itemCountLabel') }}
          </div>
          <div class="mt-3 text-3xl font-semibold text-foreground">
            {{ totalDeletedCount }}
          </div>
          <div class="mt-3 text-xs leading-6 text-muted-foreground">
            {{ $t('common.recycleBin.restoreBeforeExpire') }}
          </div>
        </Card>

        <Card class="shadow-none">
          <div
            class="text-xs uppercase tracking-[0.24em] text-muted-foreground/80"
          >
            {{ $t(`${i18nPrefix}.modules`) }}
          </div>
          <div class="mt-3 text-3xl font-semibold text-foreground">
            {{ availableModuleCount }}
          </div>
          <div class="mt-3 text-xs leading-6 text-muted-foreground">
            {{
              activeListModule
                ? `${activeModuleLabel} · ${$t('common.recycleBin.itemCount', { count: activeModuleDeletedCount })}`
                : $t(`${i18nPrefix}.noModule`)
            }}
          </div>
        </Card>
      </div>

      <Card v-show="hasDeletedItems" class="shadow-none">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t(`${i18nPrefix}.modules`) }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{
                activeListModule
                  ? `${activeModuleLabel} · ${$t('common.recycleBin.itemCount', { count: activeModuleDeletedCount })}`
                  : $t(`${i18nPrefix}.noModule`)
              }}
            </div>
          </div>
          <div
            class="rounded-full bg-muted/60 px-3 py-1 text-xs text-muted-foreground"
          >
            {{ $t('common.recycleBin.restoreBeforeExpire') }}
          </div>
        </div>

        <div
          class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-5"
        >
          <button
            v-for="item in moduleOptions"
            :key="item.module"
            type="button"
            class="group rounded-2xl border px-4 py-3 text-left transition-all"
            :class="
              isActiveModule(item.module)
                ? 'border-primary/40 bg-primary/10 shadow-sm shadow-primary/10'
                : 'border-border/60 bg-background hover:border-primary/25 hover:bg-primary/5'
            "
            @click="applyModuleChange(item.module)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-foreground">
                  {{ item.label }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{ $t('common.recycleBin.itemCount', { count: item.count }) }}
                </div>
              </div>
              <div
                class="rounded-full px-2.5 py-1 text-xs font-medium"
                :class="
                  isActiveModule(item.module)
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                "
              >
                {{ item.count }}
              </div>
            </div>
          </button>
        </div>
      </Card>

      <Card
        v-if="!hasDeletedItems"
        class="overflow-hidden border-dashed shadow-none"
        :body-style="{ padding: '40px 24px' }"
      >
        <div class="flex flex-col items-center justify-center text-center">
          <div class="rounded-3xl bg-primary/10 p-4 text-primary">
            <IconifyIcon icon="lucide:archive-x" class="size-8" />
          </div>
          <div class="mt-5 text-xl font-semibold text-foreground">
            {{ $t('common.recycleBin.empty') }}
          </div>
          <div class="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
            {{ $t('common.recycleBin.twoStageHint', { days: 30 }) }}
          </div>
          <div
            class="mt-5 flex flex-wrap justify-center gap-2 text-xs text-muted-foreground"
          >
            <span class="rounded-full bg-muted px-3 py-1">
              {{ $t('common.recycleBin.moduleStageLabel') }}
            </span>
            <span class="rounded-full bg-muted px-3 py-1">
              {{ $t('common.recycleBin.globalStageLabel') }}
            </span>
          </div>
          <div class="mt-6 text-xs text-muted-foreground">
            {{ $t(`${i18nPrefix}.modules`) }} · {{ availableModuleCount }}
          </div>
        </div>
      </Card>

      <Card
        v-show="hasDeletedItems"
        class="flex-1 shadow-none"
        :body-style="{ padding: '16px', height: '100%' }"
      >
        <ExportModal />
        <CrudGrid
          :grid="Grid"
          :show-export="true"
          :on-export="openExportModal"
          :on-refresh="onToolbarRefresh"
        >
          <template #toolbar-tools>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <span
                class="rounded-full bg-muted/70 px-3 py-1 text-xs text-muted-foreground"
              >
                {{
                  activeListModule
                    ? `${activeModuleLabel} · ${$t('common.recycleBin.itemCount', { count: activeModuleDeletedCount })}`
                    : $t('common.recycleBin.restoreBeforeExpire')
                }}
              </span>
              <Popconfirm
                v-if="showCleanup && api.triggerCleanup"
                :title="$t(`${i18nPrefix}.cleanupConfirm`)"
                @confirm="handleCleanup"
              >
                <Button type="primary" danger size="small" class="!rounded-xl">
                  <IconifyIcon icon="lucide:flame" class="mr-1 size-3.5" />
                  {{ $t(`${i18nPrefix}.cleanup`) }}
                </Button>
              </Popconfirm>
              <Tooltip
                :title="
                  activeModuleDeletedCount <= 0
                    ? $t(`${i18nPrefix}.clearModuleDisabledTip`)
                    : ''
                "
              >
                <span class="inline-block">
                  <Button
                    danger
                    size="small"
                    class="!rounded-xl"
                    :disabled="activeModuleDeletedCount <= 0"
                    @click="handleClearModule"
                  >
                    <IconifyIcon icon="lucide:trash-2" class="mr-1 size-3.5" />
                    {{ $t(`${i18nPrefix}.clearModule`) }}
                  </Button>
                </span>
              </Tooltip>
            </div>
          </template>

          <template #tenant_name_cell="{ row }">
            <Tag
              v-if="row.tenant_name"
              color="blue"
              class="!rounded-md !border-0"
            >
              {{ row.tenant_name }}
            </Tag>
            <span v-else class="text-muted-foreground">—</span>
          </template>

          <template #status_cell="{ row }">
            <Tag :color="getEnumTagColor(row.status)">
              {{ formatEnumValue(row.status) }}
            </Tag>
          </template>

          <template #is_active_cell="{ row }">
            <Tag :color="row.is_active ? 'success' : 'error'">
              {{ row.is_active ? $t('common.enabled') : $t('common.disabled') }}
            </Tag>
          </template>

          <template #scope_cell="{ row }">
            <Tag color="blue">{{ formatEnumValue(row.scope) }}</Tag>
          </template>

          <template #visibility_cell="{ row }">
            <Tag :color="getEnumTagColor(row.visibility)">
              {{ formatEnumValue(row.visibility) }}
            </Tag>
          </template>

          <template #execution_mode_cell="{ row }">
            <Tag color="processing">
              {{ formatEnumValue(row.execution_mode) }}
            </Tag>
          </template>

          <template #type_cell="{ row }">
            <Tag color="purple">{{ formatEnumValue(row.type) }}</Tag>
          </template>

          <template #tier_cell="{ row }">
            <Tag color="gold">{{ formatEnumValue(row.tier) }}</Tag>
          </template>

          <template #billing_cycle_cell="{ row }">
            <Tag color="cyan">{{ formatEnumValue(row.billing_cycle) }}</Tag>
          </template>

          <template #schedule_cell="{ row }">
            <span class="text-muted-foreground">{{
              formatScheduleDisplay(row)
            }}</span>
          </template>

          <template #size_cell="{ row }">
            <span class="text-muted-foreground">
              {{ formatFileSize(Number(row.total_size_bytes ?? 0)) }}
            </span>
          </template>

          <template #created_at_cell="{ row }">
            <Tooltip
              v-if="hasDateValue(row.created_at)"
              :title="formatDate(row.created_at)"
            >
              <span class="text-muted-foreground">
                {{ formatRelativeTime(row.created_at) }}
              </span>
            </Tooltip>
            <span v-else class="text-muted-foreground">—</span>
          </template>

          <template #expires_at_cell="{ row }">
            <Tooltip
              v-if="hasDateValue(row.expires_at)"
              :title="formatDate(row.expires_at)"
            >
              <span class="text-muted-foreground">
                {{ formatRelativeTime(row.expires_at) }}
              </span>
            </Tooltip>
            <span v-else class="text-muted-foreground">—</span>
          </template>

          <template #promoted_to_global_at_cell="{ row }">
            <Tooltip
              v-if="hasDateValue(row.promoted_to_global_at)"
              :title="formatDate(row.promoted_to_global_at)"
            >
              <span class="text-muted-foreground">
                {{ formatRelativeTime(row.promoted_to_global_at) }}
              </span>
            </Tooltip>
            <span v-else class="text-muted-foreground">—</span>
          </template>

          <template #deleted_at_cell="{ row }">
            <Tooltip
              v-if="hasDateValue(row.deleted_at)"
              :title="formatDate(row.deleted_at)"
            >
              <span class="text-muted-foreground">
                {{ formatRelativeTime(row.deleted_at) }}
              </span>
            </Tooltip>
            <span v-else class="text-muted-foreground">—</span>
          </template>
        </CrudGrid>
      </Card>
    </template>
  </Page>
</template>
