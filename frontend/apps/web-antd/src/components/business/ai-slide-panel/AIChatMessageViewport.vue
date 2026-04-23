<script lang="ts" setup>
import type { PendingOpDisplayItem } from './use-pending-page-ops';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import type {
  AgentItem,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from '#/types/ai-chat';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { toTurnFlowFirstChatMessage } from '#/components/business/ai-chat-panel/turn-flow-first-message';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    agents?: AgentItem[];
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
    isAgentSwitch: (index: number) => boolean;
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
    chatMessages: () => [],
    compact: true,
    countdownNow: 0,
    effectiveSuggestedQuestions: () => [],
    effectiveWelcomeMessage: '',
    forceShowDiagnostics: false,
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
    : 'mx-auto min-h-full w-full max-w-[42rem] space-y-4',
);

const transcriptRailClass = computed(() =>
  props.compact
    ? 'w-full space-y-3'
    : 'mx-auto w-full max-w-[42rem] space-y-3',
);

const messageListClass = computed(() =>
  props.compact ? 'space-y-2.5' : 'space-y-3.5',
);
</script>

<template>
  <div
    :ref="(element) => registerContainer?.(element as HTMLDivElement | null)"
    class="flex-1 overflow-y-auto"
    :class="compact ? 'px-3 py-3' : 'px-5 py-5 sm:px-7 lg:px-8'"
    @scroll="emit('scroll')"
  >
    <div :class="contentShellClass">
      <div
        v-if="chatMessages.length === 0 && !sending && !routing"
        class="flex h-full items-center justify-center"
      >
        <div class="ai-chat-empty-card w-full max-w-sm rounded-[22px] border border-border/28 px-5 py-5 text-center">
          <div class="ai-chat-empty-orb mx-auto mb-3 flex size-10 items-center justify-center rounded-2xl text-primary ring-1 ring-primary/12">
            <IconifyIcon icon="lucide:sparkles" class="size-5" />
          </div>
          <div class="text-[13px] font-semibold text-foreground/84">
            {{
              effectiveWelcomeMessage || $t('common.globalAiChat.welcomeDesc')
            }}
          </div>
          <div class="mt-1.5 text-[10px] leading-5 text-muted-foreground/58">
            {{ $t('common.globalAiChat.welcomeFirstTime') }}
          </div>
          <div
            v-if="effectiveSuggestedQuestions.length > 0"
            class="mt-4 flex flex-col gap-1.5"
          >
            <button
              v-for="(question, questionIndex) in effectiveSuggestedQuestions"
              :key="questionIndex"
              class="group/sq flex items-center gap-2 rounded-2xl border border-border/22 bg-background/82 px-3 py-2.5 text-left text-[11px] text-foreground/82 transition-colors hover:border-primary/18 hover:bg-primary/[0.04]"
              @click="emit('askSuggested', question)"
            >
              <IconifyIcon
                icon="lucide:message-circle"
                class="size-3.5 shrink-0 text-primary/58 transition-colors group-hover/sq:text-primary"
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
            :selected-agent="selectedAgent"
            :show-agent-switch="isAgentSwitch(idx)"
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
            class="routing-card relative overflow-hidden rounded-xl border border-border/24 px-3.5 py-2.5 backdrop-blur-sm"
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

    <div class="sticky bottom-2 z-10 flex justify-center gap-2">
      <Transition name="fade">
        <button
          v-if="showScrollToTop && !streaming"
          class="inline-flex size-7 items-center justify-center rounded-full border border-border/38 bg-background/92 text-muted-foreground shadow-[0_10px_24px_-18px_hsl(var(--foreground)/0.24)] backdrop-blur-sm transition-all hover:border-primary/20 hover:bg-primary hover:text-white"
          :aria-label="$t('common.globalAiChat.scrollToTop')"
          @click="emit('scrollToTop')"
        >
          <IconifyIcon icon="lucide:arrow-up" class="size-3.5" />
        </button>
      </Transition>
      <Transition name="fade">
        <button
          v-if="showScrollToBottom && !streaming"
          class="inline-flex size-7 items-center justify-center rounded-full border border-border/38 bg-background/92 text-muted-foreground shadow-[0_10px_24px_-18px_hsl(var(--foreground)/0.24)] backdrop-blur-sm transition-all hover:border-primary/20 hover:bg-primary hover:text-white"
          @click="emit('scrollToBottom')"
        >
          <IconifyIcon icon="lucide:arrow-down" class="size-3.5" />
        </button>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-empty-card {
  background: linear-gradient(
    180deg,
    hsl(var(--card) / 0.96) 0%,
    hsl(var(--background) / 0.98) 100%
  );
  box-shadow: 0 18px 40px -34px hsl(var(--foreground) / 0.18);
}

.ai-chat-empty-orb {
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 0.12) 0%,
    hsl(var(--primary) / 0.06) 100%
  );
}

.routing-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.94) 0%,
    hsl(var(--primary) / 0.045) 100%
  );
}
</style>
