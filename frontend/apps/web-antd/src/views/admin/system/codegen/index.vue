<script lang="ts" setup>
/**
 * 代码生成器工作台 / Codegen workbench
 *
 * 将列表页从普通 CRUD 表格升级为 codegen 状态工作台：
 * - 顶部摘要卡
 * - 关注事项侧栏
 * - 更清晰的生命周期与错误展示
 */
import type {
  CodegenConfigInfo,
  CodegenWorkbenchItem,
  CodegenWorkbenchSummary,
} from '#/api/admin/codegen';

import { computed, h, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Checkbox,
  message,
  Modal,
  Tag,
  Tooltip,
} from 'ant-design-vue';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  createCodegenConfigApi,
  deleteCodegenConfigApi,
  deleteCodegenRollbackApi,
  downloadCodegenZipApi,
  duplicateCodegenConfigApi,
  getCodegenConfigListApi,
  getCodegenWorkbenchSummaryApi,
  postCodegenGenerateApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';

import DbTableImportModal from './modules/DbTableImportModal.vue';
import PresetSelectModal from './modules/PresetSelectModal.vue';
import {
  getManifestStatusColor,
  getManifestStatusText,
  getStatusColor,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';

defineOptions({ name: 'AdminSystemCodegenList' });

type WorkbenchStat = {
  key: Exclude<WorkbenchFilterKey, 'all'>;
  icon: string;
  tone: string;
  value: number;
  label: string;
  hint: string;
};

type WorkbenchFilterKey =
  | 'all'
  | 'applied'
  | 'attention'
  | 'draft'
  | 'generated'
  | 'rollback';

type WorkbenchFocusItem = {
  id: number;
  name: string;
  resource: string;
  status: string;
  message: string;
  manifestPresent: boolean;
  severity: 'error' | 'info' | 'warning';
};

const router = useRouter();
const dbImportVisible = ref(false);
const presetSelectVisible = ref(false);
const workbenchLoading = ref(false);
const workbenchSummary = ref<CodegenWorkbenchSummary | null>(null);
const activeWorkbenchFilter = ref<WorkbenchFilterKey>('all');

const STATUS_FILTER_KEYS = ['draft', 'generated', 'applied'] as const;

function isStatusWorkbenchFilter(
  key: WorkbenchFilterKey,
): key is (typeof STATUS_FILTER_KEYS)[number] {
  return STATUS_FILTER_KEYS.includes(
    key as (typeof STATUS_FILTER_KEYS)[number],
  );
}

function buildWorkbenchItemMessage(item: CodegenWorkbenchItem): string {
  if (item.last_error) return item.last_error;
  if (item.delete_allowed === false && item.delete_reason_message) {
    return item.delete_reason_message;
  }
  if (item.last_generated_at) {
    return [
      getManifestStatusText(Boolean(item.manifest_present)),
      formatRelativeTime(item.last_generated_at) ||
        formatDate(item.last_generated_at) ||
        '—',
    ].join(' · ');
  }
  return $t('admin.system.codegen.workbench.neverGenerated');
}

function extractCheckboxChecked(event: unknown): boolean {
  return Boolean(
    (event as { target?: { checked?: boolean } })?.target?.checked,
  );
}

function getActionErrorMessage(error: unknown, fallback: string): string {
  const response = (
    error as {
      response?: {
        data?: {
          detail?: { error?: string } | string;
          message?: string;
        };
      };
      message?: string;
    }
  )?.response?.data;

  if (typeof response?.message === 'string' && response.message.trim()) {
    return response.message;
  }
  if (typeof response?.detail === 'string' && response.detail.trim()) {
    return response.detail;
  }
  if (
    typeof response?.detail === 'object' &&
    typeof response.detail?.error === 'string' &&
    response.detail.error.trim()
  ) {
    return response.detail.error;
  }
  if (
    typeof (error as { message?: string })?.message === 'string' &&
    (error as { message?: string }).message?.trim()
  ) {
    return (error as { message?: string }).message as string;
  }
  return fallback;
}

function toWorkbenchFocusItem(item: CodegenWorkbenchItem): WorkbenchFocusItem {
  let severity: WorkbenchFocusItem['severity'] = 'info';
  if (item.last_error) {
    severity = 'error';
  } else if (item.delete_allowed === false || !item.manifest_present) {
    severity = 'warning';
  }

  return {
    id: item.id,
    name: item.name,
    resource: item.resource,
    status: item.status,
    message: buildWorkbenchItemMessage(item),
    manifestPresent: Boolean(item.manifest_present),
    severity,
  };
}

function getFocusSeverityIcon(severity: WorkbenchFocusItem['severity']): string {
  if (severity === 'error') return 'lucide:triangle-alert';
  if (severity === 'warning') return 'lucide:shield-alert';
  return 'lucide:circle-dot';
}

function getFocusSeverityClasses(
  severity: WorkbenchFocusItem['severity'],
): string {
  if (severity === 'error') {
    return 'border-rose-200 bg-rose-50/80 text-rose-700';
  }
  if (severity === 'warning') {
    return 'border-amber-200 bg-amber-50/80 text-amber-700';
  }
  return 'border-slate-200 bg-slate-50/80 text-slate-700';
}

const workbenchStats = computed<WorkbenchStat[]>(() => {
  const stats = workbenchSummary.value?.stats;
  return [
    {
      key: 'draft',
      icon: 'lucide:file-pen-line',
      tone: 'text-slate-700 bg-slate-100',
      value: stats?.draft ?? 0,
      label: $t('admin.system.codegen.workbench.draft'),
      hint: $t('admin.system.codegen.workbench.draftHint'),
    },
    {
      key: 'generated',
      icon: 'lucide:sparkles',
      tone: 'text-sky-700 bg-sky-100',
      value: stats?.generated ?? 0,
      label: $t('admin.system.codegen.workbench.generated'),
      hint: $t('admin.system.codegen.workbench.generatedHint'),
    },
    {
      key: 'applied',
      icon: 'lucide:badge-check',
      tone: 'text-emerald-700 bg-emerald-100',
      value: stats?.applied ?? 0,
      label: $t('admin.system.codegen.workbench.applied'),
      hint: $t('admin.system.codegen.workbench.appliedHint'),
    },
    {
      key: 'rollback',
      icon: 'lucide:undo-2',
      tone: 'text-amber-700 bg-amber-100',
      value: stats?.rollback ?? 0,
      label: $t('admin.system.codegen.workbench.rollbackReady'),
      hint: $t('admin.system.codegen.workbench.rollbackReadyHint'),
    },
    {
      key: 'attention',
      icon: 'lucide:triangle-alert',
      tone: 'text-rose-700 bg-rose-100',
      value: stats?.attention ?? 0,
      label: $t('admin.system.codegen.workbench.attention'),
      hint: $t('admin.system.codegen.workbench.attentionHint'),
    },
  ];
});

const workbenchIssues = computed<WorkbenchFocusItem[]>(() => {
  const items = workbenchSummary.value?.sections.attention ?? [];
  return items.map(toWorkbenchFocusItem);
});

function getWorkbenchFilterConfig(key: WorkbenchFilterKey) {
  if (key === 'all') {
    return {
      label: $t('admin.system.codegen.workbench.recentIssues'),
      hint: $t('admin.system.codegen.workbench.recentIssuesHint'),
      mode: 'default' as const,
    };
  }
  const stat = workbenchStats.value.find((item) => item.key === key);
  return {
    label: stat?.label ?? $t('admin.system.codegen.workbench.recentIssues'),
    hint: stat?.hint ?? $t('admin.system.codegen.workbench.recentIssuesHint'),
    mode: isStatusWorkbenchFilter(key)
      ? ('table' as const)
      : ('panel' as const),
  };
}

const activeWorkbenchConfig = computed(() =>
  getWorkbenchFilterConfig(activeWorkbenchFilter.value),
);

const activeWorkbenchItems = computed<WorkbenchFocusItem[]>(() => {
  switch (activeWorkbenchFilter.value) {
    case 'draft':
    case 'generated':
    case 'applied': {
      return (
        workbenchSummary.value?.sections[activeWorkbenchFilter.value] ?? []
      ).map(toWorkbenchFocusItem);
    }
    case 'rollback': {
      return (workbenchSummary.value?.sections.rollback ?? []).map(
        toWorkbenchFocusItem,
      );
    }
    case 'attention': {
      return workbenchIssues.value;
    }
    case 'all':
    default: {
      return workbenchIssues.value;
    }
  }
});

const activeWorkbenchCount = computed(() => {
  if (activeWorkbenchFilter.value === 'all') {
    return workbenchIssues.value.length;
  }
  return (
    workbenchStats.value.find(
      (item) => item.key === activeWorkbenchFilter.value,
    )?.value ?? activeWorkbenchItems.value.length
  );
});

async function loadWorkbenchData() {
  workbenchLoading.value = true;
  try {
    workbenchSummary.value = await getCodegenWorkbenchSummaryApi();
  } catch {
    workbenchSummary.value = null;
  } finally {
    workbenchLoading.value = false;
  }
}

async function reloadWorkbench() {
  await Promise.all([Promise.resolve(gridReload()), loadWorkbenchData()]);
}

async function applyWorkbenchFilter(key: WorkbenchFilterKey) {
  activeWorkbenchFilter.value = key;
  gridApi.formApi?.setValues({
    'filter[status][eq]': isStatusWorkbenchFilter(key) ? key : undefined,
  });
  await gridApi.reload({ page: 1 });
}

async function resetWorkbenchFilter() {
  await applyWorkbenchFilter('all');
}

function goToBuilder(id: number) {
  router.push(`/admin/system/codegen/${id}/edit`);
}

async function onActionClick(params: { code: string; row: CodegenConfigInfo }) {
  const { code, row } = params;
  if (!row?.id) return;
  switch (code) {
    case 'edit': {
      goToBuilder(row.id);
      break;
    }
    case 'generate': {
      const forceGenerate = ref(false);
      Modal.confirm({
        title: $t('admin.system.codegen.confirm.generate', { name: row.name }),
        content: h('div', { class: 'flex flex-col gap-3' }, [
          h(
            'p',
            { class: 'm-0 text-sm text-muted-foreground' },
            $t('admin.system.codegen.workbench.generateHint', {
              resource: row.resource,
              count: row.generation_count ?? 0,
            }),
          ),
          h(
            Checkbox,
            {
              defaultChecked: false,
              onChange: (event: unknown) => {
                forceGenerate.value = extractCheckboxChecked(event);
              },
            },
            {
              default: () =>
                $t('admin.system.codegen.confirm.generateForceLabel'),
            },
          ),
          h(
            'p',
            { class: 'm-0 text-xs text-muted-foreground' },
            $t('admin.system.codegen.confirm.generateForceHint'),
          ),
        ]),
        onOk: async () => {
          try {
            const result = await postCodegenGenerateApi({
              config_id: row.id,
              force: forceGenerate.value,
            });
            if ((result as { success?: boolean }).success !== false) {
              message.success(
                $t('admin.system.codegen.messages.generateSuccess'),
              );
            } else {
              const errs = (result as { errors?: string[] }).errors;
              message.error(
                errs?.length ? errs.join('; ') : $t('common.failed'),
              );
            }
          } catch (error) {
            message.error(getActionErrorMessage(error, $t('common.failed')));
          } finally {
            await reloadWorkbench();
          }
        },
      });
      break;
    }
    case 'download': {
      try {
        await downloadCodegenZipApi(row.id);
        message.success($t('admin.system.codegen.messages.downloadSuccess'));
      } catch (error) {
        message.error(
          getActionErrorMessage(
            error,
            $t('admin.system.codegen.messages.downloadFail'),
          ),
        );
      }
      break;
    }
    case 'duplicate': {
      try {
        await duplicateCodegenConfigApi(row.id);
        message.success($t('admin.system.codegen.messages.duplicateSuccess'));
        await reloadWorkbench();
      } catch {
        message.error($t('common.failed'));
      }
      break;
    }
    case 'rollback': {
      const forceRollback = ref(false);
      Modal.confirm({
        okType: 'danger',
        title: $t('admin.system.codegen.confirm.rollback', { name: row.name }),
        content: h('div', { class: 'flex flex-col gap-3' }, [
          h(
            'p',
            { class: 'm-0 text-sm text-muted-foreground' },
            $t('admin.system.codegen.confirm.rollback'),
          ),
          h(
            Checkbox,
            {
              defaultChecked: false,
              onChange: (event: unknown) => {
                forceRollback.value = extractCheckboxChecked(event);
              },
            },
            {
              default: () =>
                $t('admin.system.codegen.confirm.rollbackForceLabel'),
            },
          ),
          h(
            'p',
            { class: 'm-0 text-xs text-muted-foreground' },
            $t('admin.system.codegen.confirm.rollbackForceHint'),
          ),
        ]),
        onOk: async () => {
          try {
            const result = await deleteCodegenRollbackApi(row.id, {
              force: forceRollback.value,
            });
            if ((result as { success?: boolean }).success !== false) {
              message.success(
                $t('admin.system.codegen.messages.rollbackSuccess'),
              );
            } else {
              const errs = (result as { errors?: string[] }).errors;
              message.error(
                errs?.length ? errs.join('; ') : $t('common.failed'),
              );
            }
          } catch (error) {
            message.error(getActionErrorMessage(error, $t('common.failed')));
          } finally {
            await reloadWorkbench();
          }
        },
      });
      break;
    }
    case 'delete': {
      Modal.confirm({
        okType: 'danger',
        title: $t('admin.system.codegen.confirm.delete', { name: row.name }),
        onOk: async () => {
          try {
            await deleteCodegenConfigApi(row.id);
            await reloadWorkbench();
          } catch {
            message.error($t('common.failed'));
          }
        },
      });
      break;
    }
  }
}

function openDbImport() {
  dbImportVisible.value = true;
}

function openPresetSelect() {
  presetSelectVisible.value = true;
}

function onPresetSelect(presetId: string | null) {
  presetSelectVisible.value = false;
  const query = presetId ? { preset: presetId } : {};
  router.replace({ path: '/admin/system/codegen/new', query });
}

async function onDbImportApplied(patch: Record<string, unknown>) {
  try {
    const { _importMode: _m, ...configJson } = patch;
    const resource = (configJson.resource as string) || 'unnamed';
    const moduleVal = (configJson.module as string) || 'system';
    const displayName = (configJson.display_name as string) || resource;
    const displayNameEn = (configJson.display_name_en as string) || resource;
    const name =
      (configJson.name as string) ||
      displayName ||
      $t('admin.system.codegen.unnamed');

    const res = await createCodegenConfigApi({
      name,
      resource,
      module: moduleVal,
      display_name: displayName,
      display_name_en: displayNameEn,
      config_json: configJson,
    });
    dbImportVisible.value = false;
    message.success($t('shared.common.success'));
    router.replace(`/admin/system/codegen/${res.id}/edit`);
  } catch {
    message.error($t('common.failed'));
  }
}

const {
  Grid,
  gridApi,
  onRefresh: gridReload,
} = useCrudPage<CodegenConfigInfo>({
  api: {
    list: getCodegenConfigListApi,
    resource: '/admin/codegen/configs',
    delete: deleteCodegenConfigApi,
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.codegen',
  defaultSort: '-created_at',
  toolbar: {
    custom: true,
    export: true,
    refresh: true,
    search: true,
    zoom: false,
  },
  customActions: {
    edit: (row) => onActionClick({ code: 'edit', row }),
    generate: (row) => onActionClick({ code: 'generate', row }),
    download: (row) => onActionClick({ code: 'download', row }),
    duplicate: (row) => onActionClick({ code: 'duplicate', row }),
    rollback: (row) => onActionClick({ code: 'rollback', row }),
    delete: (row) => onActionClick({ code: 'delete', row }),
  },
});

onMounted(() => {
  loadWorkbenchData();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-3">
    <div
      class="rounded-2xl border border-border/70 bg-background px-3.5 py-2.5 shadow-sm"
    >
      <div
        class="flex flex-col gap-2.5 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-1.5">
            <IconifyIcon icon="lucide:blocks" class="size-3.5" />
            <span class="text-lg font-semibold tracking-tight text-foreground">
              {{ $t('admin.system.codegen.name') }}
            </span>
            <Tag color="processing" class="!mr-0">
              {{ $t('admin.system.codegen.debugTag') }}
            </Tag>
            <Tag
              v-if="workbenchIssues.length > 0"
              color="warning"
              class="!mr-0"
            >
              {{ $t('admin.system.codegen.workbench.attention') }}
              {{ workbenchIssues.length }}
            </Tag>
          </div>
          <div class="mt-1 max-w-3xl text-xs text-muted-foreground">
            {{ $t('admin.system.codegen.pageDesc') }}
          </div>
        </div>

        <div class="flex shrink-0 flex-wrap gap-2">
          <Button v-access:code="['action.codegen.db']" @click="openDbImport">
            <IconifyIcon icon="lucide:database" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.importFromDb') }}
          </Button>
          <Button
            v-access:code="['action.codegen.create']"
            type="primary"
            @click="openPresetSelect"
          >
            <IconifyIcon icon="lucide:sparkles" class="mr-1 size-4" />
            {{ $t('admin.system.codegen.create') }}
          </Button>
        </div>
      </div>

      <div class="mt-2.5 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-full border border-border bg-muted/20 px-2.5 py-1 text-[11px] transition-colors hover:border-primary/40 hover:bg-primary/5"
          :class="
            activeWorkbenchFilter === 'all'
              ? 'border-primary bg-primary/5 text-primary'
              : 'text-muted-foreground'
          "
          @click="resetWorkbenchFilter"
        >
          <span class="font-medium">{{ $t('common.all') }}</span>
        </button>
        <button
          v-for="item in workbenchStats"
          :key="item.key"
          type="button"
          class="inline-flex items-center gap-2 rounded-full border bg-background px-2.5 py-1 text-left transition-colors hover:border-primary/40 hover:bg-primary/5"
          :class="
            activeWorkbenchFilter === item.key
              ? 'border-primary bg-primary/5'
              : 'border-border'
          "
          :title="item.hint"
          @click="applyWorkbenchFilter(item.key)"
        >
          <span
            class="inline-flex size-5 items-center justify-center rounded-full"
            :class="item.tone"
          >
            <IconifyIcon :icon="item.icon" class="size-3" />
          </span>
          <span class="text-xs font-semibold text-foreground">
            {{ item.value }}
          </span>
          <span class="text-[10px] text-muted-foreground">
            {{ item.label }}
          </span>
        </button>
      </div>
    </div>

    <Card
      class="min-w-0 overflow-hidden"
      :loading="workbenchLoading"
      :body-style="{ padding: '12px' }"
    >
      <div
        class="mb-2.5 flex flex-col gap-2 rounded-xl border border-border/70 bg-muted/10 px-3 py-2 md:flex-row md:items-center md:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <div class="text-sm font-semibold text-foreground">
              {{ activeWorkbenchConfig.label }}
            </div>
            <Tag
              v-if="activeWorkbenchFilter !== 'all'"
              :color="
                activeWorkbenchConfig.mode === 'table'
                  ? 'processing'
                  : 'warning'
              "
              class="!mr-0"
            >
              {{
                activeWorkbenchConfig.mode === 'table'
                  ? $t('admin.system.codegen.workbench.focusAffectsTable')
                  : $t('admin.system.codegen.workbench.focusAffectsPanel')
              }}
            </Tag>
          </div>
          <div class="mt-0.5 text-xs text-muted-foreground">
            {{ activeWorkbenchConfig.hint }}
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Tag color="processing" class="!mr-0">
            {{ activeWorkbenchCount }}
          </Tag>
        </div>
      </div>

      <div class="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_256px]">
        <div
          class="min-w-0 overflow-hidden rounded-2xl border border-border/70 bg-background"
        >
          <Grid>
            <template #name_cell="{ row }">
              <button
                type="button"
                class="group flex w-full items-start gap-2.5 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-muted/60"
                @click="goToBuilder(row.id)"
              >
                <span
                  class="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
                >
                  <IconifyIcon
                    :icon="
                      row.manifest_present
                        ? 'lucide:folder-git-2'
                        : 'lucide:file-code-2'
                    "
                    class="size-4.5"
                  />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-2">
                    <span
                      class="truncate font-medium text-foreground group-hover:text-primary"
                    >
                      {{ row.name }}
                    </span>
                    <Tag
                      v-if="row.delete_allowed === false"
                      color="warning"
                      class="!mr-0"
                    >
                      {{ $t('admin.system.codegen.workbench.deleteGuarded') }}
                    </Tag>
                  </span>
                  <span
                    class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
                  >
                    <span class="font-mono">{{ row.resource }}</span>
                    <span>{{ row.display_name || '-' }}</span>
                    <span>{{ row.module }}</span>
                  </span>
                </span>
              </button>
            </template>

            <template #status_cell="{ row }">
              <div class="flex flex-col items-center gap-1.5">
                <Tag :color="getStatusColor(row.status)" class="!mr-0">
                  {{ getStatusText(row.status) }}
                </Tag>
                <span class="text-[11px] text-muted-foreground">
                  {{
                    row.generation_count > 0
                      ? $t('admin.system.codegen.workbench.generatedCount', {
                          count: row.generation_count,
                        })
                      : $t('admin.system.codegen.workbench.neverGenerated')
                  }}
                </span>
              </div>
            </template>

            <template #manifest_present_cell="{ row }">
              <Tag
                :color="getManifestStatusColor(Boolean(row.manifest_present))"
                class="!mr-0"
              >
                {{ getManifestStatusText(Boolean(row.manifest_present)) }}
              </Tag>
            </template>

            <template #generation_count_cell="{ row }">
              <div class="flex flex-col items-center gap-1">
                <span class="text-lg font-semibold leading-none">{{
                  row.generation_count ?? 0
                }}</span>
                <span class="text-[11px] text-muted-foreground">
                  {{
                    row.last_generated_at
                      ? formatRelativeTime(row.last_generated_at) || '—'
                      : $t('admin.system.codegen.workbench.neverGenerated')
                  }}
                </span>
              </div>
            </template>

            <template #last_generated_at_cell="{ row }">
              <Tooltip :title="formatDate(row.last_generated_at)">
                <span class="text-muted-foreground">
                  {{ formatRelativeTime(row.last_generated_at) || '—' }}
                </span>
              </Tooltip>
            </template>

            <template #last_error_cell="{ row }">
              <div
                v-if="row.last_error"
                class="rounded-lg border border-rose-200 bg-rose-50/80 px-2.5 py-1.5 text-left"
              >
                <div
                  class="mb-1 flex items-center gap-1.5 text-xs font-medium text-rose-700"
                >
                  <IconifyIcon icon="lucide:triangle-alert" class="size-3.5" />
                  <span>{{
                    $t('admin.system.codegen.workbench.lastErrorLabel')
                  }}</span>
                </div>
                <div class="line-clamp-2 text-xs leading-5 text-rose-700/90">
                  {{ row.last_error }}
                </div>
              </div>
              <div v-else class="text-xs text-muted-foreground">
                {{
                  row.delete_allowed === false
                    ? row.delete_reason_message ||
                      $t('admin.system.codegen.actions.deleteDisabledHint')
                    : '—'
                }}
              </div>
            </template>
          </Grid>
        </div>

        <aside
          class="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-border/70 bg-muted/10"
        >
          <div class="border-b border-border/70 px-3 py-2">
            <div class="flex items-center justify-between gap-2">
              <div class="text-sm font-semibold text-foreground">
                {{ activeWorkbenchConfig.label }}
              </div>
              <Tag color="processing" class="!mr-0">
                {{ activeWorkbenchItems.length }}
              </Tag>
            </div>
            <div class="mt-1 text-xs leading-5 text-muted-foreground">
              {{ activeWorkbenchConfig.hint }}
            </div>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto p-2">
            <div
              v-if="activeWorkbenchItems.length === 0"
              class="flex min-h-[180px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-background/70 px-4 text-center"
            >
              <IconifyIcon
                icon="lucide:shield-check"
                class="size-8 text-muted-foreground"
              />
              <div class="mt-3 text-sm font-medium text-foreground">
                {{ $t('admin.system.codegen.workbench.cleanState') }}
              </div>
            </div>

            <div v-else class="flex flex-col gap-2">
              <button
                v-for="item in activeWorkbenchItems"
                :key="`${item.id}-${item.status}-${item.severity}`"
                type="button"
                class="rounded-xl border px-2.5 py-2.5 text-left transition-colors hover:bg-background/90"
                :class="getFocusSeverityClasses(item.severity)"
                @click="goToBuilder(item.id)"
              >
                <div class="flex items-start gap-2.5">
                  <span
                    class="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-xl bg-background/80"
                  >
                    <IconifyIcon
                      :icon="getFocusSeverityIcon(item.severity)"
                      class="size-4"
                    />
                  </span>

                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <span class="truncate text-sm font-medium">
                        {{ item.name }}
                      </span>
                      <Tag :color="getStatusColor(item.status)" class="!mr-0">
                        {{ getStatusText(item.status) }}
                      </Tag>
                    </div>

                    <div
                      class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-current/70"
                    >
                      <span class="font-mono">{{ item.resource }}</span>
                      <span>
                        {{
                          getManifestStatusText(Boolean(item.manifestPresent))
                        }}
                      </span>
                    </div>

                    <div class="mt-2 line-clamp-3 text-xs leading-5 text-current/85">
                      {{ item.message }}
                    </div>
                  </div>
                </div>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </Card>

    <DbTableImportModal
      v-model:open="dbImportVisible"
      @applied="onDbImportApplied"
    />
    <PresetSelectModal
      v-model:open="presetSelectVisible"
      @select="onPresetSelect"
    />
  </Page>
</template>
