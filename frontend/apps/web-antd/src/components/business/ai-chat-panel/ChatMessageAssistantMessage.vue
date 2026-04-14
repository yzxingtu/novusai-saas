<script lang="ts" setup>
import type {
  AgentItem,
  ChatMessage,
  RichTextAIApplyMode,
  RichTextAIApplyTarget,
  RichTextDraftRuntimeState,
} from './types';
import type { PendingPageOpForDisplay } from './pending-page-op';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { Button } from 'ant-design-vue';

import { AgentProfilePopover } from '#/components/business/agent-profile-popover';
import RichTextDraftCard from '#/components/business/ai-chat-panel/RichTextDraftCard.vue';
import { $t } from '#/locales';

import ChatMessageContentBlock from './ChatMessageContentBlock.vue';
import ChatMessageDiagnostics from './ChatMessageDiagnostics.vue';
import ChatMessageErrorCard from './ChatMessageErrorCard.vue';
import ChatMessageFooter from './ChatMessageFooter.vue';
import ChatMessagePendingConsentCard from './ChatMessagePendingConsentCard.vue';
import ChatMessageRagSources from './ChatMessageRagSources.vue';
import ChatMessageThinkingBlock from './ChatMessageThinkingBlock.vue';
import ChatMessageToolCalls from './ChatMessageToolCalls.vue';

const props = withDefaults(
  defineProps<{
    /** Agents list for resolving avatar/name by msg.agent_id (fix avatar mismatch) / 智能体列表，按 msg.agent_id 解析头像 */
    agents?: AgentItem[];
    apiPrefix?: string;
    compact?: boolean;
    /** Current timestamp for 60s countdown display (fallback: local now) / 用于 60s 倒计时的当前时间戳 */
    countdownNow?: number;
    index: number;
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
      class="group flex"
      :class="compact ? 'max-w-[90%] gap-1.5' : 'max-w-[80%] gap-2'"
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

      <div class="min-w-0">
        <!-- Agent name + model label -->
        <div v-if="msgAgentName && msg.agent_id" :class="compact ? 'mb-0.5' : 'mb-1'">
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

        <ChatMessageThinkingBlock :msg="msg" :index="index" :compact="compact" />

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

        <ChatMessageErrorCard :msg="msg" :compact="compact" />
        <ChatMessageDiagnostics :msg="msg" :compact="compact" />
        <ChatMessageContentBlock :msg="msg" :index="index" :compact="compact" />

        <!-- SSE error retry -->
        <div
          v-if="msg.requestFailedRetry"
          class="mt-1 flex items-center gap-1.5"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          <Button type="link" size="small" class="!p-0 !text-primary" @click="emit('retry', index)">
            {{ $t('common.globalAiChat.retry') }}
          </Button>
        </div>

        <ChatMessageToolCalls
          v-if="msg.toolCalls?.length"
          :msg="msg"
          :index="index"
          :compact="compact"
          :pending-ops="pendingOps"
          :countdown-now="countdownNow"
          @copy="(content) => emit('copy', content)"
        />

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
              :alt="img.revisedPrompt || $t('common.globalAiChat.generatedImage')"
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
              :href="img.isBase64 ? `data:image/png;base64,${img.url}` : img.url"
              :download="img.isBase64 ? 'generated-image.png' : undefined"
              target="_blank"
              rel="noopener noreferrer"
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

        <RichTextDraftCard
          v-if="
            msg.source === 'rich_text_ai' &&
            msg.richTextAI &&
            !msg.streaming &&
            !richTextState?.discarded
          "
          :task="msg.richTextAI"
          :state="richTextState"
          :compact="compact"
          @apply="(target, mode) => emit('richTextApply', props.index, target, mode)"
          @copy="(mode) => emit('copy', getRichTextDraftCopyContent(mode))"
          @discard="emit('richTextDiscard', props.index)"
          @undo="emit('richTextUndo', props.index)"
        />

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
                <td class="whitespace-nowrap py-0.5 pr-3 font-medium text-foreground/70">
                  {{ key }}
                </td>
                <td class="break-all py-0.5 text-muted-foreground">
                  {{ typeof val === 'object' ? JSON.stringify(val) : val }}
                </td>
              </tr>
            </table>
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
            <IconifyIcon
              icon="lucide:check-circle"
              class="mr-1 inline text-success"
              :class="compact ? 'size-3' : 'size-3.5'"
            />
            {{ $t('common.globalAiChat.confirmationResolved') }}
          </div>
        </div>

        <ChatMessagePendingConsentCard
          :msg="msg"
          :compact="compact"
          @consent-confirm="emit('consentConfirm', props.index)"
          @consent-reject="emit('consentReject', props.index)"
        />

        <ChatMessageRagSources :msg="msg" :compact="compact" />

        <!-- Action Buttons -->
        <div
          v-if="msg.actionButtons && msg.actionButtons.length > 0 && !msg.streaming"
          class="flex flex-wrap"
          :class="compact ? 'mt-1.5 gap-1.5' : 'mt-2 gap-2'"
        >
          <Button
            v-for="(btn, bi) in msg.actionButtons"
            :key="bi"
            size="small"
            :type="
              btn.style === 'primary' ? 'primary' : btn.style === 'danger' ? 'default' : 'default'
            "
            :danger="btn.style === 'danger'"
            :disabled="!!msg.actionButtonsUsed"
            :class="compact ? '!text-xs' : ''"
            @click="emit('actionClick', props.index, btn.value)"
          >
            {{ btn.label }}
          </Button>
        </div>

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
</template>
