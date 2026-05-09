<script lang="ts" setup>
import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  ChatMessage,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import ChatMessageAssistantMessage from './ChatMessageAssistantMessage.vue';
import ChatMessageUserMessage from './ChatMessageUserMessage.vue';

const props = withDefaults(
  defineProps<{
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    /** Agents list for resolving avatar/name by msg.agent_id (fix avatar mismatch) / 智能体列表，按 msg.agent_id 解析头像 */
    agents?: AgentItem[];
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
    apiPrefix?: string;
    compact?: boolean;
    forceShowDiagnostics?: boolean;
    index: number;
    kernelState?: null | TurnFlowState;
    msg: ChatMessage;
    selectedAgent?: AgentItem | null;
  }>(),
  {
    apiPrefix: '',
    agents: () => [],
    compact: false,
    forceShowDiagnostics: false,
    agentKnowledgeBases: null,
    agentKnowledgeBaseMap: null,
    agentSkillMap: null,
    kernelState: null,
    selectedAgent: null,
  },
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

const forwardAssistantListeners = {
  actionClick: (index: number, value: string) =>
    emit('actionClick', index, value),
  confirm: (index: number) => emit('confirm', index),
  consentConfirm: (index: number) => emit('consentConfirm', index),
  consentReject: (index: number) => emit('consentReject', index),
  copy: (content: string) => emit('copy', content),
  openUrl: (url: string) => emit('openUrl', url),
  regenerate: (index: number) => emit('regenerate', index),
  reject: (index: number) => emit('reject', index),
  retry: (index: number) => emit('retry', index),
};

const forwardUserListeners = {
  copy: (content: string) => emit('copy', content),
  edit: (index: number) => emit('edit', index),
  openUrl: (url: string) => emit('openUrl', url),
};
</script>

<template>
  <ChatMessageAssistantMessage
    v-if="msg.role === 'assistant'"
    v-bind="props"
    v-on="forwardAssistantListeners"
  />
  <ChatMessageUserMessage
    v-else
    :msg="msg"
    :index="index"
    :compact="compact"
    v-on="forwardUserListeners"
  />
</template>

<style scoped>
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0;
  }
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

@keyframes tc-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 hsl(var(--primary) / 40%);
    opacity: 0.6;
  }

  50% {
    box-shadow: 0 0 0 3px hsl(var(--primary) / 0%);
    opacity: 1;
  }
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

:deep(.streaming-cursor)::after {
  display: inline;
  font-weight: bold;
  color: hsl(var(--primary));
  content: '▍';
  animation: blink 0.8s step-end infinite;
}

/* Skeleton line pulse animation / 骨架线脉冲动画 */
:deep(.skeleton-line) {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

/* Thinking glow ring / 思考光环 */
:deep(.thinking-glow)::before {
  position: absolute;
  inset: -2px;
  content: '';
  background: radial-gradient(
    circle,
    hsl(var(--primary) / 20%),
    transparent 70%
  );
  border-radius: 50%;
  animation: glow-pulse 2s ease-in-out infinite;
}

:deep(.thinking-chip) {
  width: fit-content;
  background: hsl(var(--muted) / 8%);
  border: 1px solid hsl(var(--border) / 16%);
  border-radius: 12px;
  box-shadow: none;
}

:deep(.thinking-chip-icon) {
  background: hsl(var(--primary) / 8%);
}

:deep(.thinking-status-dots span) {
  width: 3px;
  height: 3px;
}

:deep(.thinking-sheet-card) {
  position: relative;
  background: hsl(var(--muted) / 8%);
  border: 1px solid hsl(var(--border) / 12%);
  border-radius: 10px;
  box-shadow: none;
}

:deep(.thinking-sheet-card)::before {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 0;
  width: 2px;
  content: '';
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 36%),
    hsl(var(--primary) / 0%)
  );
  border-radius: 999px;
}

:deep(.tool-call-inline) {
  border-bottom: 1px dashed hsl(var(--border) / 18%);
}

:deep(.tool-call-inline:last-child) {
  border-bottom: none;
}

:deep(.thinking-markdown p + p) {
  margin-top: 0.65rem;
}

:deep(.thinking-markdown pre) {
  margin: 0.75rem 0;
}

/* Typing dots animation / 打字点点动画 */
:deep(.typing-dots) {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}

:deep(.typing-dots span) {
  display: inline-block;
  width: 4px;
  height: 4px;
  background-color: hsl(var(--primary));
  border-radius: 50%;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

:deep(.typing-dots span:nth-child(2)) {
  animation-delay: 0.2s;
}

:deep(.typing-dots span:nth-child(3)) {
  animation-delay: 0.4s;
}

/* Tool call timeline dot pulse (running state) / 工具调用时间线点脉冲 */
:deep(.tc-dot-pulse) {
  box-shadow: 0 0 0 0 hsl(var(--primary) / 40%);
  animation: tc-pulse 1.5s ease-in-out infinite;
}

/* Tool call pill pulse (running status badge) / 工具调用药丸脉冲 */
:deep(.tc-pill-pulse) {
  animation: tc-pill-glow 2s ease-in-out infinite;
}
</style>
