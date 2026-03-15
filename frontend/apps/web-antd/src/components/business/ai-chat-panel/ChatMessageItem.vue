<script lang="ts" setup>
/**
 * Chat Message Item - Renders a single chat message (assistant or user).
 * 单条聊天消息项 — 渲染一条助手或用户消息。
 *
 * Supports two visual densities via `compact` prop:
 * 通过 compact 支持两种展示密度：
 * - false (default): Full page layout with avatar, Tag status, RAG sources
 * - true: Compact drawer layout with smaller sizes, no avatar/Tag/RAG
 */
import type { AgentItem, ChatMessage } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useAIPanelStore } from '#/store';

import { Button, Tooltip } from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import { MarkdownRender } from '#/components/business/markdown-render';
import { getPageOpErrorHintKey } from '#/components/business/ai-chat-panel/pageOpErrorHints';
import { $t } from '#/locales';
import { formatTimeOnly } from '#/utils/common';
import { getFileIcon } from '#/utils/file';

/** Pending page op for inline confirmation card / 待确认的页面操作（内联卡片） */
export interface PendingPageOpForDisplay {
  invokeId: string;
  operationLabel: string;
  operationDescription: string;
  params: Record<string, unknown>;
  resolved: boolean;
  allowed?: boolean;
  startedAt: number;
  toolCallId?: string;
}

const props = withDefaults(
  defineProps<{
    apiPrefix?: string;
    compact?: boolean;
    index: number;
    msg: ChatMessage;
    selectedAgent?: AgentItem | null;
    /** Whether to show an agent-switch separator above this message / 是否在本条消息上方显示智能体切换分隔 */
    showAgentSwitch?: boolean;
    /** Pending page ops for this message (filtered by toolCallId) / 本消息关联的待确认操作 */
    pendingOps?: PendingPageOpForDisplay[];
    /** Current timestamp for 60s countdown display (fallback: local now) / 用于 60s 倒计时的当前时间戳 */
    countdownNow?: number;
  }>(),
  { apiPrefix: '', compact: false, selectedAgent: null, showAgentSwitch: false, pendingOps: () => [] },
);

/** Resolve agent display info: prefer message-level, fallback to selectedAgent / 解析智能体展示信息：优先消息级，否则用 selectedAgent */
const msgAgentName = computed(() =>
  props.msg.agent_name || props.selectedAgent?.name || null,
);
const msgAgentDescription = computed(() =>
  props.msg.agent_description || props.selectedAgent?.description || null,
);
const msgModelName = computed(() =>
  props.msg.model_name || props.selectedAgent?.model_name || null,
);

const emit = defineEmits<{
  actionClick: [index: number, value: string];
  confirm: [index: number];
  consentConfirm: [index: number];
  consentReject: [index: number];
  copy: [content: string];
  edit: [index: number];
  openUrl: [url: string];
  regenerate: [index: number];
  reject: [index: number];
  retry: [index: number];
}>();


const aiPanelStore = useAIPanelStore();

/** Whether this tool call has a pending confirmation (inline) / 该工具调用是否有待确认（内联） */
function hasPendingForToolCall(tc: { id?: string; name: string; status: string }): boolean {
  if (tc.status !== 'running') return false;
  if (tc.name !== 'invoke_page_operation' && !tc.name.startsWith('pageop_')) return false;
  if (!props.pendingOps?.length) return false;
  // Prefer toolCallId match when available / 有 toolCallId 时精确匹配
  const matched = props.pendingOps.some(
    (op) => op.toolCallId && op.toolCallId === tc.id && !op.resolved,
  );
  if (matched) return true;
  // Fallback: legacy ops without toolCallId, any unresolved = waiting / 兜底：无 toolCallId 的旧数据，存在未解决则显示待确认 */
  return props.pendingOps.some((op) => !op.toolCallId && !op.resolved);
}

/** Display sub-state for running tools: waiting_confirm vs executing / 运行中工具的展示子状态 */
function getToolDisplayState(tc: { id?: string; name: string; status: string }): 'executing' | 'waiting_confirm' {
  if (tc.status !== 'running') return 'executing';
  if (hasPendingForToolCall(tc)) return 'waiting_confirm';
  return 'executing';
}

