<script lang="ts" setup>
/**
 * 知识库详情抽屉
 *
 * Tab 1: 文档管理（列表+上传+删除+重试+进度）
 * Tab 2: 检索测试
 */
import type {
  KnowledgeDocumentItem,
  SearchResultItem,
} from '#/api/tenant/knowledge-bases';

import { computed, onUnmounted, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  Input,
  message,
  Modal,
  Progress,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import {
  deleteDocumentApi,
  getDocumentListApi,
  getDocumentProgressApi,
  reindexKnowledgeBaseApi,
  retryDocumentApi,
  searchKnowledgeBaseApi,
  uploadDocumentApi,
} from '#/api/tenant/knowledge-bases';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

import { getDocStatusColor, getDocStatusText } from '../data';

const emit = defineEmits<{ success: [] }>();

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange(isOpen) {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number; name: string }>();
      if (data) {
        kbId.value = data.id;
        kbName.value = data.name;
        loadDocuments();
      }
    } else {
      stopPolling();
    }
  },
});

// ========== 基础状态 ==========
const kbId = ref(0);
const kbName = ref('');
const activeTab = ref('documents');
const loading = ref(false);

// ========== 文档管理 ==========
const documents = ref<KnowledgeDocumentItem[]>([]);
const docTotal = ref(0);
const docPage = ref(1);
const uploading = ref(false);

async function loadDocuments() {
  loading.value = true;
  try {
    const res = await getDocumentListApi(kbId.value, {
      'page[number]': docPage.value,
      'page[size]': 20,
      sort: '-created_at',
    });
    documents.value = res.items;
    docTotal.value = res.total;
    startPollingForProcessing();
  } catch {
    // handled by global interceptor
  } finally {
    loading.value = false;
  }
}

// 文档列定义
const docColumns = computed(() => [
  {
    title: $t('tenant.knowledgeBase.document.field.fileName'),
    dataIndex: 'file_name',
    key: 'file_name',
    ellipsis: true,
    width: 200,
  },
  {
    title: $t('tenant.knowledgeBase.document.field.fileType'),
    dataIndex: 'file_type',
    key: 'file_type',
    width: 80,
    align: 'center' as const,
  },
  {
    title: $t('tenant.knowledgeBase.document.field.fileSize'),
    dataIndex: 'file_size',
    key: 'file_size',
    width: 100,
    align: 'center' as const,
  },
  {
    title: $t('tenant.knowledgeBase.document.field.chunkCount'),
    dataIndex: 'chunk_count',
    key: 'chunk_count',
    width: 80,
    align: 'center' as const,
  },
  {
    title: $t('tenant.knowledgeBase.document.field.status'),
    dataIndex: 'status',
    key: 'status',
    width: 120,
    align: 'center' as const,
  },
  {
    title: $t('tenant.knowledgeBase.document.field.createdAt'),
    dataIndex: 'created_at',
    key: 'created_at',
    width: 170,
  },
  {
    title: $t('tenant.common.operation'),
    key: 'action',
    width: 140,
    align: 'center' as const,
    fixed: 'right' as const,
  },
]);

// 上传文件
async function handleUpload(file: File) {
  uploading.value = true;
  try {
    await uploadDocumentApi(kbId.value, file);
    message.success($t('common.operationSuccess'));
    await loadDocuments();
    emit('success');
  } catch {
    // handled by global interceptor
  } finally {
    uploading.value = false;
  }
  return false; // prevent default upload
}

// 删除文档
function handleDeleteDoc(doc: KnowledgeDocumentItem) {
  Modal.confirm({
    title: $t('tenant.knowledgeBase.document.delete'),
    content: doc.file_name,
    async onOk() {
      await deleteDocumentApi(kbId.value, doc.id);
      message.success($t('common.operationSuccess'));
      await loadDocuments();
      emit('success');
    },
  });
}

// 重试文档
async function handleRetryDoc(doc: KnowledgeDocumentItem) {
  try {
    await retryDocumentApi(kbId.value, doc.id);
    message.success($t('common.operationSuccess'));
    await loadDocuments();
  } catch {
    // handled
  }
}

// 重新向量化
function handleReindex() {
  Modal.confirm({
    title: $t('tenant.knowledgeBase.reindex.title'),
    content: $t('tenant.knowledgeBase.reindex.confirm'),
    async onOk() {
      const res = await reindexKnowledgeBaseApi(kbId.value);
      message.success(
        `${$t('tenant.knowledgeBase.reindex.started')} (${res.document_count})`,
      );
      await loadDocuments();
      emit('success');
    },
  });
}

// ========== 轮询处理中文档的进度 ==========
let pollingTimer: ReturnType<typeof setInterval> | null = null;
const docProgress = ref<Record<number, number>>({});

