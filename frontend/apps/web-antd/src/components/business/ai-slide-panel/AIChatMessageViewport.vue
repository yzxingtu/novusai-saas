<script lang="ts" setup>
import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  ChatMessage,
} from '#/types/ai-chat';

import { computed, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin } from 'ant-design-vue';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import ChatMessageItem from '#/components/business/ai-chat-panel/ChatMessageItem.vue';
import { toTurnFlowFirstChatMessage } from '#/components/business/ai-chat-panel/turn-flow-first-message';
import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agents?: AgentItem[];
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
    apiPrefix: string;
    chatMessages?: ChatMessage[];
    compact?: boolean;
    effectiveSuggestedQuestions?: string[];
    effectiveWelcomeMessage?: string;
    ensureAgentKnowledgeBases?: (agentId: number) => Promise<unknown> | void;
    ensureAgentSkills?: (agentId: number) => Promise<unknown> | void;
    forceShowDiagnostics?: boolean;
    registerContainer?: (element: HTMLDivElement | null) => void;
    routing?: boolean;
    selectedAgent?: AgentItem | null;
    sending?: boolean;
    showScrollToBottom?: boolean;
    showScrollToTop?: boolean;
    streaming?: boolean;
    welcomeLoading?: boolean;
    welcomeLoadingHint?: string;
  }>(),
  {
    agents: () => [],
    agentKnowledgeBases: null,
    agentKnowledgeBaseMap: null,
    agentSkillMap: null,
    chatMessages: () => [],
    compact: true,
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
    welcomeLoading: false,
    welcomeLoadingHint: '',
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
  (e: 'retry', index: number): void;
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
    return {
      kernelState: buildTurnFlowState(message) as TurnFlowState,
      key: resolveMessageRenderKey(message),
      message,
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

const emptyStateTitle = computed(() => {
  const agentName = props.selectedAgent?.name?.trim();
  if (agentName) {
    return $t('common.globalAiChat.welcomeAgentReady', { agent: agentName });
  }
  return $t('common.globalAiChat.welcomeReady');
});

const emptyStateDescription = computed(
  () =>
    props.effectiveWelcomeMessage ||
    $t('common.globalAiChat.welcomeEmptyDescription'),
);

const visibleSuggestedQuestions = computed(() =>
  props.effectiveSuggestedQuestions.slice(0, 4),
);

const welcomeLoadingVisible = computed(
  () =>
    props.welcomeLoading &&
    props.chatMessages.length === 0 &&
    !props.sending &&
    !props.routing,
);

const welcomeLoadingAgentName = computed(() => {
  const agentName = props.selectedAgent?.name?.trim();
  return agentName || $t('common.globalAiChat.assistant');
});

const welcomeLoadingHintText = computed(() => {
  if (props.welcomeLoadingHint.trim()) {
    return props.welcomeLoadingHint.trim();
  }
  const agentName = props.selectedAgent?.name?.trim();
  if (agentName) {
    return $t('common.globalAiChat.welcomeLoadingWithAgent', {
      agent: agentName,
    });
  }
  return $t('common.globalAiChat.welcomeLoading');
});

const welcomeLoadingAvatarUrl = computed(() =>
  props.selectedAgent?.avatar
    ? toAvatarDisplayUrl(props.selectedAgent.avatar)
    : '',
);

const welcomeLoadingAvatarText = computed(() => {
  const firstChar = welcomeLoadingAgentName.value.trim().charAt(0);
  return firstChar || 'AI';
});

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
    class="transcript-scroll relative flex-1 overflow-y-auto"
    :class="
      compact
        ? 'px-2 py-2 sm:px-2.5 sm:py-2.5'
        : 'px-3 py-3 sm:px-4 sm:py-3.5 lg:px-5 lg:py-4'
    "
    :aria-busy="welcomeLoadingVisible ? 'true' : 'false'"
    @scroll="emit('scroll')"
  >
    <Transition name="fade">
      <div
        v-if="welcomeLoadingVisible"
        data-testid="ai-chat-welcome-loading"
        role="status"
        aria-live="polite"
        class="absolute inset-0 z-20 flex items-center justify-center bg-background/95 px-4 py-8 backdrop-blur-[2px]"
      >
        <div
          class="flex w-full max-w-[22rem] flex-col items-center text-center"
        >
          <div
            class="ai-chat-welcome-loading-avatar flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-xl text-sm font-semibold text-primary"
          >
            <img
              v-if="welcomeLoadingAvatarUrl"
              :src="welcomeLoadingAvatarUrl"
              :alt="
                $t('common.globalAiChat.welcomeLoadingAvatarAlt', {
                  agent: welcomeLoadingAgentName,
                })
              "
              class="size-full object-cover"
            />
            <span v-else aria-hidden="true">
              {{ welcomeLoadingAvatarText }}
            </span>
          </div>
          <div
            class="mt-3 w-full truncate text-[14px] font-semibold leading-5 text-foreground"
            :title="welcomeLoadingAgentName"
          >
            {{ welcomeLoadingAgentName }}
          </div>
          <p
            class="text-muted-foreground/72 mt-1.5 line-clamp-2 w-full break-words text-[12.5px] leading-5"
          >
            {{ welcomeLoadingHintText }}
          </p>
          <Spin class="mt-3" size="small" />
        </div>
      </div>
    </Transition>

    <div :class="contentShellClass">
      <div
        v-if="
          chatMessages.length === 0 &&
          !sending &&
          !routing &&
          !welcomeLoadingVisible
        "
        class="flex justify-center pt-7 sm:pt-9"
      >
        <div class="ai-chat-empty-state w-full max-w-[27rem] px-3 text-left">
          <div class="flex items-start gap-3.5">
            <div
              class="ai-chat-empty-mark flex size-8 shrink-0 items-center justify-center rounded-lg text-primary"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="text-[15px] font-semibold leading-6 text-foreground">
                {{ emptyStateTitle }}
              </div>
              <p
                class="text-muted-foreground/72 mt-1.5 line-clamp-3 text-[12.5px] leading-5"
              >
                {{ emptyStateDescription }}
              </p>
            </div>
          </div>
          <div
            v-if="visibleSuggestedQuestions.length > 0"
            class="mt-5 grid gap-2 sm:grid-cols-2"
          >
            <button
              v-for="(question, questionIndex) in visibleSuggestedQuestions"
              :key="questionIndex"
              class="ai-chat-empty-question group/sq text-foreground/82 hover:border-primary/24 flex min-h-9 items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-[12px] transition-colors hover:bg-primary/[0.035]"
              @click="emit('askSuggested', question)"
            >
              <IconifyIcon
                icon="lucide:message-circle"
                class="text-primary/62 size-3.5 shrink-0 transition-colors group-hover/sq:text-primary"
              />
              <span class="truncate">{{ question }}</span>
              <IconifyIcon
                icon="lucide:arrow-right"
                class="text-muted-foreground/32 group-hover/sq:text-primary/66 ml-auto size-3.5 shrink-0 transition-transform group-hover/sq:translate-x-0.5"
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
            :kernel-state="entry.kernelState"
            :force-show-diagnostics="forceShowDiagnostics"
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
          />
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
  background: hsl(var(--background));
}

.ai-chat-empty-state {
  color: hsl(var(--foreground));
}

.ai-chat-empty-mark {
  background: hsl(var(--primary) / 7.5%);
  border: 1px solid hsl(var(--primary) / 12%);
}

.ai-chat-empty-question {
  background: hsl(var(--background) / 82%);
  border-color: hsl(var(--border) / 24%);
  box-shadow: 0 8px 20px -24px hsl(var(--foreground) / 16%);
}

.ai-chat-welcome-loading-avatar {
  background: hsl(var(--primary) / 7.5%);
  border: 1px solid hsl(var(--primary) / 12%);
  box-shadow: 0 12px 28px -24px hsl(var(--foreground) / 18%);
}

.routing-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 98%) 0%,
    hsl(var(--primary) / 2.4%) 100%
  );
  box-shadow: 0 12px 22px -28px hsl(var(--foreground) / 10%);
}
</style>
