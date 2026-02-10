<script lang="ts" setup>
/**
 * 工具定义管理列表页面（平台端）
 */
import type { AIToolInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIToolList' });

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIToolListApi } from '#/api/admin/ai';
import { $t } from '#/locales';

import { getFormDefaults, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

const { Grid, FormDrawer, onCreate, onRefresh } =
  useCrudPage<AIToolInfo>({
    api: {
      list: getAIToolListApi,
      resource: '/admin/ai/tools',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.ai.tool',
    nameField: 'name',
    defaultSort: '-created_at',
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <IconifyIcon
              icon="lucide:wrench"
              class="size-4 text-primary"
            />
            <span class="font-medium text-foreground">
              {{ row.name }}
            </span>
          </div>
          <div
            v-if="row.description"
            class="mt-0.5 truncate text-xs text-muted-foreground"
          >
            {{ row.description }}
          </div>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag color="blue">
            {{ row.type?.toUpperCase() }}
          </Tag>
        </template>

        <!-- 系统工具列 -->
        <template #isSystem_cell="{ row }">
          <Tag :color="row.is_system ? 'purple' : 'default'">
            {{
              row.is_system
                ? $t('admin.ai.tool.scope.system')
                : $t('admin.ai.tool.scope.tenant')
            }}
          </Tag>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Tag :color="row.is_active ? 'success' : 'default'">
            {{
              row.is_active
                ? $t('admin.common.enabled')
                : $t('admin.common.disabled')
            }}
          </Tag>
        </template>

        <!-- 租户列 -->
        <template #tenantId_cell="{ row }">
          <span v-if="row.tenant_id" class="text-foreground">
            #{{ row.tenant_id }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 超时列 -->
        <template #timeout_cell="{ row }">
          <span class="font-mono text-sm text-muted-foreground">
            {{ row.timeout }}s
          </span>
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['ai_tool:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.ai.tool.create')
              }}</span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
