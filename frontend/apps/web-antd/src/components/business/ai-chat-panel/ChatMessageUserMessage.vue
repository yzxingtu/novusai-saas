<script lang="ts" setup>
import type { ChatAttachment, ChatMessage } from './types';

import { IconifyIcon } from '@vben/icons';
import { Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatTimeOnly } from '#/utils/common';
import { getFileIcon } from '#/utils/file';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    index: number;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

const emit = defineEmits<{
  copy: [content: string];
  edit: [index: number];
  openUrl: [url: string];
}>();

/** 用户消息图片：blob 预览失效时改用 url；仍失败则隐藏避免破图 / Image load error fallback */
function onUserAttachmentImageError(event: Event, att: ChatAttachment) {
  const el = event.target as HTMLImageElement;
  if (!el) return;
  if (att.preview && el.src.startsWith('blob:') && att.url) {
    el.src = att.url;
    return;
  }
  el.classList.add('hidden');
}
</script>

<template>
  <div class="flex justify-end" :class="compact ? 'gap-2' : 'gap-3'">
    <div class="group" :class="compact ? 'max-w-[85%]' : 'max-w-[75%]'">
      <!-- Attachments -->
      <div
        v-if="msg.attachments?.length"
        class="flex flex-wrap justify-end"
        :class="compact ? 'mb-1 gap-1' : 'mb-1.5 gap-1.5'"
      >
        <template v-for="(att, ati) in msg.attachments" :key="`${ati}-${att.url}`">
          <img
            v-if="att.type === 'image'"
            :src="att.preview || att.url"
            :alt="att.name || ''"
            class="cursor-pointer rounded-lg object-contain"
            :class="
              compact
                ? 'max-h-32 max-w-40'
                : 'max-h-48 max-w-60 border border-white/20'
            "
            @error="onUserAttachmentImageError($event, att)"
            @click="emit('openUrl', att.url)"
          />
          <audio
            v-else-if="att.type === 'audio'"
            controls
            :src="att.url"
            class="max-w-full rounded-lg"
            :class="compact ? 'max-w-48' : 'max-w-64'"
          ></audio>
          <video
            v-else-if="att.type === 'video'"
            controls
            :src="att.url"
            class="max-w-full rounded-lg object-contain"
            :class="
              compact
                ? 'max-h-32 max-w-40'
                : 'max-h-48 max-w-60 border border-white/20'
            "
          ></video>
          <a
            v-else
            :href="att.url"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center rounded-lg bg-primary-foreground/10 text-primary-foreground hover:bg-primary-foreground/20"
            :class="compact ? 'gap-1 px-1.5 py-0.5 text-[11px]' : 'gap-1.5 px-2 py-1 text-xs'"
          >
            <IconifyIcon
              :icon="getFileIcon(att.name || '', att.mime_type)"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            <span :class="compact ? 'max-w-[80px]' : 'max-w-[120px]'" class="truncate">
              {{ att.name || $t('common.globalAiChat.file') }}
            </span>
          </a>
        </template>
      </div>
      <div
        v-if="msg.content"
        class="whitespace-pre-wrap rounded-2xl rounded-br-md bg-gradient-to-br from-primary to-primary/85 px-4 py-2.5 text-sm text-primary-foreground shadow-md shadow-primary/15"
      >
        {{ msg.content }}
      </div>
      <!-- User message toolbar (timestamp + copy + edit) -->
      <div
        class="mt-0.5 flex items-center justify-end gap-0.5 transition-opacity duration-200"
        :class="compact ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
      >
        <span v-if="msg.created_at" class="mr-0.5 text-[10px] tabular-nums text-muted-foreground/40">
          {{ formatTimeOnly(msg.created_at) }}
        </span>
        <Tooltip :title="$t('common.globalAiChat.copy')">
          <button
            class="flex size-5 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
            @click="emit('copy', msg.content)"
          >
            <IconifyIcon icon="lucide:copy" class="size-2.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.editResend')">
          <button
            class="flex size-5 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
            @click="emit('edit', props.index)"
          >
            <IconifyIcon icon="lucide:pencil" class="size-2.5" />
          </button>
        </Tooltip>
      </div>
    </div>
  </div>
</template>
