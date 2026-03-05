<script lang="ts" setup>
/**
 * N17: 回收站页面 — 列表 + 还原 + 清空
 */
import { ref, onMounted } from 'vue';
import { listTrashApi, restoreNodeApi, clearTrashApi } from '../api/netdisk';
import type { FileNode } from '../api/netdisk';
import FileIcon from '../components/FileIcon.vue';

const nodes           = ref<FileNode[]>([]);
const loading         = ref(false);
const clearing        = ref(false);
const showClearModal  = ref(false);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}
function fmtSize(bytes: number): string {
  if (!bytes) return '—';
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

const columns = [
  { title: '', key: 'icon', width: 36 },
  { title: '', key: 'name', dataIndex: 'name' },
  { title: '', key: 'size', dataIndex: 'sizeBytes', width: 90 },
  { title: '', key: 'deletedAt', dataIndex: 'deletedAt', width: 160 },
  { title: '', key: 'actions', width: 90 },
];

async function load() {
  loading.value = true;
  try {
    const r = await listTrashApi();
    const data = r.data as unknown as { items?: FileNode[] } | FileNode[];
    nodes.value = Array.isArray(data) ? data : (data?.items ?? []);
  } finally {
    loading.value = false;
  }
}

async function restore(nodeId: number) {
  await restoreNodeApi(nodeId);
  await load();
}

async function confirmClear() {
  clearing.value = true;
  try {
    await clearTrashApi();
    nodes.value = [];
    showClearModal.value = false;
  } finally {
    clearing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col h-full bg-background">
    <!-- 工具栏 -->
    <div class="flex items-center gap-2 py-2 px-4 border-b border-border shrink-0">
      <span class="text-[15px] font-semibold">{{ $t('plugin.netdisk.trash.title') }}</span>
      <div class="ml-auto flex gap-2">
        <a-button size="small" @click="load">{{ $t('plugin.netdisk.action.refresh') }}</a-button>
        <a-button
          v-if="nodes.length > 0"
          size="small"
          danger
          :loading="clearing"
          @click="showClearModal = true"
        >
          {{ $t('plugin.netdisk.action.clearTrash') }}
        </a-button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto p-4">
      <a-spin :spinning="loading">
        <a-empty v-if="!loading && nodes.length === 0" :description="$t('plugin.netdisk.trash.empty')" />

        <a-table
          v-else
          :data-source="nodes"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <a-table-column key="icon" :width="36">
            <template #default="{ record }">
              <FileIcon :node="record" :size="16" />
            </template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.label.name')" data-index="name" key="name" />
          <a-table-column :title="$t('plugin.netdisk.label.size')" key="size" :width="90">
            <template #default="{ record }">
              {{ record.nodeType === 'file' ? fmtSize(record.sizeBytes) : '—' }}
            </template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.label.deletedAt')" key="deletedAt" :width="160">
            <template #default="{ record }">{{ fmtDate(record.deletedAt) }}</template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.admin.actionCol')" key="actions" :width="90">
            <template #default="{ record }">
              <a-button size="small" @click="restore(record.id)">{{ $t('plugin.netdisk.action.restore') }}</a-button>
            </template>
          </a-table-column>
        </a-table>
      </a-spin>
    </div>

    <!-- 清空回收站确认弹窗 -->
    <a-modal
      v-model:open="showClearModal"
      :title="$t('plugin.netdisk.action.clearTrash')"
      :confirm-loading="clearing"
      @ok="confirmClear"
      @cancel="showClearModal = false"
    >
      <p>{{ $t('plugin.netdisk.trash.clearConfirm') }}</p>
    </a-modal>
  </div>
</template>
