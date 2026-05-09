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
    <div
      class="group/user-message"
      :class="compact ? 'max-w-[88%]' : 'max-w-[44rem]'"
    >
      <!-- Attachments -->
      <div
        v-if="msg.attachments?.length"
        class="flex flex-wrap justify-end"
        :class="compact ? 'mb-1.5 gap-1.5' : 'mb-2 gap-2'"
      >
        <template
          v-for="(att, ati) in msg.attachments"
          :key="`${ati}-${att.url}`"
        >
          <img
            v-if="att.type === 'image'"
            :src="att.preview || att.url"
            :alt="att.name || ''"
            class="user-attachment cursor-pointer rounded-2xl object-contain"
            :class="compact ? 'max-h-32 max-w-40' : 'max-h-44 max-w-56'"
            @error="onUserAttachmentImageError($event, att)"
            @click="emit('openUrl', att.url)"
          />
          <audio
            v-else-if="att.type === 'audio'"
            controls
            :src="att.url"
            class="user-attachment max-w-full rounded-2xl"
            :class="compact ? 'max-w-48' : 'max-w-64'"
          ></audio>
          <video
            v-else-if="att.type === 'video'"
            controls
            :src="att.url"
            class="user-attachment max-w-full rounded-2xl object-contain"
            :class="compact ? 'max-h-32 max-w-40' : 'max-h-44 max-w-56'"
          ></video>
          <a
            v-else
            :href="att.url"
            target="_blank"
            rel="noopener noreferrer"
            class="user-file-chip flex items-center rounded-full"
            :class="
              compact
                ? 'gap-1 px-2 py-1 text-[10px]'
                : 'gap-1.5 px-2.5 py-1 text-[10.5px]'
            "
          >
            <IconifyIcon
              :icon="getFileIcon(att.name || '', att.mime_type)"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            <span
              :class="compact ? 'max-w-[80px]' : 'max-w-[120px]'"
              class="truncate"
            >
              {{ att.name || $t('common.globalAiChat.file') }}
            </span>
          </a>
        </template>
      </div>
      <div
        v-if="msg.content"
        class="user-message-bubble whitespace-pre-wrap rounded-[15px] rounded-br-[8px] border px-3.5 py-2.5 text-primary-foreground"
        :class="
          compact
            ? 'text-[13.5px] leading-[1.74]'
            : 'text-[14.25px] leading-[1.8]'
        "
      >
        {{ msg.content }}
      </div>
      <!-- User message toolbar (timestamp + copy + edit) -->
      <div
        class="mt-1 flex items-center justify-end gap-1 transition-opacity duration-200"
        :class="
          compact
            ? 'opacity-100'
            : 'opacity-0 group-hover/user-message:opacity-100'
        "
      >
        <span
          v-if="msg.created_at"
          class="text-muted-foreground/42 mr-1 text-[9px] tabular-nums"
        >
          {{ formatTimeOnly(msg.created_at) }}
        </span>
        <Tooltip :title="$t('common.globalAiChat.copy')">
          <button
            class="user-action-button flex size-5 items-center justify-center rounded-full"
            @click="emit('copy', msg.content)"
          >
            <IconifyIcon icon="lucide:copy" class="size-2.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('common.globalAiChat.editResend')">
          <button
            class="user-action-button flex size-5 items-center justify-center rounded-full"
            @click="emit('edit', props.index)"
          >
            <IconifyIcon icon="lucide:pencil" class="size-2.5" />
          </button>
        </Tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-message-bubble {
  background: hsl(var(--primary) / 88%);
  border-color: hsl(var(--primary) / 16%);
  box-shadow: 0 10px 18px -24px hsl(var(--primary) / 18%);
}

.user-attachment {
  background: hsl(var(--background));
  border: 1px solid hsl(var(--border) / 28%);
  box-shadow: 0 12px 20px -24px hsl(var(--foreground) / 10%);
}

.user-file-chip {
  color: hsl(var(--foreground) / 82%);
  background: hsl(var(--background) / 94%);
  border: 1px solid hsl(var(--border) / 26%);
  box-shadow: 0 8px 16px -22px hsl(var(--foreground) / 10%);
}

.user-action-button {
  color: hsl(var(--muted-foreground) / 58%);
  background: hsl(var(--background) / 70%);
  border: 1px solid hsl(var(--border) / 10%);
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.user-action-button:hover {
  color: hsl(var(--foreground) / 84%);
  background: hsl(var(--primary) / 8%);
  border-color: hsl(var(--primary) / 16%);
}
</style>
