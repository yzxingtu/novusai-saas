<script lang="ts" setup>
/**
 * Knowledge base management page (platform admin) — useCrudList + card grid
 * 平台管理端知识库管理页面 — useCrudList + 卡片网格
 */
import type {
  AdminKnowledgeBaseItem,
  KnowledgeBaseGlobalStats,
} from '#/api/admin/knowledge-bases';
import type { KnowledgeBaseCardViewModel } from '#/components/business/knowledge-base-card-grid/KnowledgeBaseCardGrid.vue';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, Button, Input, Select, Tooltip } from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  deleteAdminKnowledgeBaseApi,
  getAdminKnowledgeBaseListApi,
  getKnowledgeBaseStatsApi,
} from '#/api/admin/knowledge-bases';
import KnowledgeBaseCardGrid from '#/components/business/knowledge-base-card-grid/KnowledgeBaseCardGrid.vue';
import {
  createCreateRecordPageOperation,
  createStructuredSearchPageOperation,
  useCrudList,
} from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import AIPageHeroCard from '../_shared/AIPageHeroCard.vue';
import {
  getFormDefaults,
  getScopeColor,
  getScopeOptions,
  getScopeText,
  useFormSchema,
  useGridFormSchema,
} from './data';
import Detail from './modules/detail.vue';
import Form from './modules/form.vue';

defineOptions({ name: 'AdminKnowledgeBaseList' });
const router = useRouter();

// ========== Stats cards / 统计卡片 ==========
const stats = ref<KnowledgeBaseGlobalStats | null>(null);

async function loadStats() {
  try {
    stats.value = await getKnowledgeBaseStatsApi();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

onMounted(loadStats);

// ========== Declarative CRUD / 声明式 CRUD ==========
const {
  list,
  total,
  loading,
  currentPage,
  pageSize,
  searchKeyword,
  FormDrawer,
  loadList,
  onCreate,
  onSearch,
  onPageChange,
  handleMenuAction,
} = useCrudList<AdminKnowledgeBaseItem>({
  api: {
    list: getAdminKnowledgeBaseListApi,
    delete: deleteAdminKnowledgeBaseApi,
    resource: '/admin/ai/knowledge-bases',
  },
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.knowledgeBase',
  nameField: 'name',
  defaultSort: '-created_at',
  pageSize: 12,
  recycleBin: true,
  createPermission: 'ai_knowledge_base:create',
  ai: {
    formSchema: useFormSchema,
    searchSchema: useGridFormSchema,
    entityName: $t('admin.knowledgeBase.name'),
    entityDescription: $t('admin.knowledgeBase.ai.entityDescription'),
    openRecycleBin: () => recycleBinRef.value?.open(),
    contextExtras: () => ({
      total_knowledge_bases: stats.value?.total_knowledge_bases ?? 0,
      total_documents: stats.value?.total_documents ?? 0,
      total_size_bytes: stats.value?.total_size_bytes ?? 0,
    }),
    extra: [
      createStructuredSearchPageOperation({
        description: $t('admin.knowledgeBase.ai.structuredSearchDescription'),
        params: {
          keyword: {
            type: 'string',
            description: $t('admin.knowledgeBase.ai.paramKeyword'),
          },
          scope: {
            type: 'string',
            description: $t('admin.knowledgeBase.ai.paramScope'),
          },
        },
        normalizeParams: (params) => ({
          keyword: String(params?.keyword ?? ''),
          scope: String(params?.scope ?? ''),
        }),
        runSearch: async ({ keyword, scope }) => {
          searchKeyword.value = keyword;
          scopeFilter.value = scope || undefined;
          doSearch();
        },
        successMessage: ({ keyword, scope }) => {
          const parts: string[] = [];
          if (keyword) parts.push(`keyword="${keyword}"`);
          if (scope) parts.push(`scope="${scope}"`);
          return parts.length > 0
            ? $t('admin.knowledgeBase.ai.searchApplied', {
                detail: parts.join(', '),
              })
            : $t('admin.knowledgeBase.ai.filtersCleared');
        },
      }),
      createCreateRecordPageOperation({
        description: $t('admin.knowledgeBase.ai.openCreateForm'),
        action: () => {
          onCreate();
        },
      }),
    ],
  },
});

// ========== Detail drawer / 详情抽屉 ==========
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: Detail,
});

function onDetailClick(row: AdminKnowledgeBaseItem) {
  detailDrawerApi.setData({ id: row.id, name: row.name });
  detailDrawerApi.open();
}

// ========== Recycle bin / 回收站 ==========
const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
  null,
);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() {
  recycleBinRef.value?.open();
}

const heroMetrics = computed(() => [
  {
    key: 'knowledgeBases',
    label: $t('admin.knowledgeBase.stats.totalKnowledgeBases'),
    value: stats.value?.total_knowledge_bases ?? '-',
  },
  {
    key: 'documents',
    label: $t('admin.knowledgeBase.stats.totalDocuments'),
    value: stats.value?.total_documents ?? '-',
  },
  {
    key: 'chunks',
    label: $t('admin.knowledgeBase.stats.totalChunks'),
    value: stats.value?.total_chunks ?? '-',
  },
  {
    key: 'storage',
    label: $t('admin.knowledgeBase.stats.totalStorage'),
    value: stats.value ? formatFileSize(stats.value.total_size_bytes) : '-',
  },
]);

