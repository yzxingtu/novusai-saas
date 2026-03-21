<script lang="ts" setup>
import type { AITablePolicyInfo } from '#/api/admin/ai';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Card,
  Collapse,
  CollapsePanel,
  message,
  Modal,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAITablePolicyDeclaredTablesApi,
  getAITablePolicyListApi,
  syncAITablePoliciesApi,
  updateAITablePolicyApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import { useColumns, useFormSchema, useGridFormSchema } from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'AITablePolicyList' });

const syncing = ref(false);
const declaredTables = ref<Set<string>>(new Set());

async function loadDeclaredTables() {
  try {
    const res = await getAITablePolicyDeclaredTablesApi();
    const list = Array.isArray(res)
      ? res
      : ((res as { data?: string[] })?.data ?? []);
    declaredTables.value = new Set(list);
  } catch {
    declaredTables.value = new Set();
  }
}

loadDeclaredTables();

function onToggleActive(row: AITablePolicyInfo) {
  Modal.confirm({
    title: row.is_active
      ? $t('admin.common.confirmDisable')
      : $t('admin.common.confirmEnable'),
    onOk: async () => {
      try {
        await updateAITablePolicyApi(row.id, { is_active: !row.is_active });
        message.success($t('common.success'));
        onRefresh();
      } catch {
        // handled by interceptor
      }
    },
  });
}

async function onToggleCrud(
  row: AITablePolicyInfo,
  field: 'allow_create' | 'allow_delete' | 'allow_read' | 'allow_update',
) {
  const newValue = !row[field];
  try {
    await updateAITablePolicyApi(row.id, { [field]: newValue });
    row[field] = newValue;
  } catch {
    // handled by interceptor
  }
}

async function performSyncPolicies() {
  syncing.value = true;
  try {
    const result = await syncAITablePoliciesApi();
    message.success(
      $t('admin.ai.tablePolicy.syncSuccess', {
        synced: result.synced ?? 0,
      }),
    );
    if (Array.isArray(result.declared_tables)) {
      declaredTables.value = new Set(result.declared_tables);
    } else {
      await loadDeclaredTables();
    }
    onRefresh();
    return result;
  } finally {
    syncing.value = false;
  }
}

async function onSync() {
  Modal.confirm({
    title: $t('admin.ai.tablePolicy.syncConfirm'),
    onOk: async () => {
      try {
        await performSyncPolicies();
      } catch {
        // handled by interceptor
      }
    },
  });
}

