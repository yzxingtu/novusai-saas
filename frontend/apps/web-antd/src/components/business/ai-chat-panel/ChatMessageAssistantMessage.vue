<script lang="ts" setup>
import type { PendingToolActionForDisplay } from './pending-tool-action';
import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  ChatMessage,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import { computed, toRef } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import ChatMessageKernel from '#/components/business/ai-chat-kernel/ChatMessageKernel.vue';
import { useDiagnosticsPolicy } from '#/composables/use-diagnostics-policy';
import { $t } from '#/locales';

import { shouldRenderTurnDiagnostics } from './chat-message-diagnostics-visibility';
import AgentIdentityRail from './AgentIdentityRail.vue';
import ChatMessageContentBlock from './ChatMessageContentBlock.vue';
import ChatMessageDiagnostics from './ChatMessageDiagnostics.vue';
import ChatMessageErrorCard from './ChatMessageErrorCard.vue';
import ChatMessageFooter from './ChatMessageFooter.vue';
import { useAssistantMessageViewModel } from './use-assistant-message-vm';

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
    /** Pending tool actions for this message (filtered by toolCallId) / 本消息关联的待确认工具动作 */
    pendingOps?: PendingToolActionForDisplay[];
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
}>();
const { showDiagnostics } = useDiagnosticsPolicy({
  apiPrefix: computed(() => props.apiPrefix),
  forceShow: computed(() => props.forceShowDiagnostics),
});
const {
  hasActionButtons,
  hasGeneratedImages,
  hasKernelSections,
  hasPostContentSections,
  resolvedKernelState,
  resolvedMessageAgent,
  showFooter,
} = useAssistantMessageViewModel({
  agentKnowledgeBaseMap: toRef(props, 'agentKnowledgeBaseMap'),
  agentKnowledgeBases: toRef(props, 'agentKnowledgeBases'),
  agents: toRef(props, 'agents'),
  agentSkillMap: toRef(props, 'agentSkillMap'),
  kernelState: toRef(props, 'kernelState'),
  msg: toRef(props, 'msg'),
  pendingOps: toRef(props, 'pendingOps'),
  selectedAgent: toRef(props, 'selectedAgent'),
});
const showTurnDiagnostics = computed(() =>
  shouldRenderTurnDiagnostics(props.msg, showDiagnostics.value),
);
const showKernelSection = computed(
  () => hasKernelSections.value || showTurnDiagnostics.value,
);

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
        <AgentIdentityRail
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
            class="assistant-message-body"
            :class="compact ? 'px-3 py-3' : 'px-4 py-4'"
          >
            <div class="space-y-2.5">
              <ChatMessageKernel
                v-if="showKernelSection"
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

              <ChatMessageContentBlock
                :msg="msg"
                :index="index"
                :compact="compact"
              />
              <ChatMessageErrorCard :msg="msg" :compact="compact" />
            </div>

            <div
              v-if="hasPostContentSections"
              class="assistant-message-support border-border/24 space-y-1.5 border-t"
              :class="compact ? 'mt-3 pt-2.5' : 'mt-3.5 pt-3'"
            >
              <div
                v-if="msg.requestFailedRetry"
                class="assistant-inline-panel flex items-center gap-2 rounded-[16px] border px-2.5 py-2"
                :class="msg.error ? 'justify-end' : 'justify-between'"
              >
                <span
                  v-if="!msg.error"
                  class="text-muted-foreground/78 inline-flex min-w-0 items-center gap-1.5"
                  :class="compact ? 'text-[9.5px]' : 'text-[10px]'"
                >
                  <IconifyIcon
                    icon="lucide:refresh-ccw"
                    class="text-primary/72 size-3 shrink-0"
                  />
                  <span class="truncate">{{
                    $t('shared.common.connectionLost')
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
  border: 1px solid hsl(var(--border) / 0.1);
  border-radius: 20px;
  background:
    radial-gradient(
      circle at top left,
      hsl(var(--primary) / 0.1),
      transparent 22%
    ),
    radial-gradient(
      circle at bottom right,
      hsl(var(--primary) / 0.05),
      transparent 24%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.996) 0%,
      hsl(var(--background) / 0.985) 100%
    );
  box-shadow:
    0 24px 48px -44px hsl(var(--foreground) / 0.18),
    0 10px 24px -26px hsl(var(--foreground) / 0.08);
}

.assistant-message-surface::before {
  position: absolute;
  top: 0;
  left: 1.25rem;
  right: 1.25rem;
  height: 1px;
  content: '';
  background: linear-gradient(
    90deg,
    transparent,
    hsl(var(--primary) / 0.62),
    transparent
  );
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
  box-shadow: 0 12px 22px -32px hsl(var(--foreground) / 0.1);
}

.assistant-message-surface :deep(.chat-message-kernel-shell) {
  border-color: hsl(var(--border) / 0.08);
  border-radius: 16px;
  background: hsl(var(--background) / 0.72);
  box-shadow: inset 0 1px 0 hsl(var(--background) / 0.52);
}
</style>
