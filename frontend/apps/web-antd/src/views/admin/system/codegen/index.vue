<script lang="ts" setup>
/**
 * 代码生成器工作台 / Codegen workbench
 *
 * 将列表页从普通 CRUD 表格升级为 codegen 状态工作台：
 * - 顶部摘要卡
 * - 关注事项侧栏
 * - 更清晰的生命周期与错误展示
 */
import type { CodegenConfigInfo } from '#/api/admin/codegen';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, message, Modal, Tag, Tooltip } from 'ant-design-vue';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  createCodegenConfigApi,
  deleteCodegenConfigApi,
  deleteCodegenRollbackApi,
  downloadCodegenZipApi,
  duplicateCodegenConfigApi,
  getCodegenConfigListApi,
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
const workbenchItems = ref<CodegenConfigInfo[]>([]);
const activeWorkbenchFilter = ref<WorkbenchFilterKey>('all');

const STATUS_FILTER_KEYS = ['draft', 'generated', 'applied'] as const;

function isStatusWorkbenchFilter(
  key: WorkbenchFilterKey,
): key is (typeof STATUS_FILTER_KEYS)[number] {
  return STATUS_FILTER_KEYS.includes(
    key as (typeof STATUS_FILTER_KEYS)[number],
  );
}

function buildWorkbenchItemMessage(item: CodegenConfigInfo): string {
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

function toWorkbenchFocusItem(item: CodegenConfigInfo): WorkbenchFocusItem {
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

const workbenchStats = computed<WorkbenchStat[]>(() => {
  const items = workbenchItems.value;
  return [
    {
      key: 'draft',
      icon: 'lucide:file-pen-line',
      tone: 'text-slate-700 bg-slate-100',
      value: items.filter((item) => item.status === 'draft').length,
      label: $t('admin.system.codegen.workbench.draft'),
      hint: $t('admin.system.codegen.workbench.draftHint'),
    },
    {
      key: 'generated',
      icon: 'lucide:sparkles',
      tone: 'text-sky-700 bg-sky-100',
      value: items.filter((item) => item.status === 'generated').length,
      label: $t('admin.system.codegen.workbench.generated'),
      hint: $t('admin.system.codegen.workbench.generatedHint'),
    },
    {
      key: 'applied',
      icon: 'lucide:badge-check',
      tone: 'text-emerald-700 bg-emerald-100',
      value: items.filter((item) => item.status === 'applied').length,
      label: $t('admin.system.codegen.workbench.applied'),
      hint: $t('admin.system.codegen.workbench.appliedHint'),
    },
    {
      key: 'rollback',
      icon: 'lucide:undo-2',
      tone: 'text-amber-700 bg-amber-100',
      value: items.filter((item) => item.manifest_present).length,
      label: $t('admin.system.codegen.workbench.rollbackReady'),
      hint: $t('admin.system.codegen.workbench.rollbackReadyHint'),
    },
    {
      key: 'attention',
      icon: 'lucide:triangle-alert',
      tone: 'text-rose-700 bg-rose-100',
      value: items.filter(
        (item) => item.last_error || item.delete_allowed === false,
      ).length,
      label: $t('admin.system.codegen.workbench.attention'),
      hint: $t('admin.system.codegen.workbench.attentionHint'),
    },
  ];
});

const workbenchIssues = computed<WorkbenchFocusItem[]>(() => {
  return workbenchItems.value
    .flatMap((item) => {
      const issues: WorkbenchFocusItem[] = [];
      if (item.last_error) {
        issues.push(toWorkbenchFocusItem(item));
      } else if (item.delete_allowed === false && item.delete_reason_message) {
        issues.push(toWorkbenchFocusItem(item));
      }
      return issues;
    })
    .slice(0, 6);
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
      return workbenchItems.value
        .filter((item) => item.status === activeWorkbenchFilter.value)
        .slice(0, 6)
        .map(toWorkbenchFocusItem);
    }
    case 'rollback': {
      return workbenchItems.value
        .filter((item) => item.manifest_present)
        .slice(0, 6)
        .map(toWorkbenchFocusItem);
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

const topWorkbenchIssues = computed(() => workbenchIssues.value.slice(0, 2));

async function loadWorkbenchData() {
  workbenchLoading.value = true;
  try {
    const res = await getCodegenConfigListApi({
      'page[number]': 1,
      'page[size]': 200,
      sort: '-updated_at',
    });
    workbenchItems.value = res.items ?? [];
  } catch {
    workbenchItems.value = [];
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
      Modal.confirm({
        title: $t('admin.system.codegen.confirm.generate', { name: row.name }),
        content: $t('admin.system.codegen.workbench.generateHint', {
          resource: row.resource,
          count: row.generation_count ?? 0,
        }),
        onOk: async () => {
          try {
            const result = await postCodegenGenerateApi({
              config_id: row.id,
              force: false,
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
          } catch {
            message.error($t('common.failed'));
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
      } catch {
        message.error($t('admin.system.codegen.messages.downloadFail'));
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
      Modal.confirm({
        okType: 'danger',
        title: $t('admin.system.codegen.confirm.rollback', { name: row.name }),
        onOk: async () => {
          try {
            const result = await deleteCodegenRollbackApi(row.id, {
              force: false,
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
          } catch {
            message.error($t('common.failed'));
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
      class="rounded-2xl border border-border/70 bg-background px-4 py-3 shadow-sm"
    >
      <div
        class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
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

      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-full border border-border bg-muted/20 px-3 py-1.5 text-xs transition-colors hover:border-primary/40 hover:bg-primary/5"
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
          class="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-left transition-colors hover:border-primary/40 hover:bg-primary/5"
          :class="
            activeWorkbenchFilter === item.key
              ? 'border-primary bg-primary/5'
              : 'border-border'
          "
          :title="item.hint"
          @click="applyWorkbenchFilter(item.key)"
        >
          <span
            class="inline-flex size-6 items-center justify-center rounded-full"
            :class="item.tone"
          >
            <IconifyIcon :icon="item.icon" class="size-3.5" />
          </span>
          <span class="text-sm font-semibold text-foreground">
            {{ item.value }}
          </span>
          <span class="text-[11px] text-muted-foreground">
            {{ item.label }}
          </span>
        </button>
      </div>

      <div
        v-if="topWorkbenchIssues.length > 0"
        class="mt-3 flex flex-wrap items-center gap-2 text-xs"
      >
        <span class="text-muted-foreground">
          {{ $t('admin.system.codegen.workbench.recentIssues') }}
        </span>
        <button
          v-for="issue in topWorkbenchIssues"
          :key="`${issue.id}-${issue.severity}`"
          type="button"
          class="inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1.5 transition-colors hover:bg-muted/50"
          :class="
            issue.severity === 'error'
              ? 'border-rose-200 bg-rose-50/70 text-rose-700'
              : 'border-amber-200 bg-amber-50/70 text-amber-700'
          "
          @click="goToBuilder(issue.id)"
        >
          <IconifyIcon
            :icon="
              issue.severity === 'error'
                ? 'lucide:triangle-alert'
                : 'lucide:shield-alert'
            "
            class="size-3.5 shrink-0"
          />
          <span class="max-w-[220px] truncate">{{ issue.name }}</span>
        </button>
        <Button
          v-if="workbenchIssues.length > topWorkbenchIssues.length"
          type="link"
          size="small"
          @click="applyWorkbenchFilter('attention')"
        >
          +{{ workbenchIssues.length - topWorkbenchIssues.length }}
        </Button>
      </div>
    </div>

    <Card
      class="min-w-0 overflow-hidden"
      :loading="workbenchLoading"
      :body-style="{ padding: '16px' }"
    >
      <div
        class="mb-3 flex flex-col gap-2 rounded-xl border border-border/70 bg-muted/10 px-3 py-2 md:flex-row md:items-center md:justify-between"
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

      <div
        class="overflow-hidden rounded-2xl border border-border/70 bg-background"
      >
        <Grid>
          <template #name_cell="{ row }">
            <button
              type="button"
              class="group flex w-full items-start gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-muted/60"
              @click="goToBuilder(row.id)"
            >
              <span
                class="mt-0.5 inline-flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon
                  :icon="
                    row.manifest_present
                      ? 'lucide:folder-git-2'
                      : 'lucide:file-code-2'
                  "
                  class="size-5"
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
              class="rounded-xl border border-rose-200 bg-rose-50/80 px-3 py-2 text-left"
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
