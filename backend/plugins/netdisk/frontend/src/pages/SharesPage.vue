<script lang="ts" setup>
/**
 * N18: 我的分享列表页面
 * 显示当前用户创建的所有分享链接，支持取消分享
 */
import { ref, onMounted } from 'vue';
import type { Share } from '../api/netdisk';
import { listMySharesApi, cancelShareApi } from '../api/netdisk';

const shares         = ref<Share[]>([]);
const loading        = ref(false);
const cancelTarget   = ref<string | null>(null);
const cancelLoading  = ref(false);
const showCancelModal = ref(false);

const getShared = () =>
  (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string; message?: { success: (m: string) => void } } }).NovusPluginShared;

const $t = (key: string) => getShared()?.$t?.(key) ?? key.split('.').pop() ?? key;

async function load() {
  loading.value = true;
  try {
    const r = await listMySharesApi();
    shares.value = r.data?.items ?? [];
  } catch { shares.value = []; }
  finally { loading.value = false; }
}

function promptCancel(token: string) {
  cancelTarget.value = token;
  showCancelModal.value = true;
}

async function confirmCancel() {
  if (!cancelTarget.value) return;
  cancelLoading.value = true;
  try {
    await cancelShareApi(cancelTarget.value);
    showCancelModal.value = false;
    cancelTarget.value = null;
    await load();
  } finally {
    cancelLoading.value = false;
  }
}

function copyLink(token: string) {
  const url = `${location.origin}/public/netdisk/shares/${token}`;
  navigator.clipboard?.writeText(url).then(() => {
    getShared()?.message?.success($t('plugin.netdisk.share.linkCopied'));
  });
}

function fmtDate(iso: string | null): string {
  if (!iso) return $t('plugin.netdisk.share.expiresNever');
  return new Date(iso).toLocaleDateString();
}

onMounted(load);
</script>

<template>
  <div class="flex flex-col h-full bg-background">
    <!-- 工具栏 -->
    <div class="shrink-0 flex items-center gap-2 py-2 px-4 border-b border-border">
      <span class="text-[15px] font-semibold">{{ $t('plugin.netdisk.nav.shares') }}</span>
      <div class="ml-auto">
        <a-button @click="load" :loading="loading" size="small">{{ $t('plugin.netdisk.action.refresh') }}</a-button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto p-4">
      <a-spin :spinning="loading">
        <a-empty v-if="!loading && shares.length === 0" :description="$t('plugin.netdisk.shares.empty')" />

        <a-table
          v-else
          :data-source="shares"
          :pagination="false"
          row-key="id"
          size="small"
        >
          <a-table-column :title="$t('plugin.netdisk.label.file')" data-index="nodeName" key="file">
            <template #default="{ record }">
              <a-space size="small">
                <svg v-if="record.nodeType === 'folder'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                <span>{{ record.nodeName ?? `#${record.nodeId}` }}</span>
              </a-space>
            </template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.admin.permCol')" data-index="permission" key="permission" :width="100" />
          <a-table-column :title="$t('plugin.netdisk.share.password')" key="hasPassword" :width="80">
            <template #default="{ record }">
              <a-tag v-if="record.hasPassword" color="orange">{{ $t('plugin.netdisk.share.hasPassword') }}</a-tag>
              <span v-else>—</span>
            </template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.share.expires')" key="expiresAt" :width="130">
            <template #default="{ record }">{{ fmtDate(record.expiresAt) }}</template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.admin.accessCol')" data-index="accessCount" key="accessCount" :width="70" />
          <a-table-column :title="$t('plugin.netdisk.label.status')" key="isActive" :width="80">
            <template #default="{ record }">
              <a-tag :color="record.isActive ? 'success' : 'error'">
                {{ record.isActive ? $t('plugin.netdisk.admin.statusActive') : $t('plugin.netdisk.admin.statusRevoked') }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column :title="$t('plugin.netdisk.admin.actionCol')" key="actions" :width="160">
            <template #default="{ record }">
              <a-space size="small">
                <a-button size="small" @click="copyLink(record.shareToken)">{{ $t('plugin.netdisk.share.copyLink') }}</a-button>
                <a-button v-if="record.isActive" size="small" danger @click="promptCancel(record.shareToken)">{{ $t('plugin.netdisk.share.cancel') }}</a-button>
              </a-space>
            </template>
          </a-table-column>
        </a-table>
      </a-spin>
    </div>

    <!-- 取消分享确认弹窗 -->
    <a-modal
      v-model:open="showCancelModal"
      :title="$t('plugin.netdisk.share.cancel')"
      :confirm-loading="cancelLoading"
      @ok="confirmCancel"
      @cancel="showCancelModal = false"
    >
      <p>{{ $t('plugin.netdisk.share.cancelConfirm') }}</p>
    </a-modal>
  </div>
</template>
