<script lang="ts" setup>
/**
 * N23: ShareModal — 分享设置对话框
 * 生成链接 / 设置密码 / 有效期 / 权限 / 复制链接（含密码）
 */
import { ref, computed } from 'vue';
import type { FileNode } from '../api/netdisk';
import { createShareApi } from '../api/netdisk';

interface Props {
  visible: boolean;
  node:    FileNode | null;
}
interface Emits {
  (e: 'close'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const permission  = ref<'read' | 'download'>('download');
const password    = ref('');
const expiresIdx  = ref(0);  // 0=永久, 1=1天, 2=7天, 3=30天
const shareToken  = ref('');
const creating    = ref(false);
const copied      = ref(false);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

const expiresDays = computed(() => {
  return [null, 1, 7, 30][expiresIdx.value];
});

const shareLink = computed(() => {
  if (!shareToken.value) return '';
  return `${location.origin}/public/netdisk/shares/${shareToken.value}`;
});

const shareLinkWithPwd = computed(() => {
  if (!shareLink.value) return '';
  if (!password.value) return shareLink.value;
  return `${shareLink.value}\n提取码：${password.value}`;
});

async function create() {
  if (!props.node) return;
  creating.value = true;
  try {
    const r = await createShareApi(props.node.id, {
      permission: permission.value,
      password:   password.value || undefined,
      expires_days: expiresDays.value ?? undefined,
    });
    shareToken.value = r.data.shareToken;
  } catch { /* handle error */ }
  finally { creating.value = false; }
}

async function copyLink(withPwd = false) {
  const text = withPwd ? shareLinkWithPwd.value : shareLink.value;
  await navigator.clipboard?.writeText(text);
  copied.value = true;
  setTimeout(() => { copied.value = false; }, 2000);
}

function close() {
  shareToken.value = '';
  permission.value = 'download';
  password.value   = '';
  expiresIdx.value = 0;
  emit('close');
}
</script>

<template>
  <a-modal
    :open="visible && !!node"
    :title="null"
    :footer="null"
    :width="460"
    @cancel="close"
  >
    <template #title>
      <div class="flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        {{ $t('plugin.netdisk.share.title') }}
      </div>
    </template>

    <div v-if="node" class="py-1">
      <p class="mb-4 font-medium text-sm">{{ node.name }}</p>

      <!-- 权限选择 -->
      <div class="flex items-center gap-3 mb-3.5">
        <span class="text-[13px] text-muted-foreground w-14 shrink-0">{{ $t('plugin.netdisk.share.permission') }}</span>
        <a-radio-group v-model:value="permission" size="small">
          <a-radio value="read">{{ $t('plugin.netdisk.share.permRead') }}</a-radio>
          <a-radio value="download">{{ $t('plugin.netdisk.share.permDownload') }}</a-radio>
        </a-radio-group>
      </div>

      <!-- 密码 -->
      <div class="flex items-center gap-3 mb-3.5">
        <span class="text-[13px] text-muted-foreground w-14 shrink-0">{{ $t('plugin.netdisk.share.password') }}</span>
        <a-input
          v-model:value="password"
          :placeholder="$t('plugin.netdisk.share.noPassword')"
          :maxlength="8"
          allow-clear
          class="flex-1"
        />
      </div>

      <!-- 有效期 -->
      <div class="flex items-center gap-3 mb-5">
        <span class="text-[13px] text-muted-foreground w-14 shrink-0">{{ $t('plugin.netdisk.share.expires') }}</span>
        <a-select v-model:value="expiresIdx" class="flex-1">
          <a-select-option :value="0">{{ $t('plugin.netdisk.share.expiresNever') }}</a-select-option>
          <a-select-option :value="1">{{ $t('plugin.netdisk.share.expires1d') }}</a-select-option>
          <a-select-option :value="2">{{ $t('plugin.netdisk.share.expires7d') }}</a-select-option>
          <a-select-option :value="3">{{ $t('plugin.netdisk.share.expires30d') }}</a-select-option>
        </a-select>
      </div>

      <!-- 生成按钮 -->
      <a-button
        v-if="!shareToken"
        type="primary"
        block
        :loading="creating"
        @click="create"
      >
        {{ $t('plugin.netdisk.share.generate') }}
      </a-button>

      <!-- 分享链接结果 -->
      <div v-if="shareToken">
        <div class="px-3 py-2.5 bg-muted rounded-md text-xs break-all mb-2.5 font-mono">
          {{ shareLink }}
          <span v-if="password" class="text-muted-foreground ml-2 font-sans">{{ $t('plugin.netdisk.share.accessCodeLabel') }}{{ password }}</span>
        </div>
        <div class="flex gap-2">
          <a-button type="primary" class="flex-1" @click="copyLink(false)">
            {{ copied ? $t('plugin.netdisk.share.linkCopied') : $t('plugin.netdisk.share.copyLink') }}
          </a-button>
          <a-button v-if="password" class="flex-1" @click="copyLink(true)">
            {{ $t('plugin.netdisk.share.copyWithCode') }}
          </a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>