/** Ticking now for "still running" countdown (8s+) / 用于“仍在执行”提示的计时 */
const now = ref(Date.now());
const hasRunningTool = computed(() =>
  props.msg.toolCalls?.some((tc) => tc.status === 'running') ?? false,
);
let tickInterval: ReturnType<typeof setInterval> | null = null;
function startTick() {
  if (tickInterval) return;
  tickInterval = setInterval(() => {
    now.value = Date.now();
  }, 1000);
}
function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval);
    tickInterval = null;
  }
}
watch(hasRunningTool, (running) => {
  if (running) startTick();
  else stopTick();
}, { immediate: true });
onUnmounted(stopTick);
</script>

<template>
  <!-- Agent switch separator -->
  <div
    v-if="showAgentSwitch && msg.role === 'assistant' && msgAgentName"
    class="flex items-center gap-2 py-1"
    :class="compact ? 'mb-1' : 'mb-2'"
  >
    <div class="h-px flex-1 bg-border/40" />
    <div
      class="flex items-center gap-1 rounded-full bg-muted/60 px-2.5 py-0.5 text-muted-foreground"
      :class="compact ? 'text-[10px]' : 'text-xs'"
    >
      <IconifyIcon icon="lucide:arrow-right" class="size-3" />
      <span>{{ msgAgentName }}</span>
    </div>
    <div class="h-px flex-1 bg-border/40" />
  </div>

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
      class="group flex"
      :class="compact ? 'max-w-[90%] gap-1.5' : 'max-w-[80%] gap-2'"
    >
      <!-- Avatar with profile card popover -->
      <AgentProfilePopover
        :agent-id="msg.agent_id || selectedAgent?.id"
        :agent-avatar="msg.agent_avatar || selectedAgent?.avatar"
        :agent-name="msgAgentName"
        :agent-description="msgAgentDescription"
        :model-name="msgModelName"
        :api-prefix="apiPrefix"
        :size="compact ? 'sm' : 'md'"
      />

      <div class="min-w-0">
        <!-- Agent name + model label -->
        <div
          v-if="msgAgentName && msg.agent_id"
          :class="compact ? 'mb-0.5' : 'mb-1'"
        >
          <span :class="compact ? 'text-[10px]' : 'text-xs'" class="font-medium text-muted-foreground">
            {{ msgAgentName }}
          </span>
          <span
            v-if="!compact && msgModelName"
            class="ml-1.5 rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground/60"
          >
            {{ msgModelName }}
          </span>
        </div>

        <!-- Thinking (no tool calls yet) - skeleton pulse -->
        <div
          v-if="msg.streaming && !msg.content && !msg.toolCalls?.length"
          class="thinking-skeleton space-y-2 rounded-xl border border-border/20 bg-accent/30 px-3 py-3"
        >
          <div class="flex items-center gap-2">
            <div class="thinking-glow relative flex size-5 items-center justify-center rounded-full bg-primary/10">
              <span class="typing-dots"><span /><span /><span /></span>
            </div>
            <span class="text-xs font-medium text-muted-foreground">{{ $t('common.globalAiChat.thinking') }}</span>
          </div>
          <div class="space-y-2">
            <div class="skeleton-line h-2 w-[90%] rounded-full bg-muted/50"></div>
            <div class="skeleton-line h-2 w-[72%] rounded-full bg-muted/50" style="animation-delay: 0.15s"></div>
            <div class="skeleton-line h-2 w-[55%] rounded-full bg-muted/50" style="animation-delay: 0.3s"></div>
          </div>
        </div>

        <!-- Optimizing tools indicator -->
        <div
          v-if="msg.optimizingTools"
          class="flex items-center rounded-lg bg-accent/50 text-muted-foreground"
          :class="
            compact
              ? 'mb-1 gap-1.5 px-2 py-1 text-[11px]'
              : 'mb-2 gap-2 px-3 py-1.5 text-xs'
          "
        >
          <span
            class="text-primary"
            :class="
              compact
                ? 'icon-[lucide--sparkles] h-3 w-3'
                : 'icon-[lucide--sparkles] h-3.5 w-3.5'
            "
          ></span>
          <span>{{
            $t('common.globalAiChat.optimizingTools', {
              total: msg.optimizingTools.total,
              selected: msg.optimizingTools.selected,
            })
          }}</span>
        </div>

        <!-- Markdown content -->
        <div
          v-if="msg.content"
          class="rounded-2xl border border-border/30 bg-gradient-to-br from-muted/40 to-muted/20 shadow-sm"
          :class="compact ? 'px-2.5 py-1.5 text-sm' : 'px-4 py-3'"
        >
          <MarkdownRender :content="msg.content" :streaming="!!msg.streaming" />
          <span v-if="msg.streaming" class="streaming-cursor"></span>
          <span
            v-if="msg.stoppedByUser && !msg.streaming"
            class="ml-1 text-muted-foreground/70"
          >
            {{ $t('common.globalAiChat.generationStopped') }}
          </span>
        </div>
        <!-- SSE error retry -->
        <div
          v-if="msg.requestFailedRetry"
          class="mt-1 flex items-center gap-1.5"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          <Button
            type="link"
            size="small"
            class="!p-0 !text-primary"
            @click="emit('retry', index)"
          >
            {{ $t('common.globalAiChat.retry') }}
          </Button>
        </div>

        <!-- Generating indicator (tool calls running but no content yet) -->
        <div
          v-if="msg.streaming && !msg.content && msg.toolCalls?.length"
          class="flex items-center gap-1.5 px-2 py-0.5 text-muted-foreground"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          <span class="typing-dots"><span /><span /><span /></span>
          <span>{{ $t('common.globalAiChat.generating') }}</span>
        </div>

        <!-- Tool calls timeline (below content) -->
        <div
          v-if="msg.toolCalls?.length"
          class="tc-timeline relative"
          :class="compact ? 'mt-1 pl-3' : 'mt-1.5 pl-4'"
        >
          <!-- Timeline vertical line -->
          <div
            v-if="msg.toolCalls.length > 1"
            class="absolute w-px bg-border/40"
            :class="compact ? 'bottom-1 left-[4px] top-1' : 'bottom-1.5 left-[5px] top-1.5'"
          />

          <div
            v-for="(tc, tcIdx) in msg.toolCalls"
            :key="tcIdx"
            class="relative"
            :class="tcIdx > 0 ? (compact ? 'mt-0.5' : 'mt-1') : ''"
          >
            <!-- Timeline dot -->
            <div
              class="absolute z-[1]"
              :class="compact ? '-left-3 top-[5px]' : '-left-4 top-[7px]'"
            >
              <span
                v-if="tc.status === 'running'"
                class="tc-dot-pulse block rounded-full bg-primary"
                :class="compact ? 'size-[7px]' : 'size-2'"
              />
              <span
                v-else-if="tc.status === 'success'"
                class="block rounded-full bg-green-500"
                :class="compact ? 'size-[7px]' : 'size-2'"
              />
              <span
                v-else
                class="block rounded-full bg-red-500"
                :class="compact ? 'size-[7px]' : 'size-2'"
              />
            </div>

            <!-- Tool call card -->
            <details
              class="group/tc overflow-hidden rounded-lg border border-border/20 bg-accent/15 backdrop-blur-sm transition-colors hover:bg-accent/25 [&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
              :open="tc.status === 'error'"
            >
              <summary
                class="flex cursor-pointer select-none items-center"
                :class="compact ? 'gap-1 px-2 py-[3px] text-[11px]' : 'gap-1.5 px-2.5 py-1 text-xs'"
              >
                <!-- Status pill -->
                <span
                  class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px text-[10px] font-medium leading-tight"
                  :class="
                    tc.status === 'running'
                      ? getToolDisplayState(tc) === 'waiting_confirm'
                        ? 'tc-pill-pulse bg-warning/10 text-warning'
                        : 'tc-pill-pulse bg-primary/10 text-primary'
                      : tc.status === 'success'
                        ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                        : 'bg-red-500/10 text-red-500'
                  "
                >
                  <IconifyIcon
                    v-if="tc.status !== 'running'"
                    :icon="tc.status === 'success' ? 'lucide:check' : 'lucide:x'"
                    class="size-2.5"
                  />
                  <span v-else class="tc-dot-pulse mr-0.5 inline-block size-1.5 rounded-full bg-current" />
                  {{
                    tc.status === 'running'
                      ? getToolDisplayState(tc) === 'waiting_confirm'
                        ? $t('common.globalAiChat.toolWaitingConfirm')
                        : $t('common.globalAiChat.toolExecuting')
                      : tc.status === 'success'
                        ? $t('common.globalAiChat.toolStatusOk')
                        : $t('common.globalAiChat.toolStatusErr')
                  }}
                </span>

                <!-- Tool name -->
                <span class="flex-1 truncate text-muted-foreground">
                  <template v-if="tc.skillName">
                    <span class="font-medium text-foreground/60">{{ tc.skillName }}</span>
                    <span class="mx-0.5 text-muted-foreground/30">›</span>
                  </template>
                  <span class="text-foreground/70">{{ tc.displayName || tc.name }}</span>
                  <span
                    v-if="tc.summary && tc.status === 'success'"
                    class="ml-1 text-muted-foreground/50"
                  >— {{ tc.summary }}</span>
                </span>

                <!-- Duration -->
                <span v-if="tc.durationMs" class="tabular-nums text-[10px] text-muted-foreground/40">
                  {{ (tc.durationMs / 1000).toFixed(1) }}s
                </span>

                <!-- Expand chevron -->
                <IconifyIcon
                  v-if="tc.status !== 'running'"
                  icon="lucide:chevron-down"
                  class="shrink-0 text-muted-foreground/30 transition-transform duration-200 group-open/tc:rotate-180"
                  :class="compact ? 'size-2.5' : 'size-3'"
                />
              </summary>

              <!-- Expanded details -->
              <div
                v-if="tc.output || tc.error || tc.arguments"
                class="border-t border-border/20"
                :class="compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-[11px]'"
              >
                <div
                  v-if="tc.arguments && Object.keys(tc.arguments).length > 0"
                  class="mb-1"
                >
                  <span class="font-medium text-muted-foreground/60">{{ $t('common.globalAiChat.args') }}</span>
                  <code class="ml-1 rounded bg-accent/50 px-1 py-px text-[10px] text-muted-foreground">
                    {{ JSON.stringify(tc.arguments) }}
                  </code>
                </div>
                <div
                  v-if="tc.output"
                  class="overflow-y-auto whitespace-pre-wrap break-all rounded bg-accent/30 px-1.5 py-1 text-muted-foreground"
                  :class="compact ? 'max-h-32' : 'max-h-40'"
                >
                  {{ tc.output }}
                </div>
                <div
                  v-if="tc.error"
                  class="whitespace-pre-wrap break-all rounded bg-red-50 px-1.5 py-1 text-red-500 dark:bg-red-950/30"
                >
                  {{ tc.error }}
                </div>
                <p
                  v-if="tc.status === 'error' && getPageOpErrorHintKey(tc.errorType)"
                  class="mt-1 text-[10px] text-muted-foreground"
                >
                  {{ $t(getPageOpErrorHintKey(tc.errorType)) }}
                </p>
                <a
                  v-if="tc.resultLink && tc.status === 'success'"
                  :href="tc.resultLink"
                  target="_blank"
                  class="mt-1 inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
                >
                  <IconifyIcon icon="lucide:external-link" class="size-2.5" />
                  {{ $t('common.globalAiChat.viewResult') }}
                </a>
              </div>
            </details>
            <!-- Inline confirmation card (for this tool call) / 内联确认卡片（对应本工具调用） -->
            <div
              v-for="op in (pendingOps || []).filter(o => o.toolCallId === tc.id)"
              :key="op.invokeId"
              class="mt-1 overflow-hidden rounded-lg border"
              :class="op.resolved ? 'border-border/20 bg-accent/10' : 'border-warning/30 bg-warning/5'"
            >
              <!-- Resolved state -->
              <div
                v-if="op.resolved"
                class="flex items-center gap-1.5 px-2.5 py-1.5"
                :class="compact ? 'text-[10px]' : 'text-[11px]'"
              >
                <IconifyIcon
                  :icon="op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'"
                  class="size-3 shrink-0"
                  :class="op.allowed ? 'text-green-600' : 'text-red-500'"
                />
                <span class="truncate text-muted-foreground">
                  <span class="font-medium text-foreground/60">{{ op.operationLabel }}</span>
                  <span v-if="op.operationDescription" class="ml-1 text-muted-foreground/60">{{ op.operationDescription }}</span>
                </span>
                <span
                  class="ml-auto shrink-0 rounded-full px-1.5 py-px font-medium"
                  :class="[
                    compact ? 'text-[9px]' : 'text-[10px]',
                    op.allowed ? 'bg-green-50 text-green-600 dark:bg-green-950/30' : 'bg-red-50 text-red-600 dark:bg-red-950/30',
                  ]"
                >
                  {{ op.allowed ? $t('shared.pageOperation.confirmOk') : $t('shared.pageOperation.confirmCancel') }}
                </span>
              </div>
              <!-- Pending state -->
              <template v-else>
                <div
                  class="flex items-center gap-1.5 px-2.5 py-1.5"
                  :class="compact ? 'text-[10px]' : 'text-[11px]'"
                >
                  <IconifyIcon icon="lucide:shield-alert" class="size-3.5 shrink-0 text-warning" />
                  <div class="min-w-0 flex-1">
                    <div class="truncate font-medium text-foreground/80">
                      {{ op.operationLabel }}
                    </div>
                    <div v-if="op.operationDescription" class="truncate text-muted-foreground/60">
                      {{ op.operationDescription }}
                    </div>
                    <div class="mt-0.5 text-muted-foreground/50" :class="compact ? 'text-[9px]' : 'text-[10px]'">
                      {{ $t('shared.pageOperation.confirmCountdown', { seconds: Math.max(0, 60 - Math.floor(((countdownNow ?? now) - (op.startedAt || 0)) / 1000)) }) }}
                    </div>
                  </div>
                  <div class="flex shrink-0 items-center gap-1">
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, true)"
                    >
                      <IconifyIcon icon="lucide:check" class="size-3" />
                      {{ $t('shared.pageOperation.confirmOk') }}
                    </button>
                    <button
                      class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                      @click="aiPanelStore.resolvePageOp(op.invokeId, false)"
                    >
                      <IconifyIcon icon="lucide:x" class="size-3" />
                      {{ $t('shared.pageOperation.confirmCancel') }}
                    </button>
                  </div>
                </div>
                <details
                  v-if="op.params && Object.keys(op.params).length > 0"
                  class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
                >
                  <summary class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-muted-foreground/60 hover:text-muted-foreground" :class="compact ? 'text-[9px]' : 'text-[10px]'">
                    <IconifyIcon icon="lucide:code" class="size-2.5" />
                    {{ $t('common.globalAiChat.args') }}
                    <IconifyIcon icon="lucide:chevron-down" class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180" />
                  </summary>
                  <div class="border-t border-border/20 px-2.5 py-1">
                    <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-muted-foreground" :class="compact ? 'text-[9px]' : 'text-[10px]'">{{ JSON.stringify(op.params, null, 2) }}</pre>
                  </div>
                </details>
              </template>
            </div>
            <!-- Still running hint (8s+) - outside details so always visible / 执行超 8s 的提示 -->
            <p
              v-if="tc.status === 'running' && tc.startedAt && (now - tc.startedAt) >= 8000"
              class="mt-0.5 pl-1 text-[10px] text-muted-foreground"
            >
              {{ $t('common.globalAiChat.toolStillRunningHint') }}
            </p>
          </div>
        </div>

        <!-- Generated images -->
        <div
          v-if="msg.imageResults && msg.imageResults.length > 0"
          class="flex flex-wrap"
          :class="compact ? 'mt-1.5 gap-2' : 'mt-2 gap-3'"
        >
          <div
            v-for="(img, ii) in msg.imageResults"
            :key="ii"
            class="group/img relative overflow-hidden rounded-lg border border-border"
          >
            <img
              :src="img.isBase64 ? `data:image/png;base64,${img.url}` : img.url"
              :alt="
                img.revisedPrompt || $t('common.globalAiChat.generatedImage')
              "
              class="cursor-pointer object-cover transition-transform hover:scale-105"
              :class="compact ? 'max-h-48 max-w-56' : 'max-h-64 max-w-72'"
              @click="
                emit(
                  'openUrl',
                  img.isBase64 ? `data:image/png;base64,${img.url}` : img.url,
                )
              "
            />
            <a
              :href="
                img.isBase64 ? `data:image/png;base64,${img.url}` : img.url
              "
              :download="img.isBase64 ? 'generated-image.png' : undefined"
              target="_blank"
              class="absolute bottom-2 right-2 flex size-7 items-center justify-center rounded-full bg-black/50 text-white opacity-0 transition-opacity hover:bg-black/70 group-hover/img:opacity-100"
              :title="$t('common.globalAiChat.downloadImage')"
            >
              <IconifyIcon icon="lucide:download" class="size-3.5" />
            </a>
            <div
              v-if="img.revisedPrompt"
              class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-2 pb-1.5 pt-4 text-white opacity-0 transition-opacity group-hover/img:opacity-100"
              :class="compact ? 'text-[10px]' : 'text-xs'"
            >
              <span class="line-clamp-2">{{ img.revisedPrompt }}</span>
            </div>
          </div>
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
            <IconifyIcon
              icon="lucide:shield-question"
              class="size-4 text-warning"
            />
            <span>{{ $t('common.globalAiChat.confirmationTitle') }}</span>
          </div>
          <div
            v-if="msg.pendingConfirmation.preview"
            class="overflow-y-auto rounded-md bg-accent/50"
            :class="
              compact
                ? 'mb-2 max-h-32 px-2 py-1.5 text-[10px]'
                : 'mb-3 max-h-40 px-3 py-2 text-xs'
            "
          >
            <table class="w-full text-left">
              <tr
                v-for="(val, key) in msg.pendingConfirmation.preview"
                :key="String(key)"
                class="border-b border-border/30 last:border-0"
              >
                <td
                  class="whitespace-nowrap py-0.5 pr-3 font-medium text-foreground/70"
                >
                  {{ key }}
                </td>
                <td class="break-all py-0.5 text-muted-foreground">
                  {{ typeof val === 'object' ? JSON.stringify(val) : val }}
                </td>
              </tr>
            </table>
          </div>
          <div
            v-if="!msg.pendingConfirmation.resolved"
            class="flex items-center gap-2"
          >
            <Button
              type="primary"
              size="small"
              @click="emit('confirm', props.index)"
            >
              <template #icon>
                <IconifyIcon
                  icon="lucide:check"
                  :class="compact ? 'size-3' : 'size-3.5'"
                />
              </template>
              {{ $t('common.globalAiChat.confirmBtn') }}
            </Button>
            <Button size="small" danger @click="emit('reject', props.index)">
              <template #icon>
                <IconifyIcon
                  icon="lucide:x"
                  :class="compact ? 'size-3' : 'size-3.5'"
                />
              </template>
              {{ $t('common.globalAiChat.rejectBtn') }}
            </Button>
          </div>
          <div
            v-else
            :class="compact ? 'text-[11px]' : 'text-xs'"
            class="text-muted-foreground"
          >
            <IconifyIcon
              icon="lucide:check-circle"
              class="mr-1 inline text-success"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            {{ $t('common.globalAiChat.confirmationResolved') }}
          </div>
        </div>

        <!-- Tool consent card -->
        <div
          v-if="msg.pendingConsent && !msg.streaming"
          class="overflow-hidden rounded-lg border"
          :class="[
            compact ? 'mt-1' : 'mt-1.5',
            msg.pendingConsent.resolved
              ? 'border-border/20 bg-accent/10'
              : 'border-warning/30 bg-warning/5',
          ]"
        >
          <!-- Resolved state: compact single line -->
          <div
            v-if="msg.pendingConsent.resolved"
            class="flex items-center gap-1.5 px-2.5 py-1 text-[11px]"
          >
            <IconifyIcon
              :icon="msg.pendingConsent.rejected ? 'lucide:x-circle' : msg.pendingConsent.autoApproved ? 'lucide:shield-check' : 'lucide:check-circle'"
              class="size-3 shrink-0"
              :class="msg.pendingConsent.rejected ? 'text-red-500' : 'text-green-600'"
            />
            <span class="truncate text-muted-foreground">
              <span v-if="msg.pendingConsent.skillName" class="font-medium text-foreground/60">{{ msg.pendingConsent.skillName }} ›</span>
              <code class="text-[10px]">{{ msg.pendingConsent.toolName }}</code>
            </span>
            <span
              class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
              :class="
                msg.pendingConsent.rejected
                  ? 'bg-red-50 text-red-600 dark:bg-red-950/30'
                  : msg.pendingConsent.autoApproved
                    ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/30'
                    : 'bg-green-50 text-green-600 dark:bg-green-950/30'
              "
            >
              {{
                msg.pendingConsent.rejected
                  ? $t('common.globalAiChat.consentRejected')
                  : msg.pendingConsent.autoApproved
                    ? $t('common.globalAiChat.consentAutoApproved')
                    : $t('common.globalAiChat.consentApproved')
              }}
            </span>
          </div>

          <!-- Pending state: inline with actions -->
          <template v-else>
            <p
              class="border-b border-border/20 px-2.5 py-1 text-[10px] text-muted-foreground"
            >
              {{ $t('common.globalAiChat.consentFirstTimeHint') }}
            </p>
            <div class="flex items-center gap-1.5 px-2.5 py-1.5">
              <IconifyIcon
                icon="lucide:shield-alert"
                class="size-3.5 shrink-0 text-warning"
              />
              <span class="flex-1 truncate text-[11px] text-muted-foreground">
                <span v-if="msg.pendingConsent.skillName" class="font-medium text-foreground/70">{{ msg.pendingConsent.skillName }} ›</span>
                <code class="text-[10px] font-semibold">{{ msg.pendingConsent.toolName }}</code>
              </span>
              <div class="flex shrink-0 items-center gap-1">
                <button
                  class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                  @click="emit('consentConfirm', props.index)"
                >
                  <IconifyIcon icon="lucide:check" class="size-3" />
                  {{ $t('common.globalAiChat.consentAllow') }}
                </button>
                <button
                  class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                  @click="emit('consentReject', props.index)"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                  {{ $t('common.globalAiChat.consentDeny') }}
                </button>
              </div>
            </div>
            <!-- Collapsible args -->
            <details
              v-if="
                msg.pendingConsent.arguments &&
                Object.keys(msg.pendingConsent.arguments).length > 0
              "
              class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
            >
              <summary class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground">
                <IconifyIcon icon="lucide:code" class="size-2.5" />
                {{ $t('common.globalAiChat.consentShowArgs') }}
                <IconifyIcon icon="lucide:chevron-down" class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180" />
              </summary>
              <div class="border-t border-border/20 px-2.5 py-1">
                <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground">{{ JSON.stringify(msg.pendingConsent.arguments, null, 2) }}</pre>
              </div>
            </details>
          </template>
        </div>

        <!-- RAG sources -->
        <div
          v-if="msg.ragSources && msg.ragSources.length > 0 && !msg.streaming"
          :class="compact ? 'mt-1' : 'mt-1.5'"
        >
          <details class="group">
            <summary
              class="flex cursor-pointer items-center text-muted-foreground hover:text-foreground"
              :class="compact ? 'gap-1 text-[11px]' : 'gap-1.5 text-xs'"
            >
              <IconifyIcon
                icon="lucide:book-open"
                :class="compact ? 'size-3' : 'size-3.5'"
              />
              <span
                >{{ $t('common.globalAiChat.ragSources') }} ({{
                  msg.ragSources.length
                }})</span
              >
            </summary>
            <div
              :class="
                compact ? 'mt-1 space-y-1 pl-4' : 'mt-1.5 space-y-1.5 pl-5'
              "
            >
              <div
                v-for="(src, si) in msg.ragSources"
                :key="si"
                class="rounded-md bg-accent/50 text-muted-foreground"
                :class="
                  compact ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1.5 text-xs'
                "
              >
                <div class="font-medium text-foreground">
                  {{ src.doc_name }}
                </div>
                <div
                  :class="
                    compact ? 'mt-0.5 line-clamp-2' : 'mt-0.5 line-clamp-3'
                  "
                >
                  {{ src.snippet }}
                </div>
              </div>
            </div>
          </details>
        </div>

        <!-- Action Buttons -->
        <div
          v-if="
            msg.actionButtons && msg.actionButtons.length > 0 && !msg.streaming
          "
          class="flex flex-wrap"
          :class="compact ? 'mt-1.5 gap-1.5' : 'mt-2 gap-2'"
        >
          <Button
            v-for="(btn, bi) in msg.actionButtons"
            :key="bi"
            size="small"
            :type="
              btn.style === 'primary'
                ? 'primary'
                : btn.style === 'danger'
                  ? 'default'
                  : 'default'
            "
            :danger="btn.style === 'danger'"
            :disabled="!!msg.actionButtonsUsed"
            :class="compact ? '!text-xs' : ''"
            @click="emit('actionClick', props.index, btn.value)"
          >
            {{ btn.label }}
          </Button>
        </div>

        <!-- Stats + Copy + Regenerate -->
        <div
          v-if="msg.content && !msg.streaming"
          class="flex items-center text-muted-foreground/70 transition-opacity duration-200"
          :class="[
            compact ? 'mt-0.5 gap-0.5 text-[11px]' : 'mt-1 gap-1 text-xs',
            'group-hover:opacity-100',
            compact ? 'opacity-0' : 'opacity-60 hover:opacity-100',
          ]"
        >
          <span v-if="msg.tokenUsage" class="mr-0.5 tabular-nums"
            >{{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}</span
          >
          <span v-if="msg.durationMs" class="mr-0.5 tabular-nums"
            >· {{ (msg.durationMs / 1000).toFixed(1) }}s</span
          >
          <Tooltip
            v-if="msg.memoryUpdated"
            :title="$t('common.globalAiChat.memoryUpdated')"
          >
            <span class="mr-0.5 inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
              <IconifyIcon icon="lucide:brain" class="size-2.5" />
            </span>
          </Tooltip>
          <span class="mx-0.5 text-border">·</span>
          <Tooltip :title="$t('common.globalAiChat.copy')">
            <button
              class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
              :class="compact ? 'size-5' : 'size-5'"
              @click="emit('copy', msg.content)"
            >
              <IconifyIcon icon="lucide:copy" :class="compact ? 'size-2.5' : 'size-3'" />
            </button>
          </Tooltip>
          <Tooltip :title="$t('common.globalAiChat.regenerate')">
            <button
              class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
              :class="compact ? 'size-5' : 'size-5'"
              @click="emit('regenerate', props.index)"
            >
              <IconifyIcon
                icon="lucide:refresh-cw"
                :class="compact ? 'size-2.5' : 'size-3'"
              />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>

    <!-- ===== User message ===== -->
    <div v-else class="group" :class="compact ? 'max-w-[85%]' : 'max-w-[75%]'">
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
            :class="
              compact
                ? 'max-h-32 max-w-40'
                : 'max-h-48 max-w-60 border border-white/20'
            "
            @click="emit('openUrl', att.url)"
          />
          <audio
            v-else-if="att.type === 'audio'"
            controls
            :src="att.url"
            class="max-w-full rounded-lg"
            :class="compact ? 'max-w-48' : 'max-w-64'"
          />
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
          />
          <a
            v-else
            :href="att.url"
            target="_blank"
            class="flex items-center rounded-lg bg-primary-foreground/10 text-primary-foreground hover:bg-primary-foreground/20"
            :class="
              compact
                ? 'gap-1 px-1.5 py-0.5 text-[11px]'
                : 'gap-1.5 px-2 py-1 text-xs'
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
        class="whitespace-pre-wrap rounded-2xl rounded-br-md bg-gradient-to-br from-primary to-primary/85 px-4 py-2.5 text-sm text-primary-foreground shadow-md shadow-primary/15"
      >
        {{ msg.content }}
      </div>
      <!-- User message toolbar (timestamp + copy + edit) -->
      <div class="mt-0.5 flex items-center justify-end gap-0.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
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

<style scoped>
.streaming-cursor::after {
  display: inline;
  font-weight: bold;
  color: hsl(var(--primary));
  content: '▍';
  animation: blink 0.8s step-end infinite;
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

/* Skeleton line pulse animation / 骨架线脉冲动画 */
.skeleton-line {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 0.4;
  }

  50% {
    opacity: 0.8;
  }
}

/* Thinking glow ring / 思考光环 */
.thinking-glow::before {
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  background: radial-gradient(circle, hsl(var(--primary) / 0.2), transparent 70%);
  content: '';
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

/* Typing dots animation / 打字点点动画 */
.typing-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}

.typing-dots span {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: hsl(var(--primary));
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

/* Tool call timeline dot pulse (running state) / 工具调用时间线点脉冲 */
.tc-dot-pulse {
  animation: tc-pulse 1.5s ease-in-out infinite;
  box-shadow: 0 0 0 0 hsl(var(--primary) / 0.4);
}

@keyframes tc-pulse {
  0%,
  100% {
    opacity: 0.6;
    box-shadow: 0 0 0 0 hsl(var(--primary) / 0.4);
  }

  50% {
    opacity: 1;
    box-shadow: 0 0 0 3px hsl(var(--primary) / 0);
  }
}

/* Tool call pill pulse (running status badge) / 工具调用药丸脉冲 */
.tc-pill-pulse {
  animation: tc-pill-glow 2s ease-in-out infinite;
}

@keyframes tc-pill-glow {
  0%,
  100% {
    opacity: 0.7;
  }

  50% {
    opacity: 1;
  }
}
</style>
