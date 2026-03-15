<script lang="ts" setup>
/**
 * AI 表策略管理列表页面
 * AI table policy management list page
 *
 * CRUD 权限可直接在表格中点击切换，无需打开编辑抽屉 / Toggle CRUD permissions in table, no edit drawer.
 */
import type { AITablePolicyInfo } from '#/api/admin/ai';

import { onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, message, Modal, Switch, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAITablePolicyListApi,
  syncAITablePoliciesApi,
  updateAITablePolicyApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import { useColumns, useFormSchema, useGridFormSchema } from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'AITablePolicyList' });

/**
 * 切换策略启用状态 / Toggle policy active status
 */
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
        // handled by interceptor / 错误由请求拦截器处理
      }
    },
  });
}

/**
 * 直接切换单个 CRUD 权限（无需确认弹窗，即点即改）
 * Toggle single CRUD permission inline (no confirm).
 * 使用本地更新避免 onRefresh 导致的行引用偏移
 */
async function onToggleCrud(
  row: AITablePolicyInfo,
  field: 'allow_create' | 'allow_delete' | 'allow_read' | 'allow_update',
) {
  const id = row.id;
  const newValue = !row[field];
  try {
    await updateAITablePolicyApi(id, { [field]: newValue });
    row[field] = newValue;
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

/**
 * 同步表策略 / Sync table policies
 */
const syncing = ref(false);

async function onSync() {
  Modal.confirm({
    title: $t('admin.ai.tablePolicy.syncConfirm'),
    onOk: async () => {
      syncing.value = true;
      try {
        const result = await syncAITablePoliciesApi();
        message.success(
          $t('admin.ai.tablePolicy.syncSuccess', {
            new: result.new_count ?? 0,
            existing: result.existing_count ?? 0,
          }),
        );
        onRefresh();
      } catch {
        // handled by interceptor / 错误由请求拦截器处理
      } finally {
        syncing.value = false;
      }
    },
  });
}

const { Grid, FormDrawer, onRefresh, gridApi, formAiOperations } =
  useCrudPage<AITablePolicyInfo>({
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
    ai: { pageKey: 'admin.ai.table-policies', formSchema: useFormSchema },
  });

const cleanupPageContext = registerPageContext('admin/ai/table-policies', () => ({
  page_key: 'admin.ai.table-policies',
  page_title: $t('admin.ai.tablePolicy.name'),
  page_data: {
    resource: '/admin/ai/table-policies',
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.table-policies', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the table policy list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'Table policy list refreshed' };
    },
  },
  {
    name: 'sync_policies',
    label: $t('shared.pageOperation.syncData'),
    description: 'Sync table policies from database schema',
    readonly: false,
    handler: async () => {
      onSync();
      return { success: true, message: 'Sync dialog opened' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search table policies by table name',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Table name keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[table_name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  ...formAiOperations,
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
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
        <!-- 表名列：图标 + 表名 + 显示名称 + 描述(tooltip) -->
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
                  <code class="text-sm font-semibold text-foreground">{{
                    row.table_name
                  }}</code>
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

        <!-- CRUD 权限列：可点击切换 -->
        <template #crud_cell="{ row }">
          <div class="flex items-center justify-center gap-1.5">
            <Tooltip :title="$t('admin.ai.tablePolicy.allowRead')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="row.allow_read ? 'crud-btn--read-on' : 'crud-btn--off'"
                @click="onToggleCrud(row, 'allow_read')"
              >
                R
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowCreate')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="
                  row.allow_create ? 'crud-btn--create-on' : 'crud-btn--off'
                "
                @click="onToggleCrud(row, 'allow_create')"
              >
                C
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowUpdate')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="
                  row.allow_update ? 'crud-btn--update-on' : 'crud-btn--off'
                "
                @click="onToggleCrud(row, 'allow_update')"
              >
                U
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowDelete')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="
                  row.allow_delete ? 'crud-btn--delete-on' : 'crud-btn--off'
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

        <!-- 左侧工具栏：同步 -->
        <template #toolbar-actions>
          <Button
            v-access:code="['ai_table_policy:update']"
            type="primary"
            :loading="syncing"
            @click="onSync"
          >
            <template v-if="!syncing" #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('admin.ai.tablePolicy.sync') }}
          </Button>
        </template>
      </Grid>
    </Card>
  </Page>
</template>

<style scoped>
.crud-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 26px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  border: 1px solid transparent;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.crud-btn:hover {
  transform: scale(1.08);
}

.crud-btn--off {
  color: hsl(var(--muted-foreground));
  background: hsl(var(--muted));
  border-color: hsl(var(--border));
}

.crud-btn--off:hover {
  background: hsl(var(--accent));
}

.crud-btn--read-on {
  color: rgb(22 163 74);
  background: rgb(34 197 94 / 15%);
  border-color: rgb(34 197 94 / 30%);
}

.crud-btn--create-on {
  color: rgb(37 99 235);
  background: rgb(59 130 246 / 15%);
  border-color: rgb(59 130 246 / 30%);
}

.crud-btn--update-on {
  color: rgb(234 88 12);
  background: rgb(249 115 22 / 15%);
  border-color: rgb(249 115 22 / 30%);
}

.crud-btn--delete-on {
  color: rgb(220 38 38);
  background: rgb(239 68 68 / 15%);
  border-color: rgb(239 68 68 / 30%);
}
</style>
