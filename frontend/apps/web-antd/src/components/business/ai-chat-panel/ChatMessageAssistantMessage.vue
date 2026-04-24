<script lang="ts" setup>
import type { PendingPageOpForDisplay } from './pending-page-op';
import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  AgentSkillBindingSummary,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import ChatMessageKernel from '#/components/business/ai-chat-kernel/ChatMessageKernel.vue';
import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import RichTextDraftCard from '#/components/business/ai-chat-panel/RichTextDraftCard.vue';
import { useDiagnosticsPolicy } from '#/composables/use-diagnostics-policy';
import { $t } from '#/locales';

import { shouldRenderTurnDiagnostics } from './chat-message-diagnostics-visibility';
import ChatMessageAgentAvatar from './ChatMessageAgentAvatar.vue';
import ChatMessageContentBlock from './ChatMessageContentBlock.vue';
import ChatMessageDiagnostics from './ChatMessageDiagnostics.vue';
import ChatMessageErrorCard from './ChatMessageErrorCard.vue';
import ChatMessageFooter from './ChatMessageFooter.vue';

const props = withDefaults(
  defineProps<{
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    /** Agents list for resolving avatar/name by msg.agent_id (fix avatar mismatch) / 智能体列表，按 msg.agent_id 解析头像 */
    agents?: AgentItem[];
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
    apiPrefix?: string;
    compact?: boolean;
    /** Current timestamp for 60s countdown display (fallback: local now) / 用于 60s 倒计时的当前时间戳 */
    countdownNow?: number;
    forceShowDiagnostics?: boolean;
    index: number;
    kernelState?: null | TurnFlowState;
    msg: ChatMessage;
    /** Pending page ops for this message (filtered by toolCallId) / 本消息关联的待确认操作 */
    pendingOps?: PendingPageOpForDisplay[];
    richTextState?: null | RichTextDraftRuntimeState;
    selectedAgent?: AgentItem | null;
  }>(),
  {
    apiPrefix: '',
    agents: () => [],
    compact: false,
    countdownNow: undefined,
    forceShowDiagnostics: false,
    agentKnowledgeBases: null,
    agentKnowledgeBaseMap: null,
    agentSkillMap: null,
    kernelState: null,
    selectedAgent: null,
    pendingOps: () => [],
    richTextState: null,
  },
);

const emit = defineEmits<{
  actionClick: [index: number, value: string];
  confirm: [index: number];
  consentConfirm: [index: number];
  consentReject: [index: number];
  copy: [content: string];
  openUrl: [url: string];
  regenerate: [index: number];
  reject: [index: number];
  retry: [index: number];
  richTextApply: [
    index: number,
    target: RichTextAIApplyTarget,
    mode: RichTextAIApplyMode,
  ];
  richTextDiscard: [index: number];
  richTextUndo: [index: number];
}>();
const { showDiagnostics } = useDiagnosticsPolicy({
  apiPrefix: computed(() => props.apiPrefix),
  forceShow: computed(() => props.forceShowDiagnostics),
});
const resolvedKernelState = computed(
  () => props.kernelState ?? buildTurnFlowState(props.msg, props.pendingOps),
);
const showTurnDiagnostics = computed(() =>
  shouldRenderTurnDiagnostics(props.msg, showDiagnostics.value),
);
const hasKernelSections = computed(
  () =>
    resolvedKernelState.value.timeline.length > 0 ||
    Boolean(resolvedKernelState.value.answerCard) ||
    resolvedKernelState.value.selectedEvidence.length > 0 ||
    Boolean(resolvedKernelState.value.pendingAction),
);
const hasGeneratedImages = computed(
  () => (props.msg.imageResults?.length ?? 0) > 0,
);
const hasActionButtons = computed(
  () =>
    (props.msg.actionButtons?.length ?? 0) > 0 && props.msg.streaming !== true,
);
const showFooter = computed(
  () => Boolean(props.msg.content) && props.msg.streaming !== true,
);
const showTopSection = computed(
  () => hasKernelSections.value || showTurnDiagnostics.value,
);
const hasRichTextDraftCard = computed(
  () =>
    props.msg.source === 'rich_text_ai' &&
    Boolean(props.msg.richTextAI) &&
    !props.msg.streaming &&
    !props.richTextState?.discarded,
);
const hasPostContentSections = computed(
  () =>
    props.msg.requestFailedRetry === true ||
    hasGeneratedImages.value ||
    hasRichTextDraftCard.value ||
    hasActionButtons.value ||
    showFooter.value,
);
const agentFromMessage = computed(() => {
  const messageAgentId = props.msg.agent_id;
  if (typeof messageAgentId !== 'number') {
    return null;
  }
  return props.agents.find((agent) => agent.id === messageAgentId) ?? null;
});

