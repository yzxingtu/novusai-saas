<script lang="ts" setup>
/**
 * 平台管理端知识库管理页面
 */
import type { AdminKnowledgeBaseItem } from '#/api/admin/knowledge-bases';

defineOptions({ name: 'AdminKnowledgeBaseList' });

import { onMounted, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, Statistic, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  deleteAdminKnowledgeBaseApi,
  getAdminKnowledgeBaseListApi,
  getKnowledgeBaseStatsApi,
} from '#/api/admin/knowledge-bases';
import type { KnowledgeBaseGlobalStats } from '#/api/admin/knowledge-bases';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import { getFormDefaults, getScopeColor, getScopeOptions, useColumns, useGridFormSchema } from './data';
import Detail from './modules/detail.vue';
import Form from './modules/form.vue';

// ========== 统计卡片 ==========
const stats = ref<KnowledgeBaseGlobalStats | null>(null);

async function loadStats() {
  try {
    stats.value = await getKnowledgeBaseStatsApi();
  } catch {
    // handled
  }
}

onMounted(loadStats);

// ========== 表格 ==========
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: Detail,
});

function onDetailClick(row: AdminKnowledgeBaseItem) {
  detailDrawerApi.setData({ id: row.id, name: row.name });
  detailDrawerApi.open();
}

const { Grid, FormDrawer, onRefresh } = useCrudPage<AdminKnowledgeBaseItem>({
  api: {
    list: getAdminKnowledgeBaseListApi,
    delete: deleteAdminKnowledgeBaseApi,
    resource: '/admin/ai/knowledge-bases',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.knowledgeBase',
  nameField: 'name',
  defaultSort: '-created_at',
  createPermission: 'ai_knowledge_base:create',
  customActions: {
    detail: onDetailClick,
  },
});

function getScopeText(scope: string) {
  const opt = getScopeOptions().find((o) => o.value === scope);
  return opt ? opt.label : scope;
}
</script>

<template>
  <Page auto-content-height :description="$t('admin.knowledgeBase.pageDesc')" content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />
    <DetailDrawer @success="() => { onRefresh(); loadStats(); }" />

    <!-- 统计卡片 -->
    <div v-if="stats" class="grid grid-cols-4 gap-4">
      <Card size="small">
        <Statistic
          :title="$t('admin.knowledgeBase.stats.totalKnowledgeBases')"
          :value="stats.total_knowledge_bases"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:book-open" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
      <Card size="small">
        <Statistic
          :title="$t('admin.knowledgeBase.stats.totalDocuments')"
          :value="stats.total_documents"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:file-text" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
      <Card size="small">
        <Statistic
          :title="$t('admin.knowledgeBase.stats.totalChunks')"
          :value="stats.total_chunks"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:puzzle" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
      <Card size="small">
        <Statistic
          :title="$t('admin.knowledgeBase.stats.totalStorage')"
          :value="formatFileSize(stats.total_size_bytes)"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:hard-drive" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
    </div>

    <!-- 列表 -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- Scope 列 -->
        <template #scope_cell="{ row }">
          <Tag :color="getScopeColor(row.scope)">
            {{ getScopeText(row.scope) }}
          </Tag>
        </template>

        <!-- 存储大小列 -->
        <template #size_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatFileSize(row.total_size_bytes) }}
          </span>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="row.status === 'active' ? 'success' : 'error'">
            {{ $t(`admin.knowledgeBase.status.${row.status}`) }}
          </Tag>
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
