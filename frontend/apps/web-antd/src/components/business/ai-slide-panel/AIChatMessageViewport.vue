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
    ? 'mx-auto flex min-h-full w-full max-w-[46rem] flex-col gap-2.5'
    : 'mx-auto flex min-h-full w-full max-w-[46rem] flex-col gap-3',
);

const transcriptRailClass = computed(() =>
  props.compact
    ? 'mx-auto w-full max-w-[46rem] space-y-2'
    : 'mx-auto w-full max-w-[46rem] space-y-3',
);

const messageListClass = computed(() =>
  props.compact ? 'space-y-2' : 'space-y-3',
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
    class="transcript-scroll flex-1 overflow-y-auto"
    :class="
      compact
        ? 'px-2 py-2 sm:px-2.5 sm:py-2.5'
        : 'px-3 py-3 sm:px-4 sm:py-3.5 lg:px-5 lg:py-4'
    "
    @scroll="emit('scroll')"
  >
    <div :class="contentShellClass">
      <div
        v-if="chatMessages.length === 0 && !sending && !routing"
        class="flex justify-center pt-2 sm:pt-3"
      >
        <div
          class="ai-chat-empty-card w-full max-w-[21.5rem] rounded-[22px] border px-3.5 py-3.5 text-left"
        >
          <div class="flex items-start gap-3">
            <div
              class="ai-chat-empty-orb flex size-9 shrink-0 items-center justify-center rounded-[15px] text-primary ring-1"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="border-primary/14 text-primary/84 inline-flex items-center rounded-full border bg-primary/[0.06] px-2 py-0.5 text-[8.5px] font-semibold uppercase tracking-[0.14em]"
              >
                {{ $t('common.globalAiChat.turnAnswerCardTitle') }}
              </div>
              <div
                class="text-foreground/84 mt-2 text-[10px] font-semibold leading-5"
              >
                {{
                  effectiveWelcomeMessage ||
                  $t('common.globalAiChat.welcomeDesc')
                }}
              </div>
              <div
                class="text-muted-foreground/54 mt-1 text-[8.75px] leading-4"
              >
                {{ $t('common.globalAiChat.welcomeFirstTime') }}
              </div>
            </div>
          </div>
          <div
            v-if="effectiveSuggestedQuestions.length > 0"
            class="mt-3 grid gap-1.5"
          >
            <button
              v-for="(question, questionIndex) in effectiveSuggestedQuestions"
              :key="questionIndex"
              class="group/sq border-border/14 bg-background/76 flex items-center gap-2 rounded-[14px] border px-2.5 py-1.5 text-left text-[9px] text-foreground/80 transition-colors hover:border-primary/20 hover:bg-primary/[0.04]"
              @click="emit('askSuggested', question)"
            >
              <IconifyIcon
                icon="lucide:message-circle"
                class="text-primary/58 size-3 shrink-0 transition-colors group-hover/sq:text-primary"
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
          class="overflow-hidden rounded-[14px] border"
          :class="
            op.resolved
              ? 'border-border/20 bg-accent/10'
              : 'border-warning/30 bg-warning/5'
          "
        >
          <div
            v-if="op.resolved"
            class="flex items-center gap-1.5 px-2.5 py-1.5 text-[10.5px]"
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
                class="size-3 shrink-0 text-warning"
              />
              <div class="min-w-0 flex-1">
                <div
                  class="truncate text-[10.5px] font-medium text-foreground/80"
                >
                  {{ op.operationLabel }}
                </div>
                <div
                  v-if="op.operationDescription"
                  class="truncate text-[9.5px] text-muted-foreground/60"
                >
                  {{ op.operationDescription }}
                </div>
                <div class="mt-0.5 text-[9.5px] text-muted-foreground/50">
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
                  class="inline-flex items-center gap-0.5 rounded-full bg-primary px-2 py-0.5 text-[10px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                  @click="emit('resolvePendingOp', op.invokeId, true)"
                >
                  <IconifyIcon icon="lucide:check" class="size-3" />
                  {{ $t('shared.pageOperation.confirmOk') }}
                </button>
                <button
                  class="inline-flex items-center gap-0.5 rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                  @click="emit('resolvePendingOp', op.invokeId, false)"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                  {{ $t('shared.pageOperation.confirmCancel') }}
                </button>
              </div>
            </div>
          </template>
        </div>

        <Transition name="fade">
          <div
            v-if="routing"
            class="routing-card border-border/18 relative overflow-hidden rounded-[14px] border px-2.5 py-1.5 backdrop-blur-sm"
          >
            <div class="relative z-[1] flex items-center gap-2">
              <div
                class="flex size-5 items-center justify-center rounded-[12px] bg-primary/10"
              >
                <IconifyIcon icon="lucide:route" class="size-3 text-primary" />
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="text-[9.75px] font-medium text-foreground/80">
                  {{ $t('common.globalAiChat.routingAgent') }}
                </span>
                <span class="text-muted-foreground/62 text-[9px]">
                  {{ $t('common.globalAiChat.turnStageStatus.running') }}
                </span>
              </div>
            </div>
            <div class="routing-shimmer absolute inset-0"></div>
          </div>
        </Transition>
      </div>
    </div>

    <div
      class="pointer-events-none sticky bottom-2.5 z-10 ml-auto mt-2.5 flex w-fit flex-col items-end gap-1.5 pr-1"
    >
      <Transition name="fade">
        <button
          v-if="showScrollToTop && !streaming"
          type="button"
          class="bg-background/94 hover:border-primary/22 pointer-events-auto inline-flex size-7 items-center justify-center rounded-[16px] border border-border/30 text-muted-foreground shadow-[0_12px_24px_-22px_hsl(var(--foreground)/0.16)] backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:bg-background hover:text-foreground"
          :aria-label="$t('common.globalAiChat.scrollToTop')"
          @click="emit('scrollToTop')"
        >
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            class="size-3.5"
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
          class="bg-background/94 hover:border-primary/22 pointer-events-auto inline-flex size-7 items-center justify-center rounded-[16px] border border-border/30 text-muted-foreground shadow-[0_12px_24px_-22px_hsl(var(--foreground)/0.16)] backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:bg-background hover:text-foreground"
          :aria-label="$t('common.globalAiChat.scrollToBottom')"
          @click="emit('scrollToBottom')"
        >
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            class="size-3.5"
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
.transcript-scroll {
  background:
    radial-gradient(
      circle at top,
      hsl(var(--primary) / 0.024),
      transparent 24%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.985) 0%,
      hsl(var(--background)) 100%
    );
}

.ai-chat-empty-card {
  background: linear-gradient(
    180deg,
    hsl(var(--card) / 0.975) 0%,
    hsl(var(--background) / 0.985) 100%
  );
  border-color: hsl(var(--border) / 0.2);
  box-shadow:
    0 18px 30px -34px hsl(var(--foreground) / 0.1),
    0 1px 0 hsl(var(--primary) / 0.04) inset;
}

.ai-chat-empty-orb {
  background: linear-gradient(
    180deg,
    hsl(var(--background)) 0%,
    hsl(var(--muted) / 0.24) 100%
  );
  border-color: hsl(var(--border) / 0.22);
  box-shadow: 0 10px 18px -24px hsl(var(--foreground) / 0.08);
}

.routing-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.98) 0%,
    hsl(var(--primary) / 0.024) 100%
  );
  box-shadow: 0 12px 22px -28px hsl(var(--foreground) / 0.1);
}
</style>