const fallbackAgent = computed(() =>
  typeof props.msg.agent_id === 'number' ? null : props.selectedAgent,
);

const resolvedAgentSource = computed(
  () => agentFromMessage.value ?? fallbackAgent.value,
);

const messageAgentKnowledgeBases = computed(() => {
  const agentId =
    typeof props.msg.agent_id === 'number'
      ? props.msg.agent_id
      : (resolvedAgentSource.value?.id ?? null);
  if (
    agentId === null ||
    !props.agentKnowledgeBaseMap ||
    !Object.prototype.hasOwnProperty.call(props.agentKnowledgeBaseMap, agentId)
  ) {
    return null;
  }
  return props.agentKnowledgeBaseMap[agentId] ?? null;
});

const selectedAgentKnowledgeBases = computed(() => {
  const resolvedAgentId =
    props.msg.agent_id ?? resolvedAgentSource.value?.id ?? null;
  if (resolvedAgentId === null || resolvedAgentId !== props.selectedAgent?.id) {
    return null;
  }
  return props.agentKnowledgeBases;
});

const messageAgentSkills = computed<AgentSkillBindingSummary[] | null>(() => {
  const agentId =
    typeof props.msg.agent_id === 'number'
      ? props.msg.agent_id
      : (resolvedAgentSource.value?.id ?? null);
  if (
    agentId === null ||
    !props.agentSkillMap ||
    !Object.prototype.hasOwnProperty.call(props.agentSkillMap, agentId)
  ) {
    return null;
  }
  return props.agentSkillMap[agentId] ?? null;
});

const selectedAgentSkills = computed<AgentSkillBindingSummary[] | null>(() => {
  const resolvedAgentId =
    props.msg.agent_id ?? resolvedAgentSource.value?.id ?? null;
  if (resolvedAgentId === null || resolvedAgentId !== props.selectedAgent?.id) {
    return null;
  }
  return props.selectedAgent?.skills ?? null;
});

const resolvedMessageAgent = computed(() => {
  const source = resolvedAgentSource.value;
  return {
    avatar: props.msg.agent_avatar ?? source?.avatar ?? null,
    description: props.msg.agent_description ?? source?.description ?? null,
    id: props.msg.agent_id ?? source?.id ?? null,
    knowledgeBaseIds:
      props.msg.agent_knowledge_base_ids ?? source?.knowledge_base_ids ?? null,
    knowledgeBases:
      props.msg.agent_knowledge_bases ??
      messageAgentKnowledgeBases.value ??
      source?.knowledge_bases ??
      selectedAgentKnowledgeBases.value ??
      null,
    modelName: props.msg.model_name ?? source?.model_name ?? null,
    name:
      props.msg.agent_name ??
      source?.name ??
      $t('common.globalAiChat.assistant'),
    skills:
      props.msg.agent_skills ??
      messageAgentSkills.value ??
      source?.skills ??
      selectedAgentSkills.value ??
      null,
  };
});

function pickRichTextDraftCopyContent(
  ...values: Array<null | string | undefined>
) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return '';
}

function getRichTextDraftCopyContent(mode: RichTextAIApplyMode) {
  const task = props.msg.richTextAI;
  if (!task) {
    return props.msg.content;
  }
  if (mode === 'plain') {
    return pickRichTextDraftCopyContent(
      task.draft.plainText,
      task.draft.markdown,
      props.msg.content,
      task.draft.html,
    );
  }
  return pickRichTextDraftCopyContent(
    task.draft.markdown,
    task.draft.plainText,
    props.msg.content,
    task.draft.html,
  );
}
</script>

