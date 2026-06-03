<script lang="ts" setup>
/**
 * 企业端知识库管理列表页面 — useCrudList + 卡片网格
 */
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';
import type { KnowledgeBaseCardViewModel } from '#/components/business/knowledge-base-card-grid/KnowledgeBaseCardGrid.vue';

import { computed, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, Button, Input, Tooltip } from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  deleteKnowledgeBaseApi,
  getKnowledgeBaseListApi,
} from '#/api/tenant/knowledge-bases';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import KnowledgeBaseCardGrid from '#/components/business/knowledge-base-card-grid/KnowledgeBaseCardGrid.vue';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { formatFileSize } from '#/utils/file';
import { buildFormExtraData } from '#/utils/form-extra-data';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import {
  getKBStatusColor,
  getKBStatusText,
  isTenantOwnedKnowledgeBase,
} from './data';
import KnowledgeBaseDetail from './modules/KnowledgeBaseDetail.vue';
import KnowledgeBaseForm from './modules/KnowledgeBaseForm.vue';

defineOptions({ name: 'TenantKnowledgeBaseList' });

/** Editable/deletable = owned by current tenant (tenant_id is owner_tenant_id synonym) */
function isTenantManageableKb(row: KnowledgeBaseItem): boolean {
  return isTenantOwnedKnowledgeBase(row.tenant_id);
}

// ========== 声明式 CRUD / declarative CRUD ==========
const {
  list,
  total,
  loading,
  currentPage,
  pageSize,
  searchKeyword,
  loadList,
  onSearch,
  onPageChange,
  handleMenuAction,
} = useCrudList<KnowledgeBaseItem>({
  api: {
    list: getKnowledgeBaseListApi,
    delete: deleteKnowledgeBaseApi,
    resource: '/tenant/ai/knowledge-bases',
  },
  i18nPrefix: 'tenant.knowledgeBase',
  nameField: 'name',
  defaultSort: '-created_at',
  pageSize: 12,
  recycleBin: true,
  customActions: {
    edit: (row) => kbFormRef.value?.openEdit(row, buildFormExtraData()),
  },
});

// ========== 回收站 / recycle bin ==========
const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
  null,
);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() {
  recycleBinRef.value?.open();
}

const heroMetrics = computed(() => [
  {
    key: 'total',
    label: $t('tenant.knowledgeBase.title'),
    value: total.value,
  },
  {
    key: 'recycle',
    label: $t('common.recycleBin.title'),
    value: recycleBinCount.value,
  },
]);

