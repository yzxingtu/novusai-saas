<script lang="ts" setup>
import type { PendingOpDisplayItem } from './use-pending-page-ops';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import type {
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  AgentItem,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from '#/types/ai-chat';

import { computed, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { toTurnFlowFirstChatMessage } from '#/components/business/ai-chat-panel/turn-flow-first-message';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    agents?: AgentItem[];
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
    apiPrefix: string;
    chatMessages?: ChatMessage[];
    compact?: boolean;
    countdownNow?: number;
    effectiveSuggestedQuestions?: string[];
    effectiveWelcomeMessage?: string;
    forceShowDiagnostics?: boolean;
    getPendingOpsForMessage: (msg: ChatMessage) => PendingOpDisplayItem[];
    getRichTextDraftState: (
      message: ChatMessage,
    ) => null | RichTextDraftRuntimeState;
    ensureAgentKnowledgeBases?: (agentId: number) => Promise<unknown> | void;
    ensureAgentSkills?: (agentId: number) => Promise<unknown> | void;
    registerContainer?: (element: HTMLDivElement | null) => void;
    routing?: boolean;
    selectedAgent?: AgentItem | null;
    sending?: boolean;
    showScrollToBottom?: boolean;
    showScrollToTop?: boolean;
    streaming?: boolean;
    unassociatedPendingOps?: PendingOpDisplayItem[];
  }>(),
  {
    agents: () => [],
    agentKnowledgeBases: null,
    agentKnowledgeBaseMap: null,
    agentSkillMap: null,
    chatMessages: () => [],
    compact: true,
    countdownNow: 0,
    effectiveSuggestedQuestions: () => [],
    effectiveWelcomeMessage: '',
    forceShowDiagnostics: false,
    ensureAgentKnowledgeBases: undefined,
    ensureAgentSkills: undefined,
    routing: false,
    registerContainer: undefined,
    selectedAgent: null,
    sending: false,
    showScrollToBottom: false,
    showScrollToTop: false,
    streaming: false,
    unassociatedPendingOps: () => [],
  },
);

const emit = defineEmits<{
  (e: 'actionClick', index: number, value: string): void;
  (e: 'askSuggested', question: string): void;
  (e: 'confirm', index: number): void;
  (e: 'consentConfirm', index: number): void;
  (e: 'consentReject', index: number): void;
  (e: 'copy', content: string): void;
  (e: 'edit', index: number): void;
  (e: 'openUrl', url: string): void;
  (e: 'regenerate', index: number): void;
  (e: 'reject', index: number): void;
  (e: 'resolvePendingOp', invokeId: string, allowed: boolean): void;
  (e: 'retry', index: number): void;
  (
    e: 'richTextApply',
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ): void;
  (e: 'richTextDiscard', index: number): void;
  (e: 'richTextUndo', index: number): void;
  (e: 'scroll'): void;
  (e: 'scrollToBottom'): void;
  (e: 'scrollToTop'): void;
}>();

function normalizeIdentityPart(value: unknown): string | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function hashIdentityParts(parts: string[]): string {
  let hash = 2_166_136_261;
  const joined = parts.join('\u001F');
  for (let index = 0; index < joined.length; index += 1) {
    hash ^= joined.codePointAt(index) ?? 0;
    hash = Math.imul(hash, 16_777_619);
  }
  return (hash >>> 0).toString(36);
}

function resolveMessageRenderKey(message: ChatMessage): string {
  const messageRecord = message as unknown as Record<string, unknown>;
  const persistedIdentity = [
    messageRecord.message_id,
    messageRecord.messageId,
    messageRecord.id,
  ]
    .map((value) => normalizeIdentityPart(value))
    .find(Boolean);
  if (persistedIdentity) {
    return `persisted:${persistedIdentity}`;
  }
  const normalizedClientKey = normalizeIdentityPart(message.clientKey);
  if (normalizedClientKey) {
    return `client:${normalizedClientKey}`;
  }
  return `fallback:${hashIdentityParts([
    message.role,
    normalizeIdentityPart(messageRecord.sequence) ?? '',
    normalizeIdentityPart(message.created_at) ?? '',
  ])}`;
}

const normalizedChatMessages = computed(() =>
  props.chatMessages.map((message) => {
    const normalized = toTurnFlowFirstChatMessage(message);
    if (props.streaming) {
      return normalized;
    }
    return {
      ...normalized,
      streaming: false,
    } satisfies ChatMessage;
  }),
);