<template>
  <div class="assistant-message-row flex justify-start">
    <div
      class="group/assistant flex min-w-0 items-start"
      :class="
        compact ? 'w-full max-w-full gap-2.5' : 'w-full max-w-[46rem] gap-3'
      "
    >
      <div class="assistant-avatar-rail shrink-0 pt-0.5">
        <ChatMessageAgentAvatar
          :agent-avatar="resolvedMessageAgent.avatar"
          :agent-description="resolvedMessageAgent.description"
          :agent-id="resolvedMessageAgent.id"
          :agent-knowledge-base-ids="resolvedMessageAgent.knowledgeBaseIds"
          :agent-knowledge-bases="resolvedMessageAgent.knowledgeBases"
          :agent-name="resolvedMessageAgent.name"
          :agent-skills="resolvedMessageAgent.skills"
          :compact="compact"
          :model-name="resolvedMessageAgent.modelName"
        />
      </div>

      <div class="assistant-message-column min-w-0 flex-1">
        <div class="assistant-message-surface">
          <div
            v-if="showTopSection"
            class="assistant-message-top border-b border-border/20"
            :class="compact ? 'px-2.5 py-[7px]' : 'px-3 py-[8px]'"
          >
            <ChatMessageKernel
              v-if="hasKernelSections || showTurnDiagnostics"
              :compact="compact"
              :countdown-now="countdownNow"
              :msg="msg"
              :pending-ops="pendingOps"
              :state="resolvedKernelState"
              @copy="(content) => emit('copy', content)"
              @confirm="emit('confirm', props.index)"
              @reject="emit('reject', props.index)"
              @consent-confirm="emit('consentConfirm', props.index)"
              @consent-reject="emit('consentReject', props.index)"
            >
              <template v-if="showTurnDiagnostics" #diagnostics>
                <ChatMessageDiagnostics
                  :api-prefix="apiPrefix"
                  :compact="compact"
                  :force-show="forceShowDiagnostics"
                  :msg="msg"
                />
              </template>
            </ChatMessageKernel>
          </div>

          <div
            class="assistant-message-body"
            :class="compact ? 'px-3 py-3' : 'px-4 py-[15px]'"
          >
            <div class="space-y-2">
              <ChatMessageContentBlock
                :msg="msg"
                :index="index"
                :compact="compact"
              />
              <ChatMessageErrorCard :msg="msg" :compact="compact" />
            </div>

            <div
              v-if="hasPostContentSections"
              class="assistant-message-support space-y-1.5 border-t border-border/24"
              :class="compact ? 'mt-2.5 pt-2.5' : 'mt-2.5 pt-2.5'"
            >
              <div
                v-if="msg.requestFailedRetry"
                class="assistant-inline-panel flex items-center justify-between gap-2 rounded-[16px] border px-2.5 py-2"
                :class="compact ? 'text-[9.5px]' : 'text-[10px]'"
              >
                <span
                  class="text-muted-foreground/78 inline-flex min-w-0 items-center gap-1.5"
                >
                  <IconifyIcon
                    icon="lucide:refresh-ccw"
                    class="text-primary/72 size-3 shrink-0"
                  />
                  <span class="truncate">{{
                    msg.error?.message || $t('shared.common.connectionLost')
                  }}</span>
                </span>
                <Button
                  type="link"
                  size="small"
                  class="!p-0 !text-primary"
                  @click="emit('retry', index)"
                >
                  {{ $t('common.globalAiChat.retry') }}
                </Button>
              </div>

              <div
                v-if="hasGeneratedImages"
                class="flex flex-wrap"
                :class="compact ? 'gap-2' : 'gap-3'"
              >
                <div
                  v-for="(img, ii) in msg.imageResults"
                  :key="ii"
                  class="assistant-inline-media group/img relative overflow-hidden rounded-[16px] border"
                >
                  <img
                    :src="
                      img.isBase64
                        ? `data:image/png;base64,${img.url}`
                        : img.url
                    "
                    :alt="
                      img.revisedPrompt ||
                      $t('common.globalAiChat.generatedImage')
                    "
                    class="cursor-pointer object-cover transition-transform hover:scale-[1.02]"
                    :class="compact ? 'max-h-48 max-w-56' : 'max-h-64 max-w-72'"
                    @click="
                      emit(
                        'openUrl',
                        img.isBase64
                          ? `data:image/png;base64,${img.url}`
                          : img.url,
                      )
                    "
                  />
                  <a
                    :href="
                      img.isBase64
                        ? `data:image/png;base64,${img.url}`
                        : img.url
                    "
                    :download="img.isBase64 ? 'generated-image.png' : undefined"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="bg-black/48 hover:bg-black/68 absolute right-2 top-2 flex size-7 items-center justify-center rounded-full border border-white/20 text-white opacity-0 transition-opacity group-hover/img:opacity-100"
                    :title="$t('common.globalAiChat.downloadImage')"
                  >
                    <IconifyIcon icon="lucide:download" class="size-3.5" />
                  </a>
                  <div
                    v-if="img.revisedPrompt"
                    class="from-black/68 via-black/26 absolute bottom-0 left-0 right-0 bg-gradient-to-t to-transparent px-2.5 pb-2 pt-5 text-white opacity-0 transition-opacity group-hover/img:opacity-100"
                    :class="compact ? 'text-[10px]' : 'text-xs'"
                  >
                    <span class="line-clamp-2">{{ img.revisedPrompt }}</span>
                  </div>
                </div>
              </div>

              <RichTextDraftCard
                v-if="hasRichTextDraftCard"
                :task="msg.richTextAI!"
                :state="richTextState"
                :compact="compact"
                @apply="
                  (target, mode) =>
                    emit('richTextApply', props.index, target, mode)
                "
                @copy="
                  (mode) => emit('copy', getRichTextDraftCopyContent(mode))
                "
                @discard="emit('richTextDiscard', props.index)"
                @undo="emit('richTextUndo', props.index)"
              />

              <div
                v-if="hasActionButtons"
                class="flex flex-wrap"
                :class="compact ? 'gap-1.5' : 'gap-2'"
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
                  :class="
                    compact
                      ? '!rounded-full !text-[11px]'
                      : '!rounded-full !text-[11px]'
                  "
                  @click="emit('actionClick', props.index, btn.value)"
                >
                  {{ btn.label }}
                </Button>
              </div>

              <div
                v-if="showFooter"
                class="assistant-message-footer-wrap pt-0.5"
              >
                <ChatMessageFooter
                  :msg="msg"
                  :index="index"
                  :compact="compact"
                  @copy="(content) => emit('copy', content)"
                  @regenerate="(idx) => emit('regenerate', idx)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.assistant-message-row {
  min-width: 0;
}

