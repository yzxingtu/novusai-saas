<script lang="ts" setup>
/**
 * N18: 公开分享访问页（无需登录）
 * 路由参数：?token=xxx
 */
import { ref, onMounted } from 'vue';

interface ShareInfo {
  shareToken:  string;
  permission:  string;
  hasPassword: boolean;
  expiresAt:   string | null;
  accessCount: number;
}
interface NodeInfo { id: number; name: string; nodeType: string; size: number; mimeType: string | null; }

const shareInfo  = ref<ShareInfo | null>(null);
const nodeInfo   = ref<NodeInfo | null>(null);
const password   = ref('');
const verified   = ref(false);
const error      = ref('');
const loading    = ref(false);
const downloading = ref(false);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function getToken(): string {
  return new URLSearchParams(location.search).get('token') ?? '';
}

async function fetchShare() {
  const token = getToken();
  if (!token) { error.value = 'Missing share token'; return; }
  loading.value = true;
  try {
    const r = await fetch(`/public/netdisk/shares/${token}`);
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json() as { data: { share: ShareInfo; node: NodeInfo } };
    shareInfo.value = data.data.share;
    nodeInfo.value  = data.data.node;
    if (!data.data.share.hasPassword) verified.value = true;
  } catch (e) {
    error.value = e instanceof Error ? e.message : $t('plugin.netdisk.error.share_not_found');
  } finally {
    loading.value = false;
  }
}

async function verify() {
  const token = getToken();
  loading.value = true;
  try {
    const r = await fetch(`/public/netdisk/shares/${token}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password.value }),
    });
    const data = await r.json() as { data: { verified: boolean } };
    if (data.data.verified) {
      verified.value = true;
      error.value    = '';
    } else {
      error.value = $t('plugin.netdisk.share.wrongPassword');
    }
  } catch {
    error.value = $t('plugin.netdisk.share.verifyFailed');
  } finally {
    loading.value = false;
  }
}

async function download() {
  if (!nodeInfo.value) return;
  const token = getToken();
  downloading.value = true;
  try {
    const r = await fetch(`/public/netdisk/shares/${token}/download/${nodeInfo.value.id}`);
    const data = await r.json() as { data: { url: string } };
    window.open(data.data.url, '_blank');
  } catch {
    console.error('download failed');
  } finally {
    downloading.value = false;
  }
}

function fmtSize(bytes: number): string {
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

onMounted(fetchShare);
</script>

<template>
  <div class="min-h-screen bg-accent flex items-center justify-center p-6">
    <div class="max-w-[480px] w-full bg-background rounded-xl shadow-lg p-8">

      <!-- 加载中 -->
      <div v-if="loading" class="text-center p-8">
        <a-spin size="large" />
      </div>

      <!-- 错误 -->
      <div v-else-if="error && !shareInfo" class="text-center p-8">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.5" class="mb-4"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        <p class="text-red-500 text-sm">{{ error }}</p>
      </div>

      <!-- 密码验证 -->
      <div v-else-if="shareInfo && !verified" class="text-center">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5" class="mb-4"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <h2 class="text-lg font-semibold mb-2 text-foreground">{{ $t('plugin.netdisk.share.passwordProtected') }}</h2>
        <p class="text-slate-500 mb-6 text-sm">{{ nodeInfo?.name }}</p>
        <div class="flex gap-2 mb-3 text-left">
          <a-input-password
            v-model:value="password"
            :placeholder="$t('plugin.netdisk.share.enterPassword')"
            class="flex-1"
            @pressEnter="verify"
          />
          <a-button type="primary" :loading="loading" @click="verify">
            {{ $t('plugin.netdisk.share.verifyBtn') }}
          </a-button>
        </div>
        <p v-if="error" class="text-red-500 text-[13px] text-left">{{ error }}</p>
      </div>

      <!-- 文件信息 + 下载 -->
      <div v-else-if="shareInfo && nodeInfo && verified">
        <div class="text-center mb-7">
          <div class="flex justify-center mb-3.5">
            <svg v-if="nodeInfo.nodeType === 'folder'" width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="1.2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <svg v-else width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="1.2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
          </div>
          <h2 class="text-xl font-semibold mb-1 text-foreground">{{ nodeInfo.name }}</h2>
          <p v-if="nodeInfo.nodeType === 'file'" class="text-slate-500 text-[13px] mb-1">
            {{ fmtSize(nodeInfo.size) }}
          </p>
          <p v-if="shareInfo.expiresAt" class="text-amber-500 text-xs mt-1">
            {{ $t('plugin.netdisk.share.expires') }}: {{ new Date(shareInfo.expiresAt).toLocaleDateString() }}
          </p>
        </div>

        <div class="flex flex-col gap-3">
          <a-button
            v-if="shareInfo.permission === 'download'"
            type="primary"
            block
            size="large"
            :loading="downloading"
            @click="download"
          >
            <template #icon>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </template>
            {{ $t('plugin.netdisk.action.download') }}
          </a-button>
          <div
            v-else
            class="text-center p-3 bg-muted rounded-md text-muted-foreground text-[13px]"
          >
            {{ $t('plugin.netdisk.error.no_download_permission') }}
          </div>
        </div>

        <div class="mt-4 text-center text-xs text-muted-foreground">
          {{ $t('plugin.netdisk.share.accessedCount').replace('{count}', String(shareInfo.accessCount)) }}
        </div>
      </div>
    </div>
  </div>
</template>
