<script lang="ts" setup>
/**
 * AI 表策略管理列表页面
 *
 * CRUD 权限可直接在表格中点击切换，无需打开编辑抽屉
 */
import type { AITablePolicyInfo } from '#/api/admin/ai';

defineOptions({ name: 'AITablePolicyList' });

import { ref } from 'vue';

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

import { useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

/**
 * 切换策略启用状态
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
        // handled by interceptor
      }
    },
  });
}

/**
 * 直接切换单个 CRUD 权限（无需确认弹窗，即点即改）
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
    // handled by interceptor
  }
}

/**
 * 同步表策略
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
        // handled by interceptor
      } finally {
        syncing.value = false;
      }
    },
  });
}

const { Grid, FormDrawer, onRefresh } =
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
  });
</script>

<template>
  <Page auto-content-height :description="$t('admin.ai.tablePolicy.pageDesc')" content-class="flex flex-col gap-4">
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
                :class="row.is_active ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <Tooltip :title="row.description || undefined">
                  <code class="text-sm font-semibold text-foreground">{{ row.table_name }}</code>
                </Tooltip>
              </div>
              <div class="flex items-center gap-1.5 text-xs text-muted-foreground">
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
                :class="row.allow_create ? 'crud-btn--create-on' : 'crud-btn--off'"
                @click="onToggleCrud(row, 'allow_create')"
              >
                C
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowUpdate')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="row.allow_update ? 'crud-btn--update-on' : 'crud-btn--off'"
                @click="onToggleCrud(row, 'allow_update')"
              >
                U
              </button>
            </Tooltip>
            <Tooltip :title="$t('admin.ai.tablePolicy.allowDelete')">
              <button
                v-access:code="['ai_table_policy:update']"
                class="crud-btn"
                :class="row.allow_delete ? 'crud-btn--delete-on' : 'crud-btn--off'"
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
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  user-select: none;
}

.crud-btn:hover {
  transform: scale(1.08);
}

.crud-btn--off {
  background: hsl(var(--muted));
  color: hsl(var(--muted-foreground));
  border-color: hsl(var(--border));
}

.crud-btn--off:hover {
  background: hsl(var(--accent));
}

.crud-btn--read-on {
  background: rgb(34 197 94 / 0.15);
  color: rgb(22 163 74);
  border-color: rgb(34 197 94 / 0.3);
}

.crud-btn--create-on {
  background: rgb(59 130 246 / 0.15);
  color: rgb(37 99 235);
  border-color: rgb(59 130 246 / 0.3);
}

.crud-btn--update-on {
  background: rgb(249 115 22 / 0.15);
  color: rgb(234 88 12);
  border-color: rgb(249 115 22 / 0.3);
}

.crud-btn--delete-on {
  background: rgb(239 68 68 / 0.15);
  color: rgb(220 38 38);
  border-color: rgb(239 68 68 / 0.3);
}
</style>
