<script lang="ts" setup>
/**
 * Chat Message Item - Renders a single chat message (assistant or user).
 *
 * Supports two visual densities via `compact` prop:
 * - false (default): Full page layout with avatar, Tag status, RAG sources
 * - true: Compact drawer layout with smaller sizes, no avatar/Tag/RAG
 */
import type { AgentItem, ChatMessage } from './types';

import { IconifyIcon } from '@vben/icons';

import { Button, Spin, Tag, Tooltip } from 'ant-design-vue';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    msg: ChatMessage;
    index: number;
    compact?: boolean;
    selectedAgent?: AgentItem | null;
  }>(),
  { compact: false, selectedAgent: null },
);

const emit = defineEmits<{
  copy: [content: string];
  confirm: [index: number];
  reject: [index: number];
  'open-url': [url: string];
}>();

function agentAvatar(agent: { avatar?: string | null }) {
  return agent.avatar || null;
}

function agentInitial(agent: { name: string }) {
  return agent.name.charAt(0).toUpperCase();
}
</script>

<template>
  <div
    class="flex"
    :class="[
      msg.role === 'user' ? 'justify-end' : 'justify-start',
      compact ? 'gap-2' : 'gap-3',
    ]"
  >
    <!-- ===== Assistant message ===== -->
    <div
      v-if="msg.role === 'assistant'"
      class="group"
      :class="compact ? 'max-w-[90%]' : 'flex max-w-[80%] gap-2'"
    >
      <!-- Avatar (page mode only) -->
      <div
        v-if="!compact"
        class="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-xs font-medium text-primary"
      >
        <img
          v-if="selectedAgent && agentAvatar(selectedAgent)"
          :src="agentAvatar(selectedAgent)!"
          :alt="selectedAgent?.name || ''"
          class="size-full rounded-lg object-cover"
        />
        <span v-else-if="selectedAgent">{{ agentInitial(selectedAgent) }}</span>
        <IconifyIcon v-else icon="lucide:bot" class="size-3.5" />
      </div>

      <div class="min-w-0">
        <!-- Thinking (no tool calls yet) -->
        <div
          v-if="msg.streaming && !msg.content && !msg.toolCalls?.length"
          class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-muted-foreground"
          :class="compact ? 'text-xs' : 'text-sm'"
        >
          <Spin size="small" />
          <span>{{ $t('common.globalAiChat.thinking') }}</span>
        </div>

        <!-- Optimizing tools indicator -->
        <div
          v-if="msg.optimizingTools"
          class="flex items-center rounded-lg bg-accent/50 text-muted-foreground"
          :class="compact ? 'mb-1 gap-1.5 px-2 py-1 text-[11px]' : 'mb-2 gap-2 px-3 py-1.5 text-xs'"
        >
          <span
            class="text-primary"
            :class="compact ? 'icon-[lucide--sparkles] h-3 w-3' : 'icon-[lucide--sparkles] h-3.5 w-3.5'"
          />
          <span>{{ $t('common.globalAiChat.optimizingTools', { total: msg.optimizingTools.total, selected: msg.optimizingTools.selected }) }}</span>
        </div>

        <!-- Tool calls -->
        <div
          v-if="msg.toolCalls?.length"
          :class="compact ? 'mb-1 space-y-0.5' : 'mb-2 space-y-1'"
        >
          <details
            v-for="(tc, tcIdx) in msg.toolCalls"
            :key="tcIdx"
            class="group/tc bg-accent/50 [&>summary]:list-none [&>summary::-webkit-details-marker]:hidden"
            :class="compact ? 'rounded' : 'rounded-md'"
          >
            <summary
              class="flex cursor-pointer items-center select-none"
              :class="compact ? 'gap-1.5 px-2 py-1 text-[11px]' : 'gap-2 px-3 py-1.5 text-xs'"
            >
              <Spin v-if="tc.status === 'running'" size="small" />
              <IconifyIcon
                v-else
                :icon="tc.status === 'success' ? 'lucide:check-circle' : 'lucide:x-circle'"
                class="shrink-0"
                :class="[
                  compact ? 'size-3' : 'size-3.5',
                  tc.status === 'success' ? 'text-green-600' : 'text-red-500',
                ]"
              />
              <span class="flex-1 truncate text-muted-foreground">
                <template v-if="tc.skillName">
                  <span class="font-medium text-foreground/70">{{ tc.skillName }}</span>
                  <span :class="compact ? 'mx-0.5' : 'mx-1'" class="text-muted-foreground/50">›</span>
                </template>
                {{ tc.name }}
              </span>
              <!-- Tag status (page mode only) -->
              <Tag
                v-if="!compact && tc.status !== 'running'"
                :color="tc.status === 'success' ? 'success' : 'error'"
                size="small"
              >
                {{ tc.status === 'success' ? $t('common.globalAiChat.toolSuccess') : $t('common.globalAiChat.toolFailed') }}
              </Tag>
              <span v-if="!compact && tc.status === 'running'" class="text-muted-foreground">
                {{ $t('common.globalAiChat.toolRunning') }}
              </span>
              <span v-if="tc.durationMs" class="text-muted-foreground/60">
                {{ (tc.durationMs / 1000).toFixed(1) }}s
              </span>
              <IconifyIcon
                v-if="tc.status !== 'running'"
                icon="lucide:chevron-down"
                class="shrink-0 text-muted-foreground transition-transform duration-200 group-open/tc:rotate-180"
                :class="compact ? 'size-3' : 'size-3.5'"
              />
            </summary>
            <div
              v-if="tc.output || tc.error || tc.arguments"
              class="border-t border-border/50"
              :class="compact ? 'px-2 py-1.5 text-[11px]' : 'px-3 py-2 text-xs'"
            >
              <div v-if="tc.arguments && Object.keys(tc.arguments).length" class="mb-1">
                <span class="font-medium text-muted-foreground">Args:</span>
                <code class="ml-1 text-muted-foreground" :class="compact ? 'text-[10px]' : 'text-[11px]'">
                  {{ JSON.stringify(tc.arguments) }}
                </code>
              </div>
              <div
                v-if="tc.output"
                class="overflow-y-auto whitespace-pre-wrap break-all text-muted-foreground"
                :class="compact ? 'max-h-40' : 'max-h-48'"
              >
                {{ tc.output }}
              </div>
              <div v-if="tc.error" class="whitespace-pre-wrap break-all text-red-500">
                {{ tc.error }}
              </div>
            </div>
          </details>
          <!-- Generating indicator after tool calls -->
          <div
            v-if="msg.streaming && !msg.content"
            class="flex items-center gap-2 text-muted-foreground"
            :class="compact ? 'px-2 py-1 text-[11px]' : 'px-3 py-1 text-xs'"
          >
            <Spin size="small" />
            <span>{{ $t('common.globalAiChat.generating') }}</span>
          </div>
        </div>

        <!-- Markdown content -->
        <div
          v-if="msg.content"
          class="rounded-lg border border-border bg-accent/30"
          :class="compact ? 'px-3 py-2 text-sm' : 'px-4 py-2.5'"
        >
          <MarkdownRender :content="msg.content" :streaming="!!msg.streaming" />
          <span v-if="msg.streaming" class="streaming-cursor" />
        </div>

        <!-- Confirmation card -->
        <div
          v-if="msg.pendingConfirmation && !msg.streaming"
          class="rounded-lg border border-warning/40 bg-warning/5"
          :class="compact ? 'mt-1.5 px-3 py-2' : 'mt-2 px-4 py-3'"
        >
          <div
            class="flex items-center font-medium text-foreground"
            :class="compact ? 'mb-1.5 gap-1.5 text-xs' : 'mb-2 gap-2 text-sm'"
          >
            <IconifyIcon icon="lucide:shield-question" class="size-4 text-warning" />
            <span>{{ $t('common.globalAiChat.confirmationTitle') }}</span>
          </div>
          <div
            v-if="msg.pendingConfirmation.preview"
            class="overflow-y-auto rounded-md bg-accent/50 font-mono text-muted-foreground"
            :class="compact ? 'mb-2 max-h-32 px-2 py-1.5 text-[10px]' : 'mb-3 max-h-40 px-3 py-2 text-xs'"
          >
            <pre class="whitespace-pre-wrap">{{ JSON.stringify(msg.pendingConfirmation.preview, null, 2) }}</pre>
          </div>
          <div v-if="!msg.pendingConfirmation.resolved" class="flex items-center gap-2">
            <Button type="primary" size="small" @click="emit('confirm', props.index)">
              <template #icon>
                <IconifyIcon icon="lucide:check" :class="compact ? 'size-3' : 'size-3.5'" />
              </template>
              {{ $t('common.globalAiChat.confirmBtn') }}
            </Button>
            <Button size="small" danger @click="emit('reject', props.index)">
              <template #icon>
                <IconifyIcon icon="lucide:x" :class="compact ? 'size-3' : 'size-3.5'" />
              </template>
              {{ $t('common.globalAiChat.rejectBtn') }}
            </Button>
          </div>
          <div v-else :class="compact ? 'text-[11px]' : 'text-xs'" class="text-muted-foreground">
            <IconifyIcon icon="lucide:check-circle" class="mr-1 inline text-success" :class="compact ? 'size-3' : 'size-3.5'" />
            {{ $t('common.globalAiChat.confirmationResolved') }}
          </div>
        </div>

        <!-- RAG sources (page mode only) -->
        <div
          v-if="!compact && msg.ragSources && msg.ragSources.length > 0 && !msg.streaming"
          class="mt-2"
        >
          <details class="group">
            <summary class="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
              <IconifyIcon icon="lucide:book-open" class="size-3.5" />
              <span>{{ $t('common.globalAiChat.ragSources') }} ({{ msg.ragSources.length }})</span>
            </summary>
            <div class="mt-1.5 space-y-1.5 pl-5">
              <div
                v-for="(src, si) in msg.ragSources"
                :key="si"
                class="rounded-md bg-accent/50 px-2.5 py-1.5 text-xs text-muted-foreground"
              >
                <div class="font-medium text-foreground">{{ src.doc_name }}</div>
                <div class="mt-0.5 line-clamp-2">{{ src.snippet }}</div>
              </div>
            </div>
          </details>
        </div>

        <!-- Stats + Copy -->
        <div
          v-if="msg.content && !msg.streaming"
          class="flex items-center text-muted-foreground"
          :class="compact ? 'mt-0.5 gap-2 text-[11px]' : 'mt-1 gap-3 text-xs'"
        >
          <span v-if="msg.tokenUsage">{{ msg.tokenUsage }} tokens</span>
          <span v-if="!compact && msg.durationMs">{{ (msg.durationMs / 1000).toFixed(1) }}s</span>
          <Tooltip v-if="!compact" :title="$t('common.globalAiChat.copy')">
            <IconifyIcon
              icon="lucide:copy"
              class="cursor-pointer opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
              :class="compact ? 'size-3' : 'size-3.5'"
              @click="emit('copy', msg.content)"
            />
          </Tooltip>
          <IconifyIcon
            v-else
            icon="lucide:copy"
            class="size-3 cursor-pointer opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
            @click="emit('copy', msg.content)"
          />
        </div>
      </div>
    </div>

    <!-- ===== User message ===== -->
    <div v-else :class="compact ? 'max-w-[85%]' : 'max-w-[75%]'">
      <!-- Attachments -->
      <div
        v-if="msg.attachments?.length"
        class="flex flex-wrap justify-end"
        :class="compact ? 'mb-1 gap-1' : 'mb-1.5 gap-1.5'"
      >
        <template v-for="(att, ati) in msg.attachments" :key="ati">
          <img
            v-if="att.type === 'image'"
            :src="att.preview || att.url"
            :alt="att.name || ''"
            class="cursor-pointer rounded-lg object-contain"
            :class="compact ? 'max-h-32 max-w-40' : 'max-h-48 max-w-60 border border-white/20'"
            @click="emit('open-url', att.url)"
          />
          <a
            v-else-if="!compact"
            :href="att.url"
            target="_blank"
            class="flex items-center gap-1.5 rounded-lg bg-primary-foreground/10 px-2 py-1 text-xs text-primary-foreground hover:bg-primary-foreground/20"
          >
            <IconifyIcon icon="lucide:file" class="size-3.5" />
            {{ att.name || $t('common.globalAiChat.file') }}
          </a>
        </template>
      </div>
      <div
        v-if="msg.content"
        class="whitespace-pre-wrap rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
      >
        {{ msg.content }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.streaming-cursor::after {
  content: '▍';
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: hsl(var(--primary));
  font-weight: bold;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