.assistant-avatar-rail {
  position: sticky;
  top: 0.45rem;
}

.assistant-message-surface {
  position: relative;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid hsl(var(--border) / 0.12);
  border-radius: 18px;
  background: hsl(var(--card) / 0.985);
  box-shadow: 0 18px 30px -36px hsl(var(--foreground) / 0.11);
}

.assistant-message-top {
  background: hsl(var(--muted) / 0.12);
}

.assistant-message-body {
  background: transparent;
}

.assistant-message-support {
  background: transparent;
}

.assistant-inline-panel,
.assistant-inline-media {
  border-color: hsl(var(--border) / 0.16);
  background: hsl(var(--background) / 0.94);
  box-shadow: 0 10px 16px -28px hsl(var(--foreground) / 0.06);
}

.assistant-message-surface :deep(.chat-message-kernel-shell) {
  border-color: hsl(var(--border) / 0.12);
  border-radius: 12px;
  background: hsl(var(--background) / 0.82);
  box-shadow: none;
}

.assistant-message-surface :deep(.chat-message-kernel-overview) {
  gap: 0.5rem;
}

.assistant-message-surface :deep(.kernel-overview-group) {
  padding: 0.38rem 0.5rem;
  border-color: hsl(var(--border) / 0.12);
  border-radius: 11px;
  background: hsl(var(--background) / 0.74);
}

.assistant-message-surface :deep(.kernel-overview-pill),
.assistant-message-surface :deep(.digest-label),
.assistant-message-surface :deep(.turn-process-pill) {
  border-color: hsl(var(--primary) / 0.14);
  background: hsl(var(--primary) / 0.07);
  color: hsl(var(--primary) / 0.76);
}

.assistant-message-surface :deep(.kernel-overview-copy),
.assistant-message-surface :deep(.digest-summary),
.assistant-message-surface :deep(.digest-section-copy) {
  color: hsl(var(--foreground) / 0.74);
}

.assistant-message-surface :deep(.kernel-overview-count),
.assistant-message-surface :deep(.digest-evidence-count),
.assistant-message-surface :deep(.turn-process-count) {
  border-color: hsl(var(--border) / 0.12);
  background: hsl(var(--muted) / 0.2);
  color: hsl(var(--muted-foreground) / 0.58);
}

.assistant-message-surface :deep(.kernel-overview-chevron),
.assistant-message-surface :deep(.digest-chevron),
.assistant-message-surface :deep(.turn-process-chevron) {
  border-color: hsl(var(--border) / 0.12);
  background: hsl(var(--background) / 0.82);
}

.assistant-message-surface :deep(.turn-digest-toggle),
.assistant-message-surface :deep(.turn-process-toggle) {
  border-color: hsl(var(--border) / 0.1);
  border-radius: 12px;
  background: hsl(var(--background) / 0.68);
}

.assistant-message-surface :deep(.turn-stage-detail-surface) {
  border-color: hsl(var(--border) / 0.1);
  background: hsl(var(--background) / 0.76);
}

.assistant-message-surface :deep(.digest-evidence-chip),
.assistant-message-surface :deep(.digest-evidence-more) {
  border-color: hsl(var(--border) / 0.12);
  background: hsl(var(--background) / 0.74);
}
</style>