const heroChips = computed(() => {
  const chips = [
    {
      key: 'dimensions',
      icon: 'lucide:database-zap',
      className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
      text: `${$t('admin.knowledgeBase.field.scope')} / ${$t('admin.knowledgeBase.document.title')} / ${$t('admin.knowledgeBase.stats.totalStorage')}`,
    },
    {
      key: 'recycle',
      icon: 'lucide:trash-2',
      className: 'bg-background/90 text-foreground',
      text: `${recycleBinCount.value} ${$t('common.recycleBin.title')}`,
    },
  ];

  if (scopeFilter.value) {
    chips.push({
      key: 'scope',
      icon: 'lucide:filter',
      className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
      text: getScopeText(scopeFilter.value),
    });
  }

  return chips;
});

// ========== Search filters / 搜索过滤 ==========
const scopeFilter = ref<string | undefined>(undefined);

function doSearch() {
  const params: Record<string, unknown> = {};
  if (searchKeyword.value.trim()) {
    params['filter[name][ilike]'] = searchKeyword.value.trim();
  }
  if (scopeFilter.value) {
    params['filter[scope][eq]'] = scopeFilter.value;
  }
  onSearch(params);
}

// ========== Helpers / 辅助 ==========

function onMenuClick(key: number | string, row: AdminKnowledgeBaseItem) {
  if (String(key) === 'detail') {
    onDetailClick(row);
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
    statusColor: item.status === 'active' ? 'success' : 'error',
    statusText: $t(`admin.knowledgeBase.status.${item.status}`),
    scopeColor: getScopeColor(item.scope),
    scopeText: getScopeText(item.scope),
    documentCount: item.document_count,
    totalChunks: item.total_chunks,
    totalSizeText: formatFileSize(item.total_size_bytes),
    createdAtText: formatRelativeTime(item.created_at),
    createdAtTitle: formatDate(item.created_at),
    menuActions: [
      {
        key: 'detail',
        label: $t('admin.knowledgeBase.detail'),
        icon: 'lucide:eye',
      },
      {
        key: 'edit',
        label: $t('admin.common.edit'),
        icon: 'lucide:pencil',
      },
      {
        key: 'delete',
        label: $t('admin.common.delete'),
        icon: 'lucide:trash-2',
        danger: true,
      },
    ],
    secondaryAction: {
      key: 'edit',
      label: $t('admin.common.edit'),
      icon: 'lucide:pencil',
    },
  })),
);

function onFormSuccess() {
  loadList();
  loadStats();
}

function onDetailSuccess() {
  loadList();
  loadStats();
}
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <FormDrawer @success="onFormSuccess" />
    <DetailDrawer @success="onDetailSuccess" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/knowledge-bases"
      @restored="loadList"
    />

    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.knowledgeBase.pageDesc')"
      icon="lucide:book-open"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('admin.knowledgeBase.title')"
    />

    <!-- 搜索栏 + 创建按钮 -->
    <div class="flex items-center gap-3">
      <Input
        v-model:value="searchKeyword"
        :placeholder="$t('admin.knowledgeBase.field.name')"
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
      <Select
        v-model:value="scopeFilter"
        :placeholder="$t('admin.knowledgeBase.field.scope')"
        :options="getScopeOptions()"
        allow-clear
        class="w-36"
        @change="doSearch"
      />
      <span v-access:code="['ai_knowledge_base:recycle_bin']">
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
      <span v-access:code="['ai_long_term_memory_debug:list']">
        <Tooltip :title="$t('admin.ai.memoryDebug.title')">
          <Button @click="router.push('/admin/ai/debug/memory')">
            <template #icon>
              <IconifyIcon icon="lucide:brain-circuit" class="size-4" />
            </template>
          </Button>
        </Tooltip>
      </span>
      <div class="flex-1"></div>
      <Button
        v-access:code="['ai_knowledge_base:create']"
        type="primary"
        @click="onCreate"
      >
        <template #icon>
          <IconifyIcon icon="lucide:plus" class="size-4" />
        </template>
        {{ $t('admin.knowledgeBase.create') }}
      </Button>
    </div>

    <KnowledgeBaseCardGrid
      :create-label="$t('admin.knowledgeBase.create')"
      :current-page="currentPage"
      :detail-action-label="$t('admin.knowledgeBase.detail')"
      :empty-description="$t('admin.knowledgeBase.emptyList')"
      :loading="loading"
      :page-size="pageSize"
      :stat-titles="{
        documents: $t('admin.knowledgeBase.field.documentCount'),
        chunks: $t('admin.knowledgeBase.field.totalChunks'),
        size: $t('admin.knowledgeBase.field.totalSizeBytes'),
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
          if (row) onDetailClick(row);
        }
      "
    />
  </Page>
</template>
