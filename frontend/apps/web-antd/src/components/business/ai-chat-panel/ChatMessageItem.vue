<script lang="ts" setup>
/**
 * Chat Message Item - Renders a single chat message (assistant or user).
 *
 * Supports two visual densities via `compact` prop:
 * - false (default): Full page layout with avatar, Tag status, RAG sources
 * - true: Compact drawer layout with smaller sizes, no avatar/Tag/RAG
 */
import type { AgentItem, ChatMessage } from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Spin, Tooltip } from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';
import { getFileIcon } from '#/utils/file';

const props = withDefaults(
  defineProps<{
    apiPrefix?: string;
    compact?: boolean;
    index: number;
    msg: ChatMessage;
    selectedAgent?: AgentItem | null;
    /** Whether to show an agent-switch separator above this message */
    showAgentSwitch?: boolean;
  }>(),
  { apiPrefix: '', compact: false, selectedAgent: null, showAgentSwitch: false },
);

/** Resolve agent display info: prefer message-level, fallback to selectedAgent */
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
}>();
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

        <!-- Tool calls -->
        <div
          v-if="msg.toolCalls?.length"
          :class="compact ? 'mb-1 space-y-px' : 'mb-1.5 space-y-0.5'"
        >
          <details
            v-for="(tc, tcIdx) in msg.toolCalls"
            :key="tcIdx"
            class="group/tc overflow-hidden border border-border/20 bg-accent/20 [&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
            :class="compact ? 'rounded-md' : 'rounded-lg'"
            :open="tc.status === 'error'"
          >
            <summary
              class="flex cursor-pointer select-none items-center"
              :class="
                compact
                  ? 'gap-1 px-2 py-0.5 text-[11px]'
                  : 'gap-1.5 px-2.5 py-1 text-xs'
              "
            >
              <Spin v-if="tc.status === 'running'" size="small" />
              <IconifyIcon
                v-else
                :icon="
                  tc.status === 'success'
                    ? 'lucide:check-circle'
                    : 'lucide:x-circle'
                "
                class="shrink-0"
                :class="[
                  compact ? 'size-3' : 'size-3.5',
                  tc.status === 'success' ? 'text-green-600' : 'text-red-500',
                ]"
              />
              <span class="flex-1 truncate text-muted-foreground">
                <template v-if="tc.skillName">
                  <span class="font-medium text-foreground/70">{{
                    tc.skillName
                  }}</span>
                  <span class="mx-0.5 text-muted-foreground/40">›</span>
                </template>
                {{ tc.displayName || tc.name }}
                <span
                  v-if="tc.summary && tc.status === 'success'"
                  class="ml-1 text-muted-foreground/60"
                  >— {{ tc.summary }}</span
                >
              </span>
              <span v-if="tc.durationMs" class="text-[10px] text-muted-foreground/50">
                {{ (tc.durationMs / 1000).toFixed(1) }}s
              </span>
              <IconifyIcon
                v-if="tc.status !== 'running'"
                icon="lucide:chevron-down"
                class="shrink-0 text-muted-foreground/40 transition-transform duration-200 group-open/tc:rotate-180"
                :class="compact ? 'size-2.5' : 'size-3'"
              />
            </summary>
            <div
              v-if="tc.output || tc.error || tc.arguments"
              class="border-t border-border/30"
              :class="compact ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-[11px]'"
            >
              <div
                v-if="tc.arguments && Object.keys(tc.arguments).length > 0"
                class="mb-1"
              >
                <span class="font-medium text-muted-foreground/70">{{
                  $t('common.globalAiChat.args')
                }}</span>
                <code
                  class="ml-1 rounded bg-accent/60 px-1 py-px text-[10px] text-muted-foreground"
                >
                  {{ JSON.stringify(tc.arguments) }}
                </code>
              </div>
              <div
                v-if="tc.output"
                class="overflow-y-auto whitespace-pre-wrap break-all rounded bg-accent/40 px-1.5 py-1 text-muted-foreground"
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
          <!-- Generating indicator after tool calls -->
          <div
            v-if="msg.streaming && !msg.content"
            class="flex items-center gap-1.5 px-2 py-0.5 text-muted-foreground"
            :class="compact ? 'text-[11px]' : 'text-xs'"
          >
            <span class="typing-dots"><span /><span /><span /></span>
            <span>{{ $t('common.globalAiChat.generating') }}</span>
          </div>
        </div>

        <!-- Markdown content -->
        <div
          v-if="msg.content"
          class="rounded-2xl border border-border/30 bg-gradient-to-br from-muted/40 to-muted/20 shadow-sm"
          :class="compact ? 'px-2.5 py-1.5 text-sm' : 'px-4 py-3'"
        >
          <MarkdownRender :content="msg.content" :streaming="!!msg.streaming" />
          <span v-if="msg.streaming" class="streaming-cursor"></span>
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
          {{ new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
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

/* Skeleton line pulse animation */
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

/* Thinking glow ring */
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

/* Typing dots animation */
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
</style>
