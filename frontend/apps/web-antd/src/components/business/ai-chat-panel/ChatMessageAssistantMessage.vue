<script lang="ts" setup>
import type { PendingPageOpForDisplay } from './pending-page-op';
import type {
  AgentItem,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import ChatMessageKernel from '#/components/business/ai-chat-kernel/ChatMessageKernel.vue';
import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import RichTextDraftCard from '#/components/business/ai-chat-panel/RichTextDraftCard.vue';
import { $t } from '#/locales';

import ChatMessageContentBlock from './ChatMessageContentBlock.vue';
import ChatMessageDiagnostics from './ChatMessageDiagnostics.vue';
import ChatMessageErrorCard from './ChatMessageErrorCard.vue';
import ChatMessageFooter from './ChatMessageFooter.vue';

const props = withDefaults(
  defineProps<{
    /** Agents list for resolving avatar/name by msg.agent_id (fix avatar mismatch) / 智能体列表，按 msg.agent_id 解析头像 */
    agents?: AgentItem[];
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
    /** Whether to show an agent-switch separator above this message / 是否在本条消息上方显示智能体切换分隔 */
    showAgentSwitch?: boolean;
  }>(),
  {
    apiPrefix: '',
    agents: () => [],
    compact: false,
    countdownNow: undefined,
    forceShowDiagnostics: false,
    kernelState: null,
    selectedAgent: null,
    showAgentSwitch: false,
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

/** Agent resolved by msg.agent_id from agents list (fix avatar mismatch when msg.agent_avatar is null) */
const resolvedAgent = computed(() => {
  if (props.msg.agent_id && props.agents?.length) {
    return props.agents.find((a) => a.id === props.msg.agent_id) ?? null;
  }
  return null;
});

/** Avatar: msg > agents[agent_id] > selectedAgent (avoid wrong agent avatar in history) */
const resolvedAvatar = computed(
  () =>
    props.msg.agent_avatar ??
    resolvedAgent.value?.avatar ??
    props.selectedAgent?.avatar ??
    null,
);
/** Resolve agent display info: prefer message-level, then agents by id, fallback to selectedAgent */
const msgAgentName = computed(
  () =>
    props.msg.agent_name ??
    resolvedAgent.value?.name ??
    props.selectedAgent?.name ??
    null,
);
const msgAgentDescription = computed(
  () =>
    props.msg.agent_description ??
    resolvedAgent.value?.description ??
    props.selectedAgent?.description ??
    null,
);
const msgModelName = computed(
  () =>
    props.msg.model_name ??
    resolvedAgent.value?.model_name ??
    props.selectedAgent?.model_name ??
    null,
);
const isMentionRoute = computed(() => props.msg.routeSource === 'mention');
const showRouteBadge = computed(
  () => !!msgAgentName.value && (props.showAgentSwitch || isMentionRoute.value),
);
const isAdminMode = computed(() => props.apiPrefix.startsWith('/admin'));
const resolvedKernelState = computed(
  () => props.kernelState ?? buildTurnFlowState(props.msg, props.pendingOps),
);
const hasKernelSections = computed(
  () =>
    resolvedKernelState.value.timeline.length > 0 ||
    Boolean(resolvedKernelState.value.answerCard) ||
    resolvedKernelState.value.selectedEvidence.length > 0 ||
    Boolean(resolvedKernelState.value.pendingAction) ||
    isAdminMode.value,
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
const showTopSection = computed(() => hasKernelSections.value);
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
  <!-- Agent switch separator -->
  <div
    v-if="showRouteBadge"
    class="flex items-center gap-2 py-1"
    :class="compact ? 'mb-1' : 'mb-2'"
  >
    <div class="h-px flex-1 bg-border/40"></div>
    <div
      class="flex items-center gap-1 rounded-full bg-muted/60 px-2.5 py-0.5 text-muted-foreground"
      :class="compact ? 'text-[10px]' : 'text-xs'"
    >
      <IconifyIcon
        :icon="isMentionRoute ? 'lucide:at-sign' : 'lucide:arrow-right'"
        class="size-3"
      />
      <span>{{ isMentionRoute ? `@ ${msgAgentName}` : msgAgentName }}</span>
    </div>
    <div class="h-px flex-1 bg-border/40"></div>
  </div>

  <div class="flex justify-start" :class="compact ? 'gap-2' : 'gap-3'">
    <div
      class="group flex min-w-0 items-start"
      :class="compact ? 'max-w-[88%] gap-2' : 'max-w-[70%] gap-3'"
    >
      <!-- Avatar with profile card popover -->
      <AgentProfilePopover
        :agent-id="msg.agent_id ?? selectedAgent?.id"
        :agent-avatar="resolvedAvatar"
        :agent-name="msgAgentName"
        :agent-description="msgAgentDescription"
        :model-name="msgModelName"
        :api-prefix="apiPrefix"
        :size="compact ? 'sm' : 'md'"
      />

      <div class="assistant-message-surface">
        <div
          v-if="showTopSection"
          class="assistant-message-top border-b border-border/45"
          :class="compact ? 'px-3 py-2.5' : 'px-3.5 py-3'"
        >
          <ChatMessageKernel
            v-if="hasKernelSections"
            :admin-mode="isAdminMode"
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
            <template #diagnostics>
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
          :class="compact ? 'px-3 py-2.5' : 'px-3.5 py-3'"
        >
          <div class="space-y-3">
            <ChatMessageContentBlock
              :msg="msg"
              :index="index"
              :compact="compact"
            />
            <ChatMessageErrorCard :msg="msg" :compact="compact" />
          </div>

          <div
            v-if="hasPostContentSections"
            class="assistant-message-support space-y-2.5 border-t border-border/45"
            :class="compact ? 'mt-3 pt-3' : 'mt-3.5 pt-3.5'"
          >
            <div
              v-if="msg.requestFailedRetry"
              class="bg-background/88 flex items-center gap-1.5 rounded-2xl border border-border/45 px-2.5 py-2"
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

            <div
              v-if="hasGeneratedImages"
              class="flex flex-wrap"
              :class="compact ? 'gap-2' : 'gap-3'"
            >
              <div
                v-for="(img, ii) in msg.imageResults"
                :key="ii"
                class="group/img bg-background/92 relative overflow-hidden rounded-2xl border border-border/45"
              >
                <img
                  :src="
                    img.isBase64 ? `data:image/png;base64,${img.url}` : img.url
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
                    img.isBase64 ? `data:image/png;base64,${img.url}` : img.url
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
              @copy="(mode) => emit('copy', getRichTextDraftCopyContent(mode))"
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
                :class="compact ? '!rounded-full !text-xs' : '!rounded-full'"
                @click="emit('actionClick', props.index, btn.value)"
              >
                {{ btn.label }}
              </Button>
            </div>

            <div v-if="showFooter" class="assistant-message-footer-wrap pt-0.5">
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
</template>

<style scoped>
.assistant-message-surface {
  position: relative;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  border: 1px solid hsl(var(--border) / 0.28);
  border-radius: 20px;
  background: linear-gradient(
    180deg,
    hsl(var(--card) / 0.985) 0%,
    hsl(var(--background) / 0.985) 100%
  );
  box-shadow:
    0 18px 38px -34px hsl(var(--foreground) / 0.2),
    0 1px 2px hsl(var(--foreground) / 0.035);
}

.assistant-message-surface::before {
  position: absolute;
  top: 0;
  right: 24%;
  left: 24%;
  height: 1px;
  pointer-events: none;
  content: '';
  background: linear-gradient(
    90deg,
    transparent 0%,
    hsl(var(--primary) / 0.14) 50%,
    transparent 100%
  );
}

.assistant-message-top {
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 0.045) 0%,
    hsl(var(--background) / 0.96) 100%
  );
}

.assistant-message-body {
  background: hsl(var(--background) / 0.985);
}

.assistant-message-support {
  background: linear-gradient(
    180deg,
    transparent 0%,
    hsl(var(--primary) / 0.028) 100%
  );
}
</style>