const messageRenderEntries = computed(() =>
  normalizedChatMessages.value.map((message) => {
    const pendingOps = props.getPendingOpsForMessage(message);
    return {
      kernelState: buildTurnFlowState(message, pendingOps) as TurnFlowState,
      key: resolveMessageRenderKey(message),
      message,
      pendingOps,
    };
  }),
);

const contentShellClass = computed(() =>
  props.compact
    ? 'w-full space-y-3'
    : 'mx-auto min-h-full w-full max-w-[48rem] space-y-4.5',
);

const transcriptRailClass = computed(() =>
  props.compact ? 'w-full space-y-3' : 'mx-auto w-full max-w-[48rem] space-y-3.5',
);

const messageListClass = computed(() =>
  props.compact ? 'space-y-2.5' : 'space-y-4',
);

const visibleAssistantAgentIds = computed(() => {
  const ids = new Set<number>();
  for (const message of normalizedChatMessages.value) {
    if (
      message.role !== 'assistant' ||
      typeof message.agent_id !== 'number' ||
      !Number.isFinite(message.agent_id)
    ) {
      continue;
    }
    ids.add(message.agent_id);
  }
  return [...ids];
});

function hasKnowledgeBaseSource(agentId: number): boolean {
  if (
    props.agentKnowledgeBaseMap &&
    Object.prototype.hasOwnProperty.call(props.agentKnowledgeBaseMap, agentId)
  ) {
    return true;
  }
  if (
    props.selectedAgent?.id === agentId &&
    Array.isArray(props.agentKnowledgeBases)
  ) {
    return true;
  }
  const agent = props.agents.find((item) => item.id === agentId);
  return (
    Array.isArray(agent?.knowledge_bases) ||
    Array.isArray(agent?.knowledge_base_ids)
  );
}

function hasSkillSource(agentId: number): boolean {
  if (
    props.agentSkillMap &&
    Object.prototype.hasOwnProperty.call(props.agentSkillMap, agentId)
  ) {
    return true;
  }
  if (
    props.selectedAgent?.id === agentId &&
    Array.isArray(props.selectedAgent.skills)
  ) {
    return true;
  }
  const messageHasSkills = normalizedChatMessages.value.some(
    (message) =>
      message.role === 'assistant' &&
      message.agent_id === agentId &&
      Array.isArray(message.agent_skills),
  );
  if (messageHasSkills) {
    return true;
  }
  const agent = props.agents.find((item) => item.id === agentId);
  return Array.isArray(agent?.skills);
}

watch(
  visibleAssistantAgentIds,
  (agentIds) => {
    for (const agentId of agentIds) {
      if (!hasKnowledgeBaseSource(agentId)) {
        void props.ensureAgentKnowledgeBases?.(agentId);
      }
      if (hasSkillSource(agentId)) {
        continue;
      }
      void props.ensureAgentSkills?.(agentId);
    }
  },
  { immediate: true },
);
</script>

