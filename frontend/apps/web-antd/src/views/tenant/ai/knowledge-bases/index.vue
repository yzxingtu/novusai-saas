<script lang="ts" setup>
/**
 * 企业端知识库管理列表页面 — useCrudList + 卡片网格
 */
import type { KnowledgeBaseItem } from '#/api/tenant/knowledge-bases';

import { computed, ref } from 'vue';

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
import {
  buildPageAIFormExtraData,
  createKeywordSearchPageOperation,
  createOpenRecordPageOperation,
  createPrefilledCreatePageOperation,
  useCrudList,
} from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getKBStatusColor, getKBStatusText, useFormSchema } from './data';
import KnowledgeBaseDetail from './modules/KnowledgeBaseDetail.vue';
import KnowledgeBaseForm from './modules/KnowledgeBaseForm.vue';

defineOptions({ name: 'TenantKnowledgeBaseList' });

const AI_PAGE_KEY = 'tenant.ai.knowledge-bases';

/** Editable/deletable = owned by current tenant (tenant_id is owner_tenant_id synonym) */
function isTenantManageableKb(row: KnowledgeBaseItem): boolean {
  return row.tenant_id !== null;
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
    edit: (row) => kbFormRef.value?.openEdit(
      row,
      buildPageAIFormExtraData({ pageKey: AI_PAGE_KEY }),
    ),
  },
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: useFormSchema,
    entityName: $t('tenant.knowledgeBase.name'),
    entityDescription: $t('tenant.knowledgeBase.entityDescription'),
    openRecycleBin: () => recycleBinRef.value?.open(),
    extra: [
      createPrefilledCreatePageOperation({
        description:
          'Open the create knowledge base form and optionally pre-fill fields / 打开新建知识库表单，可选预填字段',
        params: {
          chunk_overlap: {
            type: 'number',
            description: 'Chunk overlap / 分块重叠',
          },
          chunk_size: {
            type: 'number',
            description: 'Chunk size / 分块大小',
          },
          chunk_strategy: {
            type: 'string',
            description: 'Chunk strategy / 分块策略',
          },
          description: {
            type: 'string',
            description: 'Knowledge base description / 知识库简介',
          },
          embedding_model_id: {
            type: 'number',
            description: 'Embedding model ID / 向量模型 ID',
          },
          extract_images: {
            type: 'boolean',
            description: 'Whether to extract images / 是否抽取图片',
          },
          name: {
            type: 'string',
            description: 'Knowledge base name / 知识库名称',
          },
        },
        normalizeParams: (params) => ({
          ...(Number.isFinite(Number(params.chunk_overlap))
            ? { chunk_overlap: Number(params.chunk_overlap) }
            : {}),
          ...(Number.isFinite(Number(params.chunk_size))
            ? { chunk_size: Number(params.chunk_size) }
            : {}),
          ...(typeof params.chunk_strategy === 'string' && params.chunk_strategy
            ? { chunk_strategy: params.chunk_strategy }
            : {}),
          ...(typeof params.description === 'string' && params.description.trim()
            ? { description: params.description.trim() }
            : {}),
          ...(Number.isFinite(Number(params.embedding_model_id))
            ? { embedding_model_id: Number(params.embedding_model_id) }
            : {}),
          ...(typeof params.extract_images === 'boolean'
            ? { extract_images: params.extract_images }
            : {}),
          ...(typeof params.name === 'string' && params.name.trim()
            ? { name: params.name.trim() }
            : {}),
        }),
        openCreate: async (defaults) => {
          openKnowledgeBaseCreate(defaults);
        },
      }),
      createOpenRecordPageOperation({
        name: 'open_knowledge_base_detail',
        label: $t('shared.pageOperation.viewDetail'),
        description:
          'Open the knowledge base detail drawer by knowledge base ID / 按知识库 ID 打开详情抽屉',
        readonly: true,
        params: {
          id: {
            type: 'number',
            description: 'Knowledge base ID / 知识库 ID',
            required: true,
          },
        },
        normalizeParams: (params) => ({
          id: Number(params.id ?? 0),
        }),
        resolveRecord: (params) => findKnowledgeBaseById(params.id),
        resolveRecordId: (params) => params.id,
        open: async (record) => {
          openKnowledgeBaseDetail(record);
        },
      }),
      createKeywordSearchPageOperation({
        description: 'Search knowledge bases by keyword / 按关键词搜索知识库',
        setKeyword: (keyword) => {
          searchKeyword.value = keyword;
        },
        action: async () => {
          doSearch();
        },
      }),
    ],
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

// ========== KnowledgeBaseForm (ref 模式) / form by ref ==========
const kbFormRef = ref<InstanceType<typeof KnowledgeBaseForm>>();

function openKnowledgeBaseCreate(defaults: Record<string, unknown> = {}) {
  kbFormRef.value?.openNew(
    buildPageAIFormExtraData({
      pageKey: AI_PAGE_KEY,
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
    .setData({ id: row.id, name: row.name, scope: row.scope })
    .open();
}

function findKnowledgeBaseById(id: number): KnowledgeBaseItem | null {
  return list.value.find((item) => item.id === id) ?? null;
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
          @click="onCreateKB"
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
                  <MenuItem v-if="isTenantManageableKb(item)" key="edit">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                      <span>{{ $t('tenant.knowledgeBase.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="isTenantManageableKb(item)"
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
