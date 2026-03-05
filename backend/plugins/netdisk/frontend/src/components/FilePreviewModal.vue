<script lang="ts" setup>
/**
 * N19: 文件预览器 Modal
 * 支持：图片(img) / PDF(iframe) / 视频(video) / 音频(audio) / 纯文本(pre)
 * 不支持的类型提示下载
 */
import type { FileNode } from '../api/netdisk';

interface Props {
  node:    FileNode | null;
  url:     string;      // 签名预览 URL
  visible: boolean;
}
interface Emits {
  (e: 'close'): void;
  (e: 'download'): void;
}

const props = defineProps<Props>();
const emit  = defineEmits<Emits>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function previewType(node: FileNode | null): 'image' | 'pdf' | 'video' | 'audio' | 'text' | 'none' {
  if (!node) return 'none';
  const mime = node.mimeType ?? '';
  if (mime.startsWith('image/'))     return 'image';
  if (mime === 'application/pdf')    return 'pdf';
  if (mime.startsWith('video/'))     return 'video';
  if (mime.startsWith('audio/'))     return 'audio';
  if (mime.startsWith('text/') || mime.includes('json') || mime.includes('xml')) return 'text';
  return 'none';
}
</script>

<template>
  <a-modal
    :open="visible && !!node"
    :title="node?.name ?? ''"
    :footer="null"
    :width="860"
    :body-style="{ padding: '0', minHeight: '480px', display: 'flex', flexDirection: 'column' }"
    centered
    @cancel="emit('close')"
  >
    <template #extra>
      <a-button size="small" @click="emit('download')">
        <template #icon>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </template>
        {{ $t('plugin.netdisk.action.download') }}
      </a-button>
    </template>

    <div v-if="node" class="flex-1 flex items-center justify-center p-4 min-h-[480px] bg-muted rounded-b-lg">
      <!-- 图片 -->
      <img
        v-if="previewType(node) === 'image'"
        :src="url" :alt="node.name"
        class="max-w-full max-h-[520px] object-contain rounded shadow-md"
      />

      <!-- PDF -->
      <iframe
        v-else-if="previewType(node) === 'pdf'"
        :src="url" frameborder="0"
        class="w-full h-[520px] border-none rounded"
      />

      <!-- 视频 -->
      <video
        v-else-if="previewType(node) === 'video'"
        :src="url" controls
        class="max-w-full max-h-[520px] rounded"
      />

      <!-- 音频 -->
      <div v-else-if="previewType(node) === 'audio'" class="w-full text-center py-12 px-6">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="1.5" class="mb-6"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        <audio :src="url" controls class="w-full" />
      </div>

      <!-- 不支持预览 -->
      <div v-else class="text-center py-12 px-6">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.2" class="mb-4"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
        <p class="text-base font-medium mb-2 text-foreground">{{ node.name }}</p>
        <p class="text-muted-foreground text-[13px] mb-6">
          {{ $t('plugin.netdisk.preview.noPreview') }}
        </p>
        <a-button type="primary" @click="emit('download')">
          <template #icon>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </template>
          {{ $t('plugin.netdisk.action.download') }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>
