<script lang="ts" setup>
/**
 * Admin global recycle bin — standard declarative grid (VxeGrid + CrudGrid)
 * 管理端总回收站 — 系统标准声明式表格
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickParams } from '#/adapter/vxe-table';
import type {
  RecycleBinItem,
  RecycleBinModuleMeta,
  RecycleBinModuleSummary,
} from '#/api/admin/recycle-bin';

import { computed, nextTick, onMounted, onUnmounted, ref, toRaw } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

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

import {
  useGridSearchFormOptions,
  useVbenVxeGrid,
} from '#/adapter/vxe-table';
import CrudGrid from '#/core/adapter/vxe-table/components/crud-grid.vue';
import { useExportModal } from '#/core/adapter/vxe-table/components';
import {
  clearRecycleBinModuleApi,
  getRecycleBinListApi,
  getRecycleBinModulesApi,
  getRecycleBinSummaryApi,
  permanentDeleteRecycleBinItemApi,
  restoreRecycleBinItemApi,
  triggerRecycleBinCleanupApi,
} from '#/api/admin/recycle-bin';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { buildDynamicFilterSchema, buildRecycleColumns } from './data';

defineOptions({ name: 'AdminSystemRecycleBin' });

/** 仅表示正在拉取 /modules + /summary；须先于表格挂载结束，再在已挂载的 form 上 setValues */
const configFetching = ref(true);
const summary = ref<RecycleBinModuleSummary[]>([]);
const moduleMeta = ref<Record<string, RecycleBinModuleMeta>>({});
const totalDeletedCount = computed(() =>
  summary.value.reduce((sum, m) => sum + m.count, 0),
);
const hasModuleConfig = computed(
  () => Object.keys(moduleMeta.value).length > 0,
);

function sortedModuleCodes(): string[] {
  return Object.keys(moduleMeta.value).sort();
}

/** 默认选中：优先 summary 首项（与后端顺序一致），否则字典序首模块 */
function defaultModuleCode(): string {
  for (const row of summary.value) {
    if (row.module && moduleMeta.value[row.module]) {
      return row.module;
    }
  }
  const codes = sortedModuleCodes();
  return codes[0] ?? '';
}

/** 下拉选项：以 /modules 为准，条数来自 /summary（空回收站时 summary 可能为 []） */
function buildModuleSelectOptions() {
  const countBy = new Map(
    summary.value.map((s) => [s.module, s.count] as const),
  );
  return sortedModuleCodes().map((code) => {
    const meta = moduleMeta.value[code];
    const label = meta?.label ?? code;
    const c = countBy.get(code) ?? 0;
    return { label: `${label} (${c})`, value: code };
  });
}
/** Current list API module (synced on each query) / 与列表请求一致的模块 */
const activeListModule = ref('');

/** 当前列表模块在 summary 中的条数（用于禁用「清空当前模块」） */
const activeModuleDeletedCount = computed(() => {
  const mod = activeListModule.value;
  if (!mod) return 0;
  return summary.value.find((s) => s.module === mod)?.count ?? 0;
});

const syncingModule = ref(false);
/** 已与表格列/动态搜索 schema 对齐的模块（不能再用 form.module===newMod 判断，否则会与 submitOnChange 竞态） */
const lastSyncedRecycleModule = ref('');

/** Vxe 代理查询读 getLatestSubmissionValues，程序化 setValues 后需同步 */
async function syncSubmissionAndReload(page?: Record<string, unknown>) {
  const v = await gridApi.formApi?.getValues();
  if (v && gridApi.formApi?.setLatestSubmissionValues) {
    gridApi.formApi.setLatestSubmissionValues(toRaw(v));
  }
  await gridApi.reload(page ?? {});
}

function handleActionClick(e: OnActionClickParams<RecycleBinItem>) {
  const mod = activeListModule.value;
  if (!mod) return;
  if (e.code === 'restore') {
    void handleRestore(e.row, mod);
  } else if (e.code === 'delete') {
    handlePermanentDelete(e.row, mod);
  }
}

async function handleRestore(row: RecycleBinItem, module: string) {
  try {
    await restoreRecycleBinItemApi(module, row.id);
    message.success($t('common.recycleBin.restoreSuccess'));
    await refreshSummaryOnly();
    await patchModuleSelectOptions();
    await gridApi.query();
  } catch {
    //
  }
}

function handlePermanentDelete(row: RecycleBinItem, module: string) {
  const meta = moduleMeta.value[module];
  const labelField = meta?.label_field ?? 'name';
  const displayName = String(row[labelField] ?? row.id);
  Modal.confirm({
    title: $t('common.recycleBin.permanentDelete'),
    content: $t('common.recycleBin.confirmPermanentDelete', {
      name: displayName,
    }),
    okType: 'danger',
    onOk: async () => {
      await permanentDeleteRecycleBinItemApi(module, row.id);
      message.success($t('common.recycleBin.deleteSuccess'));
      await refreshSummaryOnly();
      await patchModuleSelectOptions();
      await gridApi.query();
    },
  });
}

