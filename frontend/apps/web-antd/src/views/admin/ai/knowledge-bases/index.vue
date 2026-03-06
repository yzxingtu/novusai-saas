<script lang="ts" setup>
/**
 * 平台管理端知识库管理页面 — useCrudList + 卡片网格
 */
import type {
  AdminKnowledgeBaseItem,
  KnowledgeBaseGlobalStats,
} from '#/api/admin/knowledge-bases';

import { computed, onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Dropdown,
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
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import {
  getFormDefaults,
  getScopeColor,
  getScopeOptions,
  getScopeText,
} from './data';
import Detail from './modules/detail.vue';
import Form from './modules/form.vue';

defineOptions({ name: 'AdminKnowledgeBaseList' });

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

// ========== 声明式 CRUD ==========
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
  createPermission: 'ai_knowledge_base:create',
});

// ========== 详情抽屉 ==========
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: Detail,
});

function onDetailClick(row: AdminKnowledgeBaseItem) {
  detailDrawerApi.setData({ id: row.id, name: row.name });
  detailDrawerApi.open();
}

// ========== 回收站 ==========
const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
  null,
);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() {
  recycleBinRef.value?.open();
}

// ========== 搜索过滤 ==========
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

// ========== 辅助 ==========

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

const cleanupPageContext = registerPageContext('admin/ai/knowledge-bases', () => ({
  page_key: 'admin.ai.knowledge-bases',
  page_title: $t('admin.knowledgeBase.name'),
  page_data: {
    resource: '/admin/ai/knowledge-bases',
    total_knowledge_bases: stats.value?.total_knowledge_bases ?? 0,
    total_documents: stats.value?.total_documents ?? 0,
    total_size_bytes: stats.value?.total_size_bytes ?? 0,
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.knowledge-bases', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the knowledge base list and stats',
    readonly: true,
    handler: async () => {
      await loadList();
      await loadStats();
      return { success: true, message: 'Knowledge base list refreshed' };
    },
  },
  {
    name: 'create_knowledge_base',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open the create knowledge base form',
    readonly: false,
    handler: async () => {
      onCreate();
      return { success: true, message: 'Create knowledge base form opened' };
    },
  },
  {
    name: 'search_knowledge_bases',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search knowledge bases by keyword',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Search keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      searchKeyword.value = keyword;
      doSearch();
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  {
    name: 'view_recycle_bin',
    label: $t('shared.pageOperation.restoreRecord'),
    description: 'Open the recycle bin drawer',
    readonly: true,
    handler: async () => {
      openRecycleBin();
      return { success: true, message: 'Recycle bin opened' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.knowledgeBase.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <FormDrawer @success="onFormSuccess" />
    <DetailDrawer @success="onDetailSuccess" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/knowledge-bases"
      @restored="loadList"
    />

    <!-- 统计卡片 -->
    <div v-if="stats" class="grid grid-cols-4 gap-4">
      <div
        class="flex items-center gap-3.5 rounded-xl border border-border/60 bg-card p-4 transition-colors hover:border-border"
      >
        <div
          class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10"
        >
          <IconifyIcon icon="lucide:book-open" class="size-5.5 text-primary" />
        </div>
        <div>
          <div class="text-2xl font-bold tabular-nums text-foreground">
            {{ stats.total_knowledge_bases }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ $t('admin.knowledgeBase.stats.totalKnowledgeBases') }}
          </div>
        </div>
      </div>
      <div
        class="flex items-center gap-3.5 rounded-xl border border-border/60 bg-card p-4 transition-colors hover:border-border"
      >
        <div
          class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-success/10"
        >
          <IconifyIcon icon="lucide:file-text" class="size-5.5 text-success" />
        </div>
        <div>
          <div class="text-2xl font-bold tabular-nums text-foreground">
            {{ stats.total_documents }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ $t('admin.knowledgeBase.stats.totalDocuments') }}
          </div>
        </div>
      </div>
      <div
        class="flex items-center gap-3.5 rounded-xl border border-border/60 bg-card p-4 transition-colors hover:border-border"
      >
        <div
          class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-warning/10"
        >
          <IconifyIcon icon="lucide:puzzle" class="size-5.5 text-warning" />
        </div>
        <div>
          <div class="text-2xl font-bold tabular-nums text-foreground">
            {{ stats.total_chunks }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ $t('admin.knowledgeBase.stats.totalChunks') }}
          </div>
        </div>
      </div>
      <div
        class="flex items-center gap-3.5 rounded-xl border border-border/60 bg-card p-4 transition-colors hover:border-border"
      >
        <div
          class="flex size-11 shrink-0 items-center justify-center rounded-xl bg-destructive/10"
        >
          <IconifyIcon
            icon="lucide:hard-drive"
            class="size-5.5 text-destructive"
          />
        </div>
        <div>
          <div class="text-2xl font-bold tabular-nums text-foreground">
            {{ formatFileSize(stats.total_size_bytes) }}
          </div>
          <div class="text-xs text-muted-foreground">
            {{ $t('admin.knowledgeBase.stats.totalStorage') }}
          </div>
        </div>
      </div>
    </div>

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
      <Tooltip :title="$t('common.recycleBin.title')">
        <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
          <Button @click="openRecycleBin">
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
          </Button>
        </Badge>
      </Tooltip>
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

    <!-- 卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="list.length === 0 && !loading"
        class="flex flex-col items-center justify-center py-20"
      >
        <div
          class="mb-3 flex size-16 items-center justify-center rounded-2xl bg-muted"
        >
          <IconifyIcon
            icon="lucide:book-open"
            class="size-8 text-muted-foreground"
          />
        </div>
        <p class="text-sm text-muted-foreground">
          {{ $t('admin.knowledgeBase.searchTest.noResults') }}
        </p>
      </div>
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="item in list"
          :key="item.id"
          class="group cursor-pointer rounded-xl border border-border/60 bg-card transition-all hover:border-primary/30 hover:shadow-md"
          @click="onDetailClick(item)"
        >
          <!-- 卡片头部 -->
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
              <h4 class="truncate text-sm font-semibold text-foreground">
                {{ item.name }}
              </h4>
              <div class="mt-1 flex flex-wrap items-center gap-1.5">
                <Tag
                  :color="getScopeColor(item.scope)"
                  style="
                    padding: 0 5px;
                    margin: 0;
                    font-size: 10px;
                    line-height: 16px;
                  "
                >
                  {{ getScopeText(item.scope) }}
                </Tag>
                <Tag
                  :color="item.status === 'active' ? 'success' : 'error'"
                  style="
                    padding: 0 5px;
                    margin: 0;
                    font-size: 10px;
                    line-height: 16px;
                  "
                >
                  {{ $t(`admin.knowledgeBase.status.${item.status}`) }}
                </Tag>
              </div>
            </div>
            <!-- 操作菜单 -->
            <Dropdown :trigger="['click']" placement="bottomRight" @click.stop>
              <Button
                type="text"
                size="small"
                class="!size-7 !min-w-0 shrink-0 !p-0 opacity-0 transition-opacity group-hover:opacity-100"
                @click.stop
              >
                <IconifyIcon
                  icon="lucide:ellipsis-vertical"
                  class="size-4 text-muted-foreground"
                />
              </Button>
              <template #overlay>
                <Menu
                  @click="
                    (info: { key: string | number }) =>
                      onMenuClick(info.key, item)
                  "
                >
                  <MenuItem key="detail">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:eye" class="size-3.5" />
                      <span>{{ $t('admin.knowledgeBase.detail') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="edit">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                      <span>{{ $t('admin.common.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="delete" class="!text-destructive">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                      <span>{{ $t('admin.common.delete') }}</span>
                    </div>
                  </MenuItem>
                </Menu>
              </template>
            </Dropdown>
          </div>

          <!-- 描述 -->
          <div class="px-4 pb-2">
            <p
              v-if="item.description"
              class="line-clamp-2 text-xs leading-relaxed text-muted-foreground"
            >
              {{ item.description }}
            </p>
            <p v-else class="text-xs text-muted-foreground/50">—</p>
          </div>

          <!-- Embedding 模型 -->
          <div
            v-if="item.embedding_model_name"
            class="mx-4 mb-2 flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <IconifyIcon icon="lucide:cpu" class="size-3 shrink-0" />
            <span class="truncate">{{ item.embedding_model_name }}</span>
          </div>

          <!-- 统计数据 -->
          <div
            class="flex items-center gap-4 border-t border-border/40 px-4 py-3 text-xs text-muted-foreground"
          >
            <div
              class="flex items-center gap-1"
              :title="$t('admin.knowledgeBase.field.documentCount')"
            >
              <IconifyIcon icon="lucide:file-text" class="size-3.5" />
              <span class="tabular-nums">{{ item.document_count }}</span>
            </div>
            <div
              class="flex items-center gap-1"
              :title="$t('admin.knowledgeBase.field.totalChunks')"
            >
              <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
              <span class="tabular-nums">{{ item.total_chunks }}</span>
            </div>
            <div
              class="flex items-center gap-1"
              :title="$t('admin.knowledgeBase.field.totalSizeBytes')"
            >
              <IconifyIcon icon="lucide:hard-drive" class="size-3.5" />
              <span>{{ formatFileSize(item.total_size_bytes) }}</span>
            </div>
            <div class="ml-auto flex items-center gap-1">
              <IconifyIcon icon="lucide:clock" class="size-3.5" />
              <span>{{ formatDate(item.created_at) }}</span>
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
