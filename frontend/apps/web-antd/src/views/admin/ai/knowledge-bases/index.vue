<script lang="ts" setup>
/**
 * Knowledge base management page (platform admin) — useCrudList + card grid
 * 平台管理端知识库管理页面 — useCrudList + 卡片网格
 */
import type {
  AdminKnowledgeBaseItem,
  KnowledgeBaseGlobalStats,
} from '#/api/admin/knowledge-bases';

import { computed, onMounted, ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  Pagination,
  Select,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  deleteAdminKnowledgeBaseApi,
  getAdminKnowledgeBaseListApi,
  getKnowledgeBaseStatsApi,
} from '#/api/admin/knowledge-bases';
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
    entityDescription:
      'Manage AI knowledge base configs, documents, and vector indexes / 管理 AI 知识库的配置、文档和向量索引',
    openRecycleBin: () => recycleBinRef.value?.open(),
    contextExtras: () => ({
      total_knowledge_bases: stats.value?.total_knowledge_bases ?? 0,
      total_documents: stats.value?.total_documents ?? 0,
      total_size_bytes: stats.value?.total_size_bytes ?? 0,
    }),
    extra: [
      createStructuredSearchPageOperation({
        description:
          'Search knowledge bases by keyword and optional scope filter / 按关键词和可选作用域搜索知识库',
        params: {
          keyword: {
            type: 'string',
            description: 'Search keyword / 搜索关键词',
          },
          scope: {
            type: 'string',
            description:
              'Resource scope filter: global_shared, admin_only, all_tenants, admin_and_selected_tenants, selected_tenants / 资源作用域过滤',
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
            ? `Searched: ${parts.join(', ')} / 已搜索：${parts.join(', ')}`
            : 'Filters cleared / 已清除过滤条件';
        },
      }),
      createCreateRecordPageOperation({
        description: 'Open the create knowledge base form / 打开新建知识库表单',
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

    <!-- Card grid / 卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="list.length === 0 && !loading"
        class="flex min-h-[300px] items-center justify-center"
      >
        <Empty :description="$t('admin.knowledgeBase.emptyList')">
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
        </Empty>
      </div>
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="item in list"
          :key="item.id"
          class="group relative rounded-xl border border-border bg-card transition-all duration-200 hover:border-primary/30 hover:shadow-md"
        >
          <!-- Card header / 卡片头部 -->
          <div class="flex items-start gap-3 p-4 pb-2">
            <div
              class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"
            >
              <IconifyIcon
                icon="lucide:book-open"
                class="size-5 text-primary"
              />
            </div>
            <div class="min-w-0 flex-1">
              <h4
                class="cursor-pointer truncate text-sm font-semibold text-foreground hover:text-primary"
                @click="onDetailClick(item)"
              >
                {{ item.name }}
              </h4>
              <div class="mt-1 flex flex-wrap items-center gap-1.5">
                <Tag
                  :color="getScopeColor(item.scope)"
                  class="!mr-0 !text-[10px] !leading-4"
                  style="padding: 0 5px"
                >
                  {{ getScopeText(item.scope) }}
                </Tag>
                <Tag
                  :color="item.status === 'active' ? 'success' : 'error'"
                  class="!mr-0 !text-[10px] !leading-4"
                  style="padding: 0 5px"
                >
                  {{ $t(`admin.knowledgeBase.status.${item.status}`) }}
                </Tag>
              </div>
            </div>
            <!-- Action menu / 操作菜单 -->
            <Dropdown
              :trigger="['click']"
              placement="bottomRight"
              class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
            >
              <button
                class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                @click.stop
              >
                <IconifyIcon icon="lucide:more-vertical" class="size-4" />
              </button>
              <template #overlay>
                <Menu
                  @click="
                    (info: { key: string | number }) =>
                      onMenuClick(info.key, item)
                  "
                >
                  <MenuItem key="detail">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:eye" class="size-4" />
                      <span>{{ $t('admin.knowledgeBase.detail') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="edit">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-4" />
                      <span>{{ $t('admin.common.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="delete" class="!text-destructive">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      <span>{{ $t('admin.common.delete') }}</span>
                    </div>
                  </MenuItem>
                </Menu>
              </template>
            </Dropdown>
          </div>

          <!-- Description / 描述 -->
          <p
            v-if="item.description"
            class="mx-4 mb-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
          >
            {{ item.description }}
          </p>
          <p v-else class="mx-4 mb-2 text-xs italic text-muted-foreground/50">
            {{ $t('admin.knowledgeBase.noDescription') }}
          </p>

          <!-- Embedding model chip / Embedding 模型芯片 -->
          <div
            v-if="item.embedding_model_name"
            class="mx-4 mb-3 flex items-center gap-1.5"
          >
            <div
              class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
            >
              <IconifyIcon icon="lucide:cpu" class="size-3" />
              <span class="truncate">{{ item.embedding_model_name }}</span>
            </div>
          </div>

          <!-- Footer: stats + time + quick actions / 底栏：统计+时间+快捷操作 -->
          <div
            class="flex items-center justify-between border-t border-border/50 px-4 py-3 text-[11px] text-muted-foreground"
          >
            <div class="flex items-center gap-3">
              <Tooltip :title="$t('admin.knowledgeBase.field.documentCount')">
                <span class="flex items-center gap-1">
                  <IconifyIcon icon="lucide:file-text" class="size-3.5" />
                  <span class="tabular-nums">{{ item.document_count }}</span>
                </span>
              </Tooltip>
              <Tooltip :title="$t('admin.knowledgeBase.field.totalChunks')">
                <span class="flex items-center gap-1">
                  <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
                  <span class="tabular-nums">{{ item.total_chunks }}</span>
                </span>
              </Tooltip>
              <Tooltip :title="$t('admin.knowledgeBase.field.totalSizeBytes')">
                <span class="flex items-center gap-1">
                  <IconifyIcon icon="lucide:hard-drive" class="size-3.5" />
                  <span>{{ formatFileSize(item.total_size_bytes) }}</span>
                </span>
              </Tooltip>
              <Tooltip :title="formatDate(item.created_at)">
                <span class="flex items-center gap-1">
                  <IconifyIcon icon="lucide:clock" class="size-3.5" />
                  <span>{{ formatRelativeTime(item.created_at) }}</span>
                </span>
              </Tooltip>
            </div>
            <div class="flex items-center gap-2">
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10"
                @click="onDetailClick(item)"
              >
                <IconifyIcon icon="lucide:eye" class="size-3" />
                <span>{{ $t('admin.knowledgeBase.detail') }}</span>
              </button>
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                @click="handleMenuAction('edit', item)"
              >
                <IconifyIcon icon="lucide:pencil" class="size-3" />
                <span>{{ $t('admin.common.edit') }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Spin>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-end">
      <Pagination
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        size="small"
        :show-size-changer="false"
        @change="onPageChange"
      />
    </div>
  </Page>
</template>
