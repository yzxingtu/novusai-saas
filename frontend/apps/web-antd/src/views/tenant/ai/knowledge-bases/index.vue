<script lang="ts" setup>
/**
 * 租户端知识库管理列表页面 — useCrudList + 卡片网格
 */
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';

import { computed, onUnmounted, ref } from 'vue';

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
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  deleteKnowledgeBaseApi,
  getKnowledgeBaseListApi,
} from '#/api/tenant/knowledge-bases';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getKBStatusColor, getKBStatusText } from './data';
import KnowledgeBaseDetail from './modules/KnowledgeBaseDetail.vue';
import KnowledgeBaseForm from './modules/KnowledgeBaseForm.vue';

defineOptions({ name: 'TenantKnowledgeBaseList' });

// ========== 声明式 CRUD ==========
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
    edit: (row) => kbFormRef.value?.openEdit(row),
  },
});

// ========== 回收站 ==========
const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
  null,
);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() {
  recycleBinRef.value?.open();
}

// ========== KnowledgeBaseForm (ref 模式) ==========
const kbFormRef = ref<InstanceType<typeof KnowledgeBaseForm>>();

// ========== 详情抽屉 ==========
const [DetailDrawer, detailDrawerApi] = useVbenDrawer({
  connectedComponent: KnowledgeBaseDetail,
});

function onDetail(row: KnowledgeBaseItem) {
  detailDrawerApi
    .setData({ id: row.id, name: row.name, scope: row.scope })
    .open();
}

// ========== 搜索 ==========
function doSearch() {
  const params: Record<string, unknown> = {};
  if (searchKeyword.value.trim()) {
    params['filter[name][ilike]'] = searchKeyword.value.trim();
  }
  onSearch(params);
}

// ========== 菜单操作 ==========
function onMenuClick(key: number | string, row: KnowledgeBaseItem) {
  if (String(key) === 'detail') {
    onDetail(row);
  } else {
    handleMenuAction(String(key), row);
  }
}

const cleanupPageContext = registerPageContext('tenant/ai/knowledge-bases', () => ({
  page_key: 'tenant.ai.knowledge-bases',
  page_title: $t('tenant.knowledgeBase.name'),
  page_data: {
    resource: '/tenant/ai/knowledge-bases',
    total: total.value,
  },
}));

const cleanupPageOps = registerPageOperations('tenant.ai.knowledge-bases', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the knowledge base list',
    readonly: true,
    handler: async () => {
      await loadList();
      return { success: true, message: 'Knowledge base list refreshed' };
    },
  },
  {
    name: 'create_knowledge_base',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open the create knowledge base form',
    readonly: false,
    handler: async () => {
      kbFormRef.value?.openNew();
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
      searchKeyword.value = (params?.keyword as string) || '';
      doSearch();
      return { success: true, message: `Searched for: ${searchKeyword.value}` };
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
    :description="$t('tenant.knowledgeBase.pageDesc')"
    content-class="flex flex-col gap-4"
  >
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
        v-access:code="['knowledge_base:create']"
        type="primary"
        @click="kbFormRef?.openNew()"
      >
        <template #icon>
          <IconifyIcon icon="lucide:plus" class="size-4" />
        </template>
        {{ $t('tenant.knowledgeBase.create') }}
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
        <p class="mb-4 text-sm text-muted-foreground">
          {{ $t('tenant.knowledgeBase.empty') }}
        </p>
        <Button
          v-access:code="['knowledge_base:create']"
          type="primary"
          @click="kbFormRef?.openNew()"
        >
          <template #icon>
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </template>
          {{ $t('tenant.knowledgeBase.create') }}
        </Button>
      </div>
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="item in list"
          :key="item.id"
          class="group cursor-pointer rounded-xl border border-border/60 bg-card transition-all hover:border-primary/30 hover:shadow-md"
          @click="onDetail(item)"
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
              <div class="mt-1 flex items-center gap-1.5">
                <Tag
                  :color="getKBStatusColor(item.status)"
                  style="
                    padding: 0 5px;
                    margin: 0;
                    font-size: 10px;
                    line-height: 16px;
                  "
                >
                  {{ getKBStatusText(item.status) }}
                </Tag>
                <Tag
                  v-if="item.scope && item.scope !== 'all_tenants'"
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
                      <span>{{ $t('tenant.knowledgeBase.detail') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem v-if="item.scope === 'all_tenants'" key="edit">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                      <span>{{ $t('tenant.knowledgeBase.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="item.scope === 'all_tenants'"
                    key="delete"
                    class="!text-destructive"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                      <span>{{ $t('tenant.common.delete') }}</span>
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
              :title="$t('tenant.knowledgeBase.field.documentCount')"
            >
              <IconifyIcon icon="lucide:file-text" class="size-3.5" />
              <span class="tabular-nums">{{ item.document_count }}</span>
            </div>
            <div
              class="flex items-center gap-1"
              :title="$t('tenant.knowledgeBase.field.totalChunks')"
            >
              <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
              <span class="tabular-nums">{{ item.total_chunks }}</span>
            </div>
            <div
              class="flex items-center gap-1"
              :title="$t('tenant.knowledgeBase.field.totalSizeBytes')"
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
