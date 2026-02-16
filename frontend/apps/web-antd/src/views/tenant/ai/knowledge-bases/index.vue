<script lang="ts" setup>
/**
 * 租户端知识库管理列表页面
 */
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';

defineOptions({ name: 'TenantKnowledgeBaseList' });

import { ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  deleteKnowledgeBaseApi,
  getKnowledgeBaseListApi,
} from '#/api/tenant/knowledge-bases';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import {
  getKBStatusColor,
  getKBStatusText,
  useColumns,
  useGridFormSchema,
} from './data';
import KnowledgeBaseDetail from './modules/KnowledgeBaseDetail.vue';
import KnowledgeBaseForm from './modules/KnowledgeBaseForm.vue';

const kbFormRef = ref<InstanceType<typeof KnowledgeBaseForm>>();

// 详情抽屉
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: KnowledgeBaseDetail,
});

function onDetail(row: KnowledgeBaseItem) {
  detailDrawerApi
    .setData({ id: row.id, name: row.name })
    .open();
}

function onEdit(row: KnowledgeBaseItem) {
  kbFormRef.value?.openEdit(row);
}

const { Grid, onRefresh: gridReload } = useCrudPage<KnowledgeBaseItem>({
  api: {
    list: getKnowledgeBaseListApi,
    delete: deleteKnowledgeBaseApi,
    resource: '/tenant/ai/knowledge-bases',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: KnowledgeBaseForm,
  i18nPrefix: 'tenant.knowledgeBase',
  nameField: 'name',
  defaultSort: '-created_at',
  recycleBin: true,
  customActions: {
    detail: onDetail,
    edit: onEdit,
  },
});

function onFormSuccess() {
  gridReload();
}

function onDetailSuccess() {
  gridReload();
}
</script>

<template>
  <Page auto-content-height :description="$t('tenant.knowledgeBase.pageDesc')" content-class="flex flex-col gap-4">
    <!-- 表单抽屉 -->
    <KnowledgeBaseForm ref="kbFormRef" @success="onFormSuccess" />
    <!-- 详情抽屉 -->
    <DetailDrawer @success="onDetailSuccess" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['knowledge_base:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="kbFormRef?.openNew()"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('tenant.knowledgeBase.create')
              }}</span>
            </div>
          </Card>
        </template>

        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:book-open"
              class="size-3.5 text-muted-foreground"
            />
            <span
              class="cursor-pointer font-medium text-primary hover:underline"
              @click="onDetail(row)"
            >{{ row.name }}</span>
          </div>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getKBStatusColor(row.status)">
            {{ getKBStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 模型列 -->
        <template #model_cell="{ row }">
          <span v-if="row.embedding_model_name" class="text-muted-foreground">
            {{ row.embedding_model_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 大小列 -->
        <template #size_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatFileSize(row.total_size_bytes) }}
          </span>
        </template>

        <!-- 描述列 -->
        <template #desc_cell="{ row }">
          <Tooltip v-if="row.description" :title="row.description">
            <span class="line-clamp-1 text-muted-foreground">
              {{ row.description }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