const heroChips = computed(() => [
  {
    key: 'focus',
    icon: 'lucide:database-zap',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('tenant.knowledgeBase.document.title')} / ${$t('tenant.knowledgeBase.searchTest.title')} / ${$t('tenant.knowledgeBase.ragConfig.title')}`,
  },
  {
    key: 'storage',
    icon: 'lucide:hard-drive',
    className: 'bg-background/90 text-foreground',
    text: `${$t('tenant.knowledgeBase.field.totalChunks')} / ${$t('tenant.knowledgeBase.field.totalSizeBytes')}`,
  },
]);

// ========== KnowledgeBaseForm (ref 模式) / form by ref ==========
const kbFormRef = ref<InstanceType<typeof KnowledgeBaseForm>>();

function openKnowledgeBaseCreate(defaults: Record<string, unknown> = {}) {
  kbFormRef.value?.openNew(
    buildFormExtraData({
      defaults,
    }),
  );
}

function onCreateKB() {
  openKnowledgeBaseCreate();
}

// ========== 详情抽屉 / detail drawer ==========
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: KnowledgeBaseDetail,
});

function onDetail(row: KnowledgeBaseItem) {
  openKnowledgeBaseDetail(row);
}

function openKnowledgeBaseDetail(row: KnowledgeBaseItem) {
  detailDrawerApi
    .setData({
      id: row.id,
      name: row.name,
      scope: row.scope,
      tenantId: row.tenant_id,
    })
    .open();
}

// ========== 搜索 / search ==========
function doSearch() {
  const params: Record<string, unknown> = {};
  if (searchKeyword.value.trim()) {
    params['filter[name][ilike]'] = searchKeyword.value.trim();
  }
  onSearch(params);
}

// ========== 菜单操作 / row menu actions ==========
function onMenuClick(key: number | string, row: KnowledgeBaseItem) {
  if (String(key) === 'detail') {
    onDetail(row);
  } else {
    handleMenuAction(String(key), row);
  }
}

const cardItems = computed<KnowledgeBaseCardViewModel[]>(() =>
  list.value.map((item) => ({
    id: item.id,
    name: item.name,
    description: item.description,
    embeddingModelName: item.embedding_model_name,
    statusColor: getKBStatusColor(item.status),
    statusText: getKBStatusText(item.status),
    scopeColor:
      item.scope && item.scope !== 'all_tenants'
        ? getScopeColor(item.scope)
        : undefined,
    scopeText:
      item.scope && item.scope !== 'all_tenants'
        ? getScopeText(item.scope)
        : undefined,
    documentCount: item.document_count,
    totalChunks: item.total_chunks,
    totalSizeText: formatFileSize(item.total_size_bytes),
    createdAtText: formatRelativeTime(item.created_at),
    createdAtTitle: formatDate(item.created_at),
    menuActions: [
      {
        key: 'detail',
        label: $t('tenant.knowledgeBase.detail'),
        icon: 'lucide:eye',
      },
      ...(isTenantManageableKb(item)
        ? [
            {
              key: 'edit',
              label: $t('tenant.knowledgeBase.edit'),
              icon: 'lucide:pencil',
            },
            {
              key: 'delete',
              label: $t('tenant.common.delete'),
              icon: 'lucide:trash-2',
              danger: true,
            },
          ]
        : []),
    ],
  })),
);
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('tenant.knowledgeBase.pageDesc')"
      icon="lucide:book-open"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('tenant.knowledgeBase.title')"
    />

    <KnowledgeBaseForm ref="kbFormRef" @success="loadList" />
    <DetailDrawer @success="loadList" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/tenant/ai/knowledge-bases"
      @restored="loadList"
    />

    <!-- 搜索栏 + 创建按钮 -->
    <div class="flex items-center gap-3">
      <Input
        v-model:value="searchKeyword"
        :placeholder="$t('tenant.knowledgeBase.search')"
        allow-clear
        class="max-w-xs"
        @press-enter="doSearch"
        @clear="doSearch"
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-4 text-muted-foreground"
          />
        </template>
      </Input>
      <span v-access:code="['knowledge_base:recycle_bin']">
        <Tooltip :title="$t('common.recycleBin.title')">
          <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
            <Button @click="openRecycleBin">
              <template #icon>
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
              </template>
            </Button>
          </Badge>
        </Tooltip>
      </span>
      <div class="flex-1"></div>
      <Button
        v-access:code="['knowledge_base:create']"
        type="primary"
        @click="onCreateKB"
      >
        <template #icon>
          <IconifyIcon icon="lucide:plus" class="size-4" />
        </template>
        {{ $t('tenant.knowledgeBase.create') }}
      </Button>
    </div>

    <KnowledgeBaseCardGrid
      card-clickable
      :create-label="$t('tenant.knowledgeBase.create')"
      :current-page="currentPage"
      :empty-description="$t('tenant.knowledgeBase.empty')"
      :loading="loading"
      :page-size="pageSize"
      :stat-titles="{
        documents: $t('tenant.knowledgeBase.field.documentCount'),
        chunks: $t('tenant.knowledgeBase.field.totalChunks'),
        size: $t('tenant.knowledgeBase.field.totalSizeBytes'),
      }"
      :total="total"
      :value="cardItems"
      @menu-action="
        (actionKey, itemId) => {
          const row = list.find((item) => item.id === itemId);
          if (row) onMenuClick(actionKey, row);
        }
      "
      @page-change="onPageChange"
      @select="
        (itemId) => {
          const row = list.find((item) => item.id === itemId);
          if (row) onDetail(row);
        }
      "
    />
  </Page>
</template>
