import type { MaybeRefOrGetter } from 'vue';

import type {
  AgentItem,
  AgentKnowledgeBaseBindingsByAgentId,
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingsByAgentId,
  AgentSkillBindingSummary,
  ChatMessage,
} from './types';

import type { TurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import { computed, toValue } from 'vue';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';
import { $t } from '#/locales';

export interface AssistantMessageResolvedAgent {
  avatar: null | string;
  description: null | string;
  id: null | number;
  knowledgeBaseIds: null | number[];
  knowledgeBases: AgentKnowledgeBaseBindingSummary[] | null;
  modelName: null | string;
  name: string;
  skills: AgentSkillBindingSummary[] | null;
}

export interface UseAssistantMessageVmOptions {
  agentKnowledgeBaseMap?: MaybeRefOrGetter<
    AgentKnowledgeBaseBindingsByAgentId | null | undefined
  >;
  agentKnowledgeBases?: MaybeRefOrGetter<
    AgentKnowledgeBaseBindingSummary[] | null | undefined
  >;
  agents?: MaybeRefOrGetter<AgentItem[] | undefined>;
  agentSkillMap?: MaybeRefOrGetter<
    AgentSkillBindingsByAgentId | null | undefined
  >;
  kernelState?: MaybeRefOrGetter<null | TurnFlowState | undefined>;
  msg: MaybeRefOrGetter<ChatMessage>;
  selectedAgent?: MaybeRefOrGetter<AgentItem | null | undefined>;
}

export function useAssistantMessageViewModel(
  options: UseAssistantMessageVmOptions,
) {
  const currentAgents = computed(() => toValue(options.agents) ?? []);
  const currentAgentKnowledgeBaseMap = computed(
    () => toValue(options.agentKnowledgeBaseMap) ?? null,
  );
  const currentAgentKnowledgeBases = computed(
    () => toValue(options.agentKnowledgeBases) ?? null,
  );
  const currentAgentSkillMap = computed(
    () => toValue(options.agentSkillMap) ?? null,
  );
  const currentKernelState = computed(
    () => toValue(options.kernelState) ?? null,
  );
  const currentMessage = computed(() => toValue(options.msg));
  const currentSelectedAgent = computed(
    () => toValue(options.selectedAgent) ?? null,
  );

  const resolvedKernelState = computed(
    () => currentKernelState.value ?? buildTurnFlowState(currentMessage.value),
  );

  const hasKernelSections = computed(
    () =>
      resolvedKernelState.value.timeline.length > 0 ||
      Boolean(resolvedKernelState.value.answerCard) ||
      resolvedKernelState.value.selectedEvidence.length > 0 ||
      Boolean(resolvedKernelState.value.pendingAction),
  );

  const hasGeneratedImages = computed(
    () => (currentMessage.value.imageResults?.length ?? 0) > 0,
  );

  const hasActionButtons = computed(
    () =>
      (currentMessage.value.actionButtons?.length ?? 0) > 0 &&
      currentMessage.value.streaming !== true,
  );

  const showFooter = computed(
    () =>
      Boolean(currentMessage.value.content) &&
      currentMessage.value.streaming !== true,
  );

  const hasRichTextDraftCard = computed(() => false);

  const hasPostContentSections = computed(
    () =>
      currentMessage.value.requestFailedRetry === true ||
      hasGeneratedImages.value ||
      hasRichTextDraftCard.value ||
      hasActionButtons.value ||
      showFooter.value,
  );

  const agentFromMessage = computed(() => {
    const messageAgentId = currentMessage.value.agent_id;
    if (typeof messageAgentId !== 'number') {
      return null;
    }
    return (
      currentAgents.value.find((agent) => agent.id === messageAgentId) ?? null
    );
  });

  const fallbackAgent = computed(() =>
    typeof currentMessage.value.agent_id === 'number'
      ? null
      : currentSelectedAgent.value,
  );

  const resolvedAgentSource = computed(
    () => agentFromMessage.value ?? fallbackAgent.value,
  );

  const messageAgentKnowledgeBases = computed(() => {
    const agentId =
      typeof currentMessage.value.agent_id === 'number'
        ? currentMessage.value.agent_id
        : (resolvedAgentSource.value?.id ?? null);
    if (
      agentId === null ||
      !currentAgentKnowledgeBaseMap.value ||
      !Object.prototype.hasOwnProperty.call(
        currentAgentKnowledgeBaseMap.value,
        agentId,
      )
    ) {
      return null;
    }
    return currentAgentKnowledgeBaseMap.value[agentId] ?? null;
  });

  const selectedAgentKnowledgeBases = computed(() => {
    const resolvedAgentId =
      currentMessage.value.agent_id ?? resolvedAgentSource.value?.id ?? null;
    if (
      resolvedAgentId === null ||
      resolvedAgentId !== currentSelectedAgent.value?.id
    ) {
      return null;
    }
    return currentAgentKnowledgeBases.value;
  });

  const messageAgentSkills = computed<AgentSkillBindingSummary[] | null>(() => {
    const agentId =
      typeof currentMessage.value.agent_id === 'number'
        ? currentMessage.value.agent_id
        : (resolvedAgentSource.value?.id ?? null);
    if (
      agentId === null ||
      !currentAgentSkillMap.value ||
      !Object.prototype.hasOwnProperty.call(currentAgentSkillMap.value, agentId)
    ) {
      return null;
    }
    return currentAgentSkillMap.value[agentId] ?? null;
  });

  const selectedAgentSkills = computed<AgentSkillBindingSummary[] | null>(
    () => {
      const resolvedAgentId =
        currentMessage.value.agent_id ?? resolvedAgentSource.value?.id ?? null;
      if (
        resolvedAgentId === null ||
        resolvedAgentId !== currentSelectedAgent.value?.id
      ) {
        return null;
      }
      return currentSelectedAgent.value?.skills ?? null;
    },
  );

  const resolvedMessageAgent = computed<AssistantMessageResolvedAgent>(() => {
    const source = resolvedAgentSource.value;
    return {
      avatar: currentMessage.value.agent_avatar ?? source?.avatar ?? null,
      description:
        currentMessage.value.agent_description ?? source?.description ?? null,
      id: currentMessage.value.agent_id ?? source?.id ?? null,
      knowledgeBaseIds:
        currentMessage.value.agent_knowledge_base_ids ??
        source?.knowledge_base_ids ??
        null,
      knowledgeBases:
        currentMessage.value.agent_knowledge_bases ??
        messageAgentKnowledgeBases.value ??
        source?.knowledge_bases ??
        selectedAgentKnowledgeBases.value ??
        null,
      modelName: currentMessage.value.model_name ?? source?.model_name ?? null,
      name:
        currentMessage.value.agent_name ??
        source?.name ??
        $t('common.globalAiChat.assistant'),
      skills:
        currentMessage.value.agent_skills ??
        messageAgentSkills.value ??
        source?.skills ??
        selectedAgentSkills.value ??
        null,
    };
  });

  return {
    hasActionButtons,
    hasGeneratedImages,
    hasKernelSections,
    hasPostContentSections,
    hasRichTextDraftCard,
    resolvedKernelState,
    resolvedMessageAgent,
    showFooter,
  };
}
