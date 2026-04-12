<script lang="ts" setup>
import type {
  MonitoringConversationMessage,
  MonitoringConversationDetail,
} from '../../api';

import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Image, Tag, Timeline, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatTimeOnly } from '#/utils/common';
import { toAbsoluteApiUrl } from '#/utils/image';

import {
  formatTokens,
  roleColor,
  truncateText,
} from './helpers';

defineOptions({ name: 'MonitoringConversationMessagesCard' });

interface MessageAttachment {
  attachment_id?: number;
  mime_type?: string;
  name?: string;
  type?: string;
  url?: string;
}

defineProps<{
  i18nPrefix: string;
  messages: MonitoringConversationDetail['message_list'];
}>();

function getMessageAttachments(
  message: MonitoringConversationMessage,
): MessageAttachment[] {
  const meta = message.metadata;
  if (!meta || typeof meta !== 'object') return [];
  const raw = (meta as Record<string, unknown>).attachments;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (item): item is MessageAttachment =>
        Boolean(item) && typeof item === 'object' && !Array.isArray(item),
    )
    .map((item) => ({
      ...item,
      url: toAbsoluteApiUrl(item.url) || item.url,
    }));
}
</script>

<template>
  <Card class="monitoring-card" :bordered="false">
    <template #title>
      <div class="monitoring-card__title">
        <IconifyIcon class="size-4" icon="lucide:messages-square" />
        <span>{{ $t(`${i18nPrefix}.tabMessages`) }}</span>
        <Tag color="blue">
          {{ formatTokens(messages.length) }}
        </Tag>
      </div>
    </template>

    <Empty v-if="messages.length === 0" />

    <Timeline v-else class="monitoring-scroll-area">
      <Timeline.Item
        v-for="message in messages"
        :key="message.id"
        :color="roleColor(message.role)"
      >
        <div class="monitoring-message-item">
          <div class="monitoring-message-head">
            <Tag :color="roleColor(message.role)">
              {{ message.role }}
            </Tag>
            <span class="text-xs text-muted-foreground">
              #{{ message.sequence }}
            </span>
            <Tooltip :title="formatDate(message.created_at)">
              <span class="text-xs text-muted-foreground">
                {{ formatTimeOnly(message.created_at) }}
              </span>
            </Tooltip>
            <span v-if="message.token_count" class="text-xs text-muted-foreground">
              {{ formatTokens(message.token_count) }}
            </span>
            <Tag v-if="message.tool_name" color="purple">
              {{ message.tool_name }}
            </Tag>
          </div>

          <div
            v-if="getMessageAttachments(message).length > 0"
            class="mt-1 flex flex-wrap gap-1.5"
          >
            <template
              v-for="(att, ati) in getMessageAttachments(message)"
              :key="ati"
            >
              <Image
                v-if="att.type === 'image' && att.url"
                :src="att.url"
                :alt="att.name || ''"
                class="max-h-32 max-w-40 cursor-pointer rounded-lg border border-border/50 object-contain"
                :preview="{ src: att.url }"
              />
              <a
                v-else
                :href="att.url"
                target="_blank"
                class="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-xs text-foreground hover:bg-muted"
              >
                <IconifyIcon class="size-3" icon="lucide:paperclip" />
                {{ att.name || att.url || $t('common.attachment') }}
              </a>
            </template>
          </div>

          <div v-if="message.tool_calls?.length" class="mt-1 space-y-1">
            <div
              v-for="(tc, tci) in message.tool_calls"
              :key="tci"
              class="rounded bg-muted/40 px-2 py-1 text-xs"
            >
              <span class="font-medium">{{
                (tc as any)?.function?.name || '-'
              }}</span>
              <span
                v-if="(tc as any)?.function?.arguments"
                class="ml-1 text-muted-foreground"
              >
                {{ truncateText((tc as any).function.arguments, 200) }}
              </span>
            </div>
          </div>

          <div
            v-if="message.content"
            class="monitoring-message-content whitespace-pre-wrap"
          >
            {{ message.content }}
          </div>
          <div
            v-else-if="!message.tool_calls?.length && getMessageAttachments(message).length === 0"
            class="text-xs text-muted-foreground"
          >
            -
          </div>
        </div>
      </Timeline.Item>
    </Timeline>
  </Card>
</template>
