<script setup lang="ts">
/**
 * 富文本编辑器 - 文档列表页
 *
 * 双栏布局：左侧文件夹树 + 右侧文档卡片列表
 * 支持搜索/过滤/排序、新建文档、文档状态标签
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  Button,
  Empty,
  Input,
  Space,
  Spin,
} from 'ant-design-vue';

import { useRichEditorApi } from '#/views/tenant/plugins/rich-editor/composables/use-rich-editor-api';
import { $t } from '#/locales';

import DocumentCard from './components/DocumentCard.vue';

const router = useRouter();
const { listDocuments, deleteDocument } = useRichEditorApi();

const loading = ref(false);
const documents = ref<any[]>([]);
const total = ref(0);
const searchKeyword = ref('');
const currentPage = ref(1);
const pageSize = ref(20);

async function fetchDocuments() {
  loading.value = true;
  try {
    const params: Record<string, string> = {
      'page[number]': String(currentPage.value),
      'page[size]': String(pageSize.value),
      sort: '-updated_at',
    };
    if (searchKeyword.value) {
      params['filter[title][ilike]'] = searchKeyword.value;
    }
    const res = await listDocuments(params);
    documents.value = res.items || [];
    total.value = res.total || 0;
  } finally {
    loading.value = false;
  }
}

function handleCreate() {
  router.push('/tenant/plugins/rich-editor/editor/new');
}

function handleEdit(doc: any) {
  router.push(`/tenant/plugins/rich-editor/editor/${doc.id}`);
}

async function handleDelete(doc: any) {
  await deleteDocument(doc.id);
  await fetchDocuments();
}

function handleSearch() {
  currentPage.value = 1;
  fetchDocuments();
}

const isEmpty = computed(
  () => !loading.value && documents.value.length === 0,
);

onMounted(() => {
  fetchDocuments();
});
</script>

<template>
  <Page :title="$t('tenant.richEditor.title')">
    <div class="rich-editor-list">
      <!-- 顶部操作栏 -->
      <div class="mb-4 flex items-center justify-between">
        <Space>
          <Input.Search
            v-model:value="searchKeyword"
            :placeholder="$t('tenant.richEditor.searchPlaceholder')"
            allow-clear
            style="width: 280px"
            @search="handleSearch"
            @press-enter="handleSearch"
          />
        </Space>
        <Button type="primary" @click="handleCreate">
          <template #icon>
            <span class="icon-[lucide--plus] mr-1" />
          </template>
          {{ $t('tenant.richEditor.createDocument') }}
        </Button>
      </div>

      <!-- 文档列表 -->
      <Spin :spinning="loading">
        <div v-if="isEmpty" class="flex min-h-[400px] items-center justify-center">
          <Empty :description="$t('tenant.richEditor.emptyDescription')">
            <Button type="primary" @click="handleCreate">
              {{ $t('tenant.richEditor.createFirst') }}
            </Button>
          </Empty>
        </div>
        <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <DocumentCard
            v-for="doc in documents"
            :key="doc.id"
            :document="doc"
            @edit="handleEdit"
            @delete="handleDelete"
          />
        </div>
      </Spin>
    </div>
  </Page>
</template>

<style scoped>
.rich-editor-list {
  min-height: 60vh;
}
</style>