async function handleCleanup() {
  try {
    await triggerRecycleBinCleanupApi(30);
    message.success($t('admin.system.recycleBin.cleanupTriggered'));
    await refreshSummaryOnly();
    await patchModuleSelectOptions();
    await gridApi.query();
  } catch {
    //
  }
}

function handleClearModule() {
  const mod = activeListModule.value;
  if (!mod) return;
  const currentSummary = summary.value.find((s) => s.module === mod);
  const moduleName = currentSummary?.label ?? mod;
  Modal.confirm({
    title: $t('admin.system.recycleBin.clearModule'),
    content: $t('admin.system.recycleBin.clearModuleConfirm', {
      module: moduleName,
    }),
    okType: 'danger',
    onOk: async () => {
      const res = await clearRecycleBinModuleApi(mod);
      const count = res?.count ?? 0;
      message.success(
        $t('admin.system.recycleBin.clearModuleSuccess', { count }),
      );
      await refreshSummaryOnly();
      await patchModuleSelectOptions();
      await syncSubmissionAndReload();
    },
  });
}

function onModuleFieldChange(v: string) {
  void applyModuleChange(v);
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

function deleteLevelProps() {
  return {
    allowClear: false,
    class: 'w-full',
    options: [
      { label: $t('admin.system.recycleBin.levelAll'), value: 'all' },
      { label: $t('admin.system.recycleBin.levelAdmin'), value: 'admin' },
      { label: $t('admin.system.recycleBin.levelTenant'), value: 'tenant' },
    ],
  };
}

function buildFullSchema(activeMod: string): VbenFormSchema[] {
  const meta = activeMod ? (moduleMeta.value[activeMod] ?? null) : null;
  return [
    {
      component: 'Select',
      componentProps: moduleSelectProps(),
      fieldName: 'module',
      label: $t('admin.system.recycleBin.modules'),
    },
    {
      component: 'Select',
      componentProps: deleteLevelProps(),
      fieldName: 'delete_level',
      label: $t('admin.system.recycleBin.deleteSource'),
    },
    ...buildDynamicFilterSchema(meta, activeMod),
  ];
}

async function applyModuleChange(newMod: string) {
  if (!newMod || syncingModule.value) return;
  // submitOnChange 可能先于本 handler 把 module 写入表单，若此时用 getValues().module 对比会误判「未变化」而跳过列/schema 更新
  if (lastSyncedRecycleModule.value === newMod) return;
  syncingModule.value = true;
  try {
    const prevDl =
      (await gridApi.formApi?.getValues())?.delete_level ?? 'all';
    await gridApi.formApi?.setState({
      schema: buildFullSchema(newMod),
    });
    await nextTick();
    await gridApi.formApi?.setValues({
      delete_level: prevDl,
      module: newMod,
    });
    gridApi.setGridOptions({
      columns: buildRecycleColumns(
        moduleMeta.value[newMod] ?? null,
        newMod,
        handleActionClick,
      ),
    });
    lastSyncedRecycleModule.value = newMod;
    await syncSubmissionAndReload({ page: 1 });
  } finally {
    syncingModule.value = false;
  }
}

async function loadModuleMeta() {
  try {
    const res = await getRecycleBinModulesApi();
    moduleMeta.value = res ?? {};
  } catch {
    moduleMeta.value = {};
  }
}

/** 仅更新条数统计；不在此 updateSchema，避免触发表单 submitOnChange 反复请求 */
async function refreshSummaryOnly() {
  try {
    const res = await getRecycleBinSummaryApi();
    summary.value = res ?? [];
  } catch {
    summary.value = [];
  }
}

const [Grid, gridApi] = useVbenVxeGrid({
  formOptions: useGridSearchFormOptions(buildFullSchema('')),
  gridOptions: {
    cellConfig: { height: 56 },
    columns: buildRecycleColumns(null, '', handleActionClick),
    keepSource: true,
    pagerConfig: { enabled: true },
    proxyConfig: {
      ajax: {
        query: async ({ page }: { page: { currentPage: number; pageSize: number } }, formValues: Record<string, unknown>) => {
          const mod = String(formValues?.module ?? '');
          activeListModule.value = mod;
          if (!mod) {
            return { items: [], total: 0 };
          }
          const params: Record<string, unknown> = {
            'page[number]': page.currentPage,
            'page[size]': page.pageSize,
            sort: '-deleted_at',
          };
          for (const [key, val] of Object.entries(formValues ?? {})) {
            if (key === 'module' || key === 'delete_level') continue;
            if (val !== undefined && val !== null && val !== '') {
              params[key] = val;
            }
          }
          const dl = formValues?.delete_level;
          if (dl && dl !== 'all') {
            params.delete_level = dl;
          }
          return getRecycleBinListApi(mod, params);
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

/** 同步「数据模块」下拉中的条数（summary 变化后调用） */
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
  const v = await gridApi.formApi?.getValues();
  if (v && gridApi.formApi?.setLatestSubmissionValues) {
    gridApi.formApi.setLatestSubmissionValues(toRaw(v));
  }
  await gridApi.query();
}

/**
 * 在 CrudGrid 已挂载、formApi.mount 完成后执行。
 * 若在 v-if 隐藏表格阶段调用 setState/setValues，会无效，表现为下拉「请选择」、列表 0 条。
 */
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
    delete_level: 'all',
    module: first,
  });
  gridApi.setGridOptions({
    columns: buildRecycleColumns(
      moduleMeta.value[first] ?? null,
      first,
      handleActionClick,
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
  if (!hasModuleConfig.value) {
    return;
  }
  // 等待 v-if 切换到 Card+CrudGrid，formApi.mount 完成后再写表单
  await nextTick();
  await nextTick();
  await bootstrapGridForm();
});

const cleanupPageContext = registerPageContext('admin/system/recycle-bin', () => ({
  page_key: 'admin.system.recycle-bin',
  page_title: $t('admin.system.recycleBin.title'),
  page_data: {
    resource: '/admin/recycle-bin',
  },
}));

const cleanupPageOps = registerPageOperations('admin.system.recycle-bin', [
  {
    description: 'Reload the recycle bin summary and list',
    handler: async () => {
      await onToolbarRefresh();
      return { message: 'Recycle bin refreshed', success: true };
    },
    label: $t('shared.pageOperation.refreshList'),
    name: 'refresh_list',
    readonly: true,
  },
  {
    description: 'Trigger cleanup of expired items in recycle bin',
    handler: async () => {
      await triggerRecycleBinCleanupApi();
      await onToolbarRefresh();
      return { message: 'Cleanup triggered', success: true };
    },
    label: $t('shared.pageOperation.deleteRecord'),
    name: 'trigger_cleanup',
    readonly: false,
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    content-class="flex flex-col gap-4"
    :description="$t('admin.system.recycleBin.description')"
  >
    <Card
      v-if="!configFetching && !hasModuleConfig"
      class="flex-1"
      :body-style="{ padding: '48px 16px' }"
    >
      <Empty :description="$t('admin.system.recycleBin.configUnavailable')" />
    </Card>

    <Spin v-else-if="configFetching" class="block py-24" />

    <Card
      v-else
      class="flex-1"
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
              v-if="totalDeletedCount > 0"
              class="mr-1 hidden text-xs text-muted-foreground sm:inline"
            >
              {{
                $t('common.recycleBin.itemCount', {
                  count: totalDeletedCount,
                })
              }}
              ·
              {{ $t('common.recycleBin.retentionDays', { days: 30 }) }}
            </span>
            <Popconfirm
              :title="$t('admin.system.recycleBin.cleanupConfirm')"
              @confirm="handleCleanup"
            >
              <Button type="primary" danger size="small">
                <IconifyIcon icon="lucide:flame" class="mr-1 size-3.5" />
                {{ $t('admin.system.recycleBin.cleanup') }}
              </Button>
            </Popconfirm>
            <Tooltip
              :title="
                activeModuleDeletedCount <= 0
                  ? $t('admin.system.recycleBin.clearModuleDisabledTip')
                  : ''
              "
            >
              <span class="inline-block">
                <Button
                  danger
                  size="small"
                  :disabled="activeModuleDeletedCount <= 0"
                  @click="handleClearModule"
                >
                  <IconifyIcon icon="lucide:trash-2" class="mr-1 size-3.5" />
                  {{ $t('admin.system.recycleBin.clearModule') }}
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

        <template #delete_level_cell="{ row }">
          <span
            v-if="row.delete_level === 'admin'"
            class="inline-flex items-center gap-1 rounded-md bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive"
          >
            <IconifyIcon icon="lucide:shield" class="size-3" />
            {{ $t('admin.system.recycleBin.levelAdmin') }}
          </span>
          <span
            v-else-if="row.delete_level === 'tenant'"
            class="inline-flex items-center gap-1 rounded-md bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning"
          >
            <IconifyIcon icon="lucide:building-2" class="size-3" />
            {{ $t('admin.system.recycleBin.levelTenant') }}
          </span>
          <span v-else class="text-muted-foreground">—</span>
        </template>

        <template #deleted_at_cell="{ row }">
          <Tooltip :title="formatDate(row.deleted_at)">
            <span class="text-muted-foreground">{{
              formatRelativeTime(row.deleted_at)
            }}</span>
          </Tooltip>
        </template>
      </CrudGrid>
    </Card>
  </Page>
</template>