function startPollingForProcessing() {
  stopPolling();
  const processingDocs = documents.value.filter(
    (d) => !['completed', 'error'].includes(d.status),
  );
  if (processingDocs.length === 0) return;

  pollingTimer = setInterval(async () => {
    let hasProcessing = false;
    for (const doc of processingDocs) {
      try {
        const prog = await getDocumentProgressApi(kbId.value, doc.id);
        docProgress.value[doc.id] = prog.progress;
        if (!['completed', 'error'].includes(prog.stage)) {
          hasProcessing = true;
        }
      } catch {
        // ignore
      }
    }
    if (!hasProcessing) {
      stopPolling();
      await loadDocuments();
      emit('success');
    }
  }, 3000);
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

onUnmounted(stopPolling);

// ========== 检索测试 ==========
const searchQuery = ref('');
const searchLoading = ref(false);
const searchResults = ref<SearchResultItem[]>([]);

async function handleSearch() {
  if (!searchQuery.value.trim()) return;
  searchLoading.value = true;
  try {
    searchResults.value = await searchKnowledgeBaseApi(kbId.value, {
      query: searchQuery.value.trim(),
    });
  } catch {
    // handled
  } finally {
    searchLoading.value = false;
  }
}

watch(activeTab, (tab) => {
  if (tab === 'documents') {
    loadDocuments();
  }
});
</script>

<template>
  <Drawer
    :title="`${$t('tenant.knowledgeBase.detail')} - ${kbName}`"
    class="w-[800px]"
  >
    <Tabs v-model:activeKey="activeTab">
      <!-- ========== 文档管理 Tab ========== -->
      <Tabs.TabPane key="documents" :tab="$t('tenant.knowledgeBase.document.title')">
        <div class="mb-4 flex items-center justify-between">
          <Space>
            <Upload
              :before-upload="handleUpload"
              :show-upload-list="false"
              :multiple="true"
              accept=".pdf,.docx,.txt,.md,.csv,.html,.htm"
            >
              <Button type="primary" :loading="uploading">
                <IconifyIcon icon="lucide:upload" class="mr-1 size-4" />
                {{ $t('tenant.knowledgeBase.document.upload') }}
              </Button>
            </Upload>
            <Button @click="handleReindex">
              <IconifyIcon icon="lucide:refresh-cw" class="mr-1 size-4" />
              {{ $t('tenant.knowledgeBase.reindex.title') }}
            </Button>
          </Space>
          <span class="text-muted-foreground">
            {{ $t('tenant.knowledgeBase.document.uploadHint') }}
          </span>
        </div>

        <Table
          :columns="docColumns"
          :data-source="documents"
          :loading="loading"
          :pagination="{
            current: docPage,
            total: docTotal,
            pageSize: 20,
            onChange: (p: number) => { docPage = p; loadDocuments(); },
          }"
          :scroll="{ x: 800 }"
          row-key="id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <!-- 文件大小 -->
            <template v-if="column.key === 'file_size'">
              {{ formatFileSize(record.file_size) }}
            </template>

            <!-- 状态（含进度条） -->
            <template v-else-if="column.key === 'status'">
              <div class="flex flex-col items-center gap-1">
                <Tag :color="getDocStatusColor(record.status)">
                  {{ getDocStatusText(record.status) }}
                </Tag>
                <Progress
                  v-if="!['completed', 'error'].includes(record.status)"
                  :percent="docProgress[record.id] ?? 0"
                  :show-info="false"
                  size="small"
                  class="w-16"
                />
                <Tooltip
                  v-if="record.error_message"
                  :title="record.error_message"
                >
                  <span class="cursor-help text-xs text-destructive">
                    {{ record.error_message?.slice(0, 30) }}...
                  </span>
                </Tooltip>
              </div>
            </template>

            <!-- 创建时间 -->
            <template v-else-if="column.key === 'created_at'">
              <span class="text-muted-foreground">
                {{ formatDate(record.created_at) }}
              </span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <Space>
                <Button
                  v-if="record.status === 'error'"
                  type="link"
                  size="small"
                  @click="handleRetryDoc(record as KnowledgeDocumentItem)"
                >
                  {{ $t('tenant.knowledgeBase.document.retry') }}
                </Button>
                <Button
                  type="link"
                  danger
                  size="small"
                  @click="handleDeleteDoc(record as KnowledgeDocumentItem)"
                >
                  {{ $t('tenant.knowledgeBase.document.delete') }}
                </Button>
              </Space>
            </template>
          </template>
        </Table>
      </Tabs.TabPane>

      <!-- ========== 检索测试 Tab ========== -->
      <Tabs.TabPane key="search" :tab="$t('tenant.knowledgeBase.searchTest.title')">
        <div class="mb-4 flex gap-2">
          <Input
            v-model:value="searchQuery"
            :placeholder="$t('tenant.knowledgeBase.searchTest.placeholder')"
            allow-clear
            @press-enter="handleSearch"
          />
          <Button
            type="primary"
            :loading="searchLoading"
            @click="handleSearch"
          >
            {{ $t('tenant.knowledgeBase.searchTest.search') }}
          </Button>
        </div>

        <Spin :spinning="searchLoading">
          <Empty
            v-if="searchResults.length === 0 && !searchLoading"
            :description="$t('tenant.knowledgeBase.searchTest.noResults')"
          />

          <div v-else class="flex flex-col gap-3">
            <Card
              v-for="(result, idx) in searchResults"
              :key="result.chunk_id"
              size="small"
              class="border-l-4"
              :style="{ borderLeftColor: `hsl(${210 - idx * 15}, 70%, 55%)` }"
            >
              <div class="mb-2 flex items-center justify-between">
                <Tag color="blue">
                  #{{ idx + 1 }}
                </Tag>
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {{ $t('tenant.knowledgeBase.searchTest.score') }}:
                    {{ (result.score * 100).toFixed(1) }}%
                  </span>
                  <span>|</span>
                  <span>
                    {{ $t('tenant.knowledgeBase.searchTest.source') }}:
                    {{ result.document_name }}
                  </span>
                </div>
              </div>
              <div class="whitespace-pre-wrap text-sm leading-relaxed">
                {{ result.content }}
              </div>
            </Card>
          </div>
        </Spin>
      </Tabs.TabPane>
    </Tabs>
  </Drawer>
</template>
