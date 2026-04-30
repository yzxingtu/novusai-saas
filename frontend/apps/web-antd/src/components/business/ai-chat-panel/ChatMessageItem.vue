<script lang="ts" setup>
import type {
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  AgentItem,
  ChatMessage,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import ChatMessageItemShell from './ChatMessageItemShell.vue';

defineOptions({ name: 'ChatMessageItem' });

const props = withDefaults(
  defineProps<{
    agents?: AgentItem[];
    apiPrefix?: string;
    compact?: boolean;
    forceShowDiagnostics?: boolean;
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agentKnowledgeBaseMap?: AgentKnowledgeBaseBindingsByAgentId | null;
    agentSkillMap?: AgentSkillBindingsByAgentId | null;
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

const forwardListeners = {
  actionClick: (index: number, value: string) =>
    emit('actionClick', index, value),
  confirm: (index: number) => emit('confirm', index),
  consentConfirm: (index: number) => emit('consentConfirm', index),
  consentReject: (index: number) => emit('consentReject', index),
  copy: (content: string) => emit('copy', content),
  edit: (index: number) => emit('edit', index),
  openUrl: (url: string) => emit('openUrl', url),
  regenerate: (index: number) => emit('regenerate', index),
  reject: (index: number) => emit('reject', index),
  retry: (index: number) => emit('retry', index),
};
</script>

<template>
  <ChatMessageItemShell v-bind="props" v-on="forwardListeners" />
</template>