<template>
  <div
    :ref="(element) => registerContainer?.(element as HTMLDivElement | null)"
    class="flex-1 overflow-y-auto"
    :class="compact ? 'px-3 py-3' : 'px-4 py-4 sm:px-6 lg:px-8'"
    @scroll="emit('scroll')"
  >
    <div :class="contentShellClass">
      <div
        v-if="chatMessages.length === 0 && !sending && !routing"
        class="flex h-full items-center justify-center"
      >
        <div
          class="ai-chat-empty-card w-full max-w-sm rounded-[28px] border px-6 py-6 text-center"
        >
          <div
            class="ai-chat-empty-orb mx-auto mb-3 flex size-11 items-center justify-center rounded-[20px] text-primary ring-1"
          >
            <IconifyIcon icon="lucide:message-square-text" class="size-5" />
          </div>
          <div
            class="text-foreground/84 text-[12px] font-semibold tracking-[0.01em]"
          >
            {{
              effectiveWelcomeMessage || $t('common.globalAiChat.welcomeDesc')
            }}
          </div>
          <div class="text-muted-foreground/58 mt-1.5 text-[9.75px] leading-5">
            {{ $t('common.globalAiChat.welcomeFirstTime') }}
          </div>
          <div
            v-if="effectiveSuggestedQuestions.length > 0"
            class="mt-4 flex flex-col gap-1.5"
          >
            <button
              v-for="(question, questionIndex) in effectiveSuggestedQuestions"
              :key="questionIndex"
              class="group/sq border-border/18 bg-background/84 text-foreground/82 hover:border-primary/18 flex items-center gap-2 rounded-[18px] border px-3 py-2.5 text-left text-[10.5px] transition-colors hover:bg-primary/[0.04]"
              @click="emit('askSuggested', question)"
            >
              <IconifyIcon
                icon="lucide:message-circle"
                class="text-primary/58 size-3.5 shrink-0 transition-colors group-hover/sq:text-primary"
              />
              <span class="truncate">{{ question }}</span>
              <IconifyIcon
                icon="lucide:arrow-right"
                class="ml-auto size-3 shrink-0 text-muted-foreground/30 transition-transform group-hover/sq:translate-x-0.5 group-hover/sq:text-primary/60"
              />
            </button>
          </div>
        </div>
      </div>

      <div :class="transcriptRailClass">
        <div class="w-full" :class="messageListClass">
          <ChatMessageItem
            v-for="(entry, idx) in messageRenderEntries"
            :key="entry.key"
            :msg="entry.message"
            :index="idx"
            :api-prefix="apiPrefix"
            :agents="agents"
            :agent-knowledge-bases="agentKnowledgeBases"
            :agent-knowledge-base-map="agentKnowledgeBaseMap"
            :agent-skill-map="agentSkillMap"
            :selected-agent="selectedAgent"
            :pending-ops="entry.pendingOps"
            :kernel-state="entry.kernelState"
            :countdown-now="countdownNow"
            :force-show-diagnostics="forceShowDiagnostics"
            :rich-text-state="getRichTextDraftState(entry.message)"
            :compact="compact"
            @copy="emit('copy', $event)"
            @confirm="emit('confirm', $event)"
            @reject="emit('reject', $event)"
            @consent-confirm="emit('consentConfirm', $event)"
            @consent-reject="emit('consentReject', $event)"
            @open-url="emit('openUrl', $event)"
            @action-click="
              (messageIndex, value) => emit('actionClick', messageIndex, value)
            "
            @regenerate="emit('regenerate', $event)"
            @edit="emit('edit', $event)"
            @retry="emit('retry', $event)"
            @rich-text-apply="
              (index, target, mode) =>
                emit('richTextApply', index, target, mode)
            "
            @rich-text-discard="emit('richTextDiscard', $event)"
            @rich-text-undo="emit('richTextUndo', $event)"
          />
        </div>

        <div
          v-for="op in unassociatedPendingOps"
          :key="op.invokeId"
          class="overflow-hidden rounded-lg border"
          :class="
            op.resolved
              ? 'border-border/20 bg-accent/10'
              : 'border-warning/30 bg-warning/5'
          "
        >
          <div
            v-if="op.resolved"
            class="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px]"
          >
            <IconifyIcon
              :icon="op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'"
              class="size-3 shrink-0"
              :class="op.allowed ? 'text-green-600' : 'text-red-500'"
            />
            <span class="truncate text-muted-foreground">
              <span class="font-medium text-foreground/60">{{
                op.operationLabel
              }}</span>
              <span
                v-if="op.operationDescription"
                class="ml-1 text-muted-foreground/60"
                >{{ op.operationDescription }}</span
              >
            </span>
            <span
              class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
              :class="
                op.allowed
                  ? 'bg-green-50 text-green-600 dark:bg-green-950/30'
                  : 'bg-red-50 text-red-600 dark:bg-red-950/30'
              "
            >
              {{
                op.allowed
                  ? $t('shared.pageOperation.confirmOk')
                  : $t('shared.pageOperation.confirmCancel')
              }}
            </span>
          </div>

          <template v-else>
            <div class="flex items-center gap-1.5 px-2.5 py-1.5">
              <IconifyIcon
                icon="lucide:shield-alert"
                class="size-3.5 shrink-0 text-warning"
              />
              <div class="min-w-0 flex-1">
                <div
                  class="truncate text-[11px] font-medium text-foreground/80"
                >
                  {{ op.operationLabel }}
                </div>
                <div
                  v-if="op.operationDescription"
                  class="truncate text-[10px] text-muted-foreground/60"
                >
                  {{ op.operationDescription }}
                </div>
                <div class="mt-0.5 text-[10px] text-muted-foreground/50">
                  {{
                    $t('shared.pageOperation.confirmCountdown', {
                      seconds: Math.max(
                        0,
                        60 -
                          Math.floor(
                            (countdownNow - (op.startedAt || 0)) / 1000,
                          ),
                      ),
                    })
                  }}
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <button
                  class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                  @click="emit('resolvePendingOp', op.invokeId, true)"
                >
                  <IconifyIcon icon="lucide:check" class="size-3" />
                  {{ $t('shared.pageOperation.confirmOk') }}
                </button>
                <button
                  class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                  @click="emit('resolvePendingOp', op.invokeId, false)"
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
              <summary
                class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
              >
                <IconifyIcon icon="lucide:code" class="size-2.5" />
                {{ $t('common.globalAiChat.args') }}
                <IconifyIcon
                  icon="lucide:chevron-down"
                  class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180"
                />
              </summary>
              <div class="border-t border-border/20 px-2.5 py-1">
                <pre
                  class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
                  >{{ JSON.stringify(op.params, null, 2) }}</pre
                >
              </div>
            </details>
          </template>
        </div>

        <Transition name="fade">
          <div
            v-if="routing"
            class="routing-card border-border/24 relative overflow-hidden rounded-xl border px-3.5 py-2.5 backdrop-blur-sm"
          >
            <div class="relative z-[1] flex items-center gap-2.5">
              <div
                class="relative flex size-6 items-center justify-center rounded-lg bg-primary/10"
              >
                <IconifyIcon
                  icon="lucide:route"
                  class="size-3.5 text-primary"
                />
                <span
                  class="routing-dot absolute -right-0.5 -top-0.5 size-2 rounded-full bg-primary"
                ></span>
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="text-xs font-medium text-foreground/80">
                  {{ $t('common.globalAiChat.routingAgent') }}
                </span>
                <div class="flex items-center gap-1">
                  <span
                    class="routing-dot size-1 rounded-full bg-primary/60"
                  ></span>
                  <span
                    class="routing-dot size-1 rounded-full bg-primary/60"
                    style="animation-delay: 0.15s"
                  ></span>
                  <span
                    class="routing-dot size-1 rounded-full bg-primary/60"
                    style="animation-delay: 0.3s"
                  ></span>
                </div>
              </div>
            </div>
            <div class="routing-shimmer absolute inset-0"></div>
          </div>
        </Transition>
      </div>
    </div>

    <div
      class="pointer-events-none sticky bottom-3 z-10 ml-auto mt-3 flex w-fit flex-col items-end gap-1.5 pr-1"
    >
      <Transition name="fade">
        <button
          v-if="showScrollToTop && !streaming"
          type="button"
          class="pointer-events-auto inline-flex size-9 items-center justify-center rounded-2xl border border-border/34 bg-background/96 text-muted-foreground shadow-[0_14px_28px_-22px_hsl(var(--foreground)/0.16)] backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-primary/22 hover:bg-background hover:text-foreground"
          :aria-label="$t('common.globalAiChat.scrollToTop')"
          @click="emit('scrollToTop')"
        >
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            class="size-4"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.6"
          >
            <path d="M8 12V4" />
            <path d="M4.75 7.25 8 4l3.25 3.25" />
          </svg>
        </button>
      </Transition>
      <Transition name="fade">
        <button
          v-if="showScrollToBottom && !streaming"
          type="button"
          class="pointer-events-auto inline-flex size-9 items-center justify-center rounded-2xl border border-border/34 bg-background/96 text-muted-foreground shadow-[0_14px_28px_-22px_hsl(var(--foreground)/0.16)] backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-primary/22 hover:bg-background hover:text-foreground"
          :aria-label="$t('common.globalAiChat.scrollToBottom')"
          @click="emit('scrollToBottom')"
        >
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            class="size-4"
            fill="none"
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.6"
          >
            <path d="M8 4v8" />
            <path d="M4.75 8.75 8 12l3.25-3.25" />
          </svg>
        </button>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-empty-card {
  background: linear-gradient(
    180deg,
    hsl(var(--card)) 0%,
    hsl(var(--background) / 0.98) 100%
  );
  border-color: hsl(var(--border) / 0.32);
  box-shadow: 0 20px 34px -32px hsl(var(--foreground) / 0.14);
}

.ai-chat-empty-orb {
  background: linear-gradient(
    180deg,
    hsl(var(--background)) 0%,
    hsl(var(--muted) / 0.42) 100%
  );
  border-color: hsl(var(--border) / 0.32);
  box-shadow: 0 14px 24px -24px hsl(var(--foreground) / 0.1);
}

.routing-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.98) 0%,
    hsl(var(--muted) / 0.2) 100%
  );
}
</style>
