<script lang="ts" setup>
/**
 * 租户端工具管理列表页面
 */
import type { ToolDefinitionInfo } from '#/api/tenant/tools';

defineOptions({ name: 'TenantToolList' });

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, message, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  deleteToolApi,
  getToolListApi,
} from '#/api/tenant/tools';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { getToolTypeColor, getToolTypeText, useColumns, useGridFormSchema } from './data';
import ToolForm from './modules/ToolForm.vue';
import TestToolModal from './modules/TestToolModal.vue';

const toolFormRef = ref<InstanceType<typeof ToolForm>>();
const testModalOpen = ref(false);
const testToolId = ref<null | number>(null);

function onTest(row: ToolDefinitionInfo) {
  testToolId.value = row.id;
  testModalOpen.value = true;
}

function onEdit(row: ToolDefinitionInfo) {
  toolFormRef.value?.openEdit(row);
}

let gridReload: () => void;

const { Grid } = useCrudPage<ToolDefinitionInfo>({
  api: {
    list: getToolListApi,
    delete: deleteToolApi,
    resource: '/tenant/ai/tools',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: ToolForm,
  i18nPrefix: 'tenant.ai.tool',
  nameField: 'name',
  defaultSort: '-created_at',
  customActions: {
    test: onTest,
    edit: onEdit,
  },
  onMounted(grid) {
    gridReload = () => grid.commitProxy('query');
  },
});

function onFormSuccess() {
  gridReload();
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- 表单抽屉 -->
    <ToolForm ref="toolFormRef" @success="onFormSuccess" />

    <!-- 测试弹窗 -->
    <TestToolModal
      v-model:open="testModalOpen"
      :tool-id="testToolId"
    />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['agent_tool:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="toolFormRef?.openNew()"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('tenant.ai.tool.create')
              }}</span>
            </div>
          </Card>
        </template>

        <!-- 工具名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:wrench"
              class="size-3.5 text-muted-foreground"
            />
            <span class="font-medium">{{ row.name }}</span>
          </div>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag :color="getToolTypeColor(row.type)">
            {{ getToolTypeText(row.type) }}
          </Tag>
        </template>

        <!-- 描述列 -->
        <template #description_cell="{ row }">
          <Tooltip v-if="row.description" :title="row.description">
            <span class="line-clamp-1 text-muted-foreground">
              {{ row.description }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 系统工具列 -->
        <template #isSystem_cell="{ row }">
          <Tag v-if="row.is_system" color="purple">
            {{ $t('tenant.ai.tool.systemTag') }}
          </Tag>
          <Tag v-else color="default">
            {{ $t('tenant.ai.tool.customTag') }}
          </Tag>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Tag :color="row.is_active ? 'success' : 'default'">
            {{ row.is_active ? $t('common.enabled') : $t('common.disabled') }}
          </Tag>
        </template>

        <!-- 超时列 -->
        <template #timeout_cell="{ row }">
          <span class="text-muted-foreground">{{ row.timeout }}s</span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