const { Grid, FormDrawer, onRefresh } = useCrudPage<AITablePolicyInfo>({
  api: {
    list: getAITablePolicyListApi,
    resource: '/admin/ai/table-policies',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  i18nPrefix: 'admin.ai.tablePolicy',
  nameField: 'table_name',
  defaultSort: 'sort_order',
  gridOptions: {
    expandConfig: {
      accordion: true,
      trigger: 'row',
      iconOpen: 'vxe-icon-square-minus',
      iconClose: 'vxe-icon-square-plus',
    },
  },
  ai: {
    pageKey: 'admin.ai.table-policies',
    formSchema: () => useFormSchema(),
    entityName: $t('admin.ai.tablePolicy.name'),
    entityDescription: $t('admin.ai.tablePolicy.pageDesc'),
    disabledOperations: ['create_record', 'delete_record'],
    tablePolicy: {
      enabled: true,
      kind: 'management',
      relatedResources: ['/admin/ai/table-policies'],
      relatedTables: ['ai_table_policies'],
      supportedActions: [
        'list_policies',
        'sync_policies',
        'edit_policy',
        'inspect_columns',
      ],
    },
    contextExtras: () => ({
      declared_table_count: declaredTables.value.size,
      declared_tables: [...declaredTables.value].slice(0, 50),
    }),
    extra: [
      {
        name: 'sync_policies',
        label: $t('shared.pageOperation.syncData'),
        description:
          'Sync table policies from code declarations / 从代码声明同步表策略',
        readonly: false,
        handler: async () => {
          const result = await performSyncPolicies();
          return {
            success: true,
            message: $t('admin.ai.tablePolicy.syncSuccess', {
              synced: result.synced ?? 0,
            }),
            data: {
              declared_tables: Array.isArray(result.declared_tables)
                ? result.declared_tables
                : [...declaredTables.value],
              synced: result.synced ?? 0,
            },
          };
        },
      },
    ],
  },
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.tablePolicy.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 展开行 -->
        <template #expand_content="{ row }">
          <div class="grid grid-cols-1 gap-4 px-4 py-3 md:grid-cols-3">
            <!-- 屏蔽列 -->
            <div
              class="rounded-lg border border-red-200/60 bg-red-50/30 p-3 dark:border-red-900/40 dark:bg-red-950/20"
            >
              <div
                class="mb-2 text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-500"
              >
                {{ $t('admin.ai.tablePolicy.expandBlockedColumns') }}
                <span class="ml-1 font-normal">
                  ({{ (row.blocked_columns || []).length }})
                </span>
              </div>
              <div
                v-if="(row.blocked_columns?.length ?? 0) > 0"
                class="flex flex-wrap gap-1.5"
              >
                <Tag
                  v-for="col in row.blocked_columns || []"
                  :key="col"
                  color="red"
                  class="m-0"
                >
                  {{ col }}
                </Tag>
              </div>
              <div v-else class="text-xs text-muted-foreground">
                {{ $t('admin.ai.tablePolicy.expandNoData') }}
              </div>
            </div>
            <!-- 只读列 -->
            <div
              class="rounded-lg border border-amber-200/60 bg-amber-50/30 p-3 dark:border-amber-900/40 dark:bg-amber-950/20"
            >
              <div
                class="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-500"
              >
                {{ $t('admin.ai.tablePolicy.expandReadonlyColumns') }}
                <span class="ml-1 font-normal">
                  ({{ (row.readonly_columns || []).length }})
                </span>
              </div>
              <div
                v-if="(row.readonly_columns?.length ?? 0) > 0"
                class="flex flex-wrap gap-1.5"
              >
                <Tag
                  v-for="col in row.readonly_columns || []"
                  :key="col"
                  color="orange"
                  class="m-0"
                >
                  {{ col }}
                </Tag>
              </div>
              <div v-else class="text-xs text-muted-foreground">
                {{ $t('admin.ai.tablePolicy.expandNoData') }}
              </div>
            </div>
            <!-- 已配置列描述 -->
            <div
              class="rounded-lg border border-emerald-200/60 bg-emerald-50/30 p-3 dark:border-emerald-900/40 dark:bg-emerald-950/20"
            >
              <div
                class="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-500"
              >
                {{ $t('admin.ai.tablePolicy.expandDescribedColumns') }}
                <span class="ml-1 font-normal">
                  ({{
                    row.column_descriptions
                      ? Object.keys(row.column_descriptions).length
                      : 0
                  }})
                </span>
              </div>
              <div
                v-if="
                  row.column_descriptions &&
                  Object.keys(row.column_descriptions).length > 0
                "
                class="space-y-1"
              >
                <Collapse :bordered="false" ghost>
                  <CollapsePanel
                    :key="1"
                    :header="
                      $t('admin.ai.tablePolicy.expandDescribedList', {
                        count: Object.keys(row.column_descriptions).length,
                      })
                    "
                  >
                    <div class="max-h-40 space-y-1.5 overflow-y-auto pr-1">
                      <div
                        v-for="[colName, desc] in Object.entries(
                          row.column_descriptions,
                        )"
                        :key="colName"
                        class="flex gap-2 border-b border-border/50 pb-1.5 last:border-0 last:pb-0"
                      >
                        <code class="shrink-0 text-xs text-foreground">{{
                          colName
                        }}</code>
                        <span
                          class="min-w-0 flex-1 break-words text-xs text-muted-foreground"
                          >{{ desc }}</span
                        >
                      </div>
                    </div>
                  </CollapsePanel>
                </Collapse>
              </div>
              <div v-else class="text-xs text-muted-foreground">
                {{ $t('admin.ai.tablePolicy.expandNoData') }}
              </div>
            </div>
          </div>
        </template>

        <!-- 表名列 -->
        <template #tableName_cell="{ row }">
          <div class="flex items-center gap-2.5">
            <div
              class="flex size-8 shrink-0 items-center justify-center rounded-lg"
              :class="row.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                icon="lucide:table-2"
                class="size-4"
                :class="
                  row.is_active ? 'text-primary' : 'text-muted-foreground'
                "
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <Tooltip :title="row.description || undefined">
                  <code class="text-sm font-semibold text-foreground">
                    {{ row.table_name }}
                  </code>
                </Tooltip>
                <Tooltip
                  v-if="!declaredTables.has(row.table_name)"
                  :title="$t('admin.ai.tablePolicy.notDeclaredWarning')"
                >
                  <IconifyIcon
                    icon="lucide:alert-triangle"
                    class="ml-1 size-3.5 text-amber-500"
                  />
                </Tooltip>
              </div>
              <div
                class="flex items-center gap-1.5 text-xs text-muted-foreground"
              >
                <span>{{ row.label }}</span>
                <span v-if="row.permission_code" class="text-[10px] opacity-60">
                  · {{ row.permission_code }}
                </span>
              </div>
            </div>
          </div>
        </template>

        <!-- CRUD 权限列 -->
        <template #crud_cell="{ row }">
          <div class="flex items-center justify-center gap-1.5">
            <Tooltip :title="$t('admin.ai.tablePolicy.allowRead')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold transition-all hover:scale-105"
                :class="
                  row.allow_read
                    ? 'border border-green-500/30 bg-green-500/15 text-green-600'
                    : 'border border-border bg-muted text-muted-foreground'
                "
                @click="onToggleCrud(row, 'allow_read')"
              >
                R
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowCreate')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold transition-all hover:scale-105"
                :class="
                  row.allow_create
                    ? 'border border-blue-500/30 bg-blue-500/15 text-blue-600'
                    : 'border border-border bg-muted text-muted-foreground'
                "
                @click="onToggleCrud(row, 'allow_create')"
              >
                C
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowUpdate')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold transition-all hover:scale-105"
                :class="
                  row.allow_update
                    ? 'border border-orange-500/30 bg-orange-500/15 text-orange-600'
                    : 'border border-border bg-muted text-muted-foreground'
                "
                @click="onToggleCrud(row, 'allow_update')"
              >
                U
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowDelete')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold transition-all hover:scale-105"
                :class="
                  row.allow_delete
                    ? 'border border-red-500/30 bg-red-500/15 text-red-600'
                    : 'border border-border bg-muted text-muted-foreground'
                "
                @click="onToggleCrud(row, 'allow_delete')"
              >
                D
              </button>
            </Tooltip>
          </div>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_table_policy:update']"
            :checked="row.is_active"
            size="small"
            @change="() => onToggleActive(row)"
          />
        </template>

        <!-- 右侧工具栏：同步按钮 -->
        <template #toolbar-tools>
          <Tooltip :title="$t('admin.ai.tablePolicy.sync')">
            <button
              v-access:code="['ai_table_policy:update']"
              class="ml-2 flex size-8 items-center justify-center rounded-lg border border-border/60 bg-background text-muted-foreground transition-all hover:border-primary/30 hover:text-primary"
              :disabled="syncing"
              @click="onSync"
            >
              <IconifyIcon
                icon="lucide:refresh-cw"
                class="size-3.5"
                :class="syncing && 'animate-spin'"
              />
            </button>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
