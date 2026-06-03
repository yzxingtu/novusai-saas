import type { ChatKBBindingInfo } from '#/api/shared/ai-chat';
import type { AgentItem, ConversationItem } from '#/types/ai-chat';

import { computed, ref } from 'vue';

import {
  getChatAgentKBBindingsApi,
  getChatAgentsApi,
  getGlobalConversationsApi,
} from '#/api/shared/ai-chat';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';
import { toAvatarDisplayUrl } from '#/utils/image';

const USER_API_PREFIX = '/api/user';

export interface UserPortalAgentSkill {
  id: number;
  name: string;
}

export interface UserPortalAgent extends AgentItem {
  created_at?: null | string;
  execution_mode?: null | string;
  owner_type?: null | string;
  published_version?: null | number;
  scope?: null | string;
  skills?: UserPortalAgentSkill[];
  updated_at?: null | string;
}

export interface AgentKnowledgeSignal {
  bindings: ChatKBBindingInfo[];
  count: number;
  hasKnowledge: boolean;
}

export interface LoadWorkspaceOptions {
  agentPageSize?: number;
  conversationPageSize?: number;
}

function normalizePortalAgent(agent: UserPortalAgent): UserPortalAgent {
  return {
    ...agent,
    avatar: agent.avatar ? toAvatarDisplayUrl(agent.avatar) : null,
    description: agent.description ?? null,
    input_variables: Array.isArray(agent.input_variables)
      ? agent.input_variables
      : [],
    suggested_questions: Array.isArray(agent.suggested_questions)
      ? agent.suggested_questions
      : [],
    skills: Array.isArray(agent.skills) ? agent.skills : [],
    welcome_message: agent.welcome_message ?? null,
  };
}

function scoreAgent(
  agent: UserPortalAgent,
  recentConversationAgentIds: Set<number>,
): number {
  let score = 0;

  if (recentConversationAgentIds.has(agent.id)) {
    score += 40;
  }
  if (agent.model_capabilities?.supports_vision) {
    score += 12;
  }
  if (normalizeStarterQuestions(agent.suggested_questions).length > 0) {
    score += 10;
  }
  if (agent.welcome_message) {
    score += 4;
  }
  if (agent.owner_type === 'tenant') {
    score += 3;
  }
  if ((agent.skills?.length ?? 0) > 0) {
    score += Math.min(agent.skills?.length ?? 0, 4);
  }

  const createdAt = agent.created_at ? new Date(agent.created_at).getTime() : 0;
  if (Number.isFinite(createdAt) && createdAt > 0) {
    score += createdAt / 1_000_000_000_000;
  }

  return score;
}

export function useUserPortalWorkspace() {
  const agents = ref<UserPortalAgent[]>([]);
  const conversations = ref<ConversationItem[]>([]);
  const agentsLoading = ref(false);
  const conversationsLoading = ref(false);
  const knowledgeSignals = ref<Record<number, AgentKnowledgeSignal>>({});

  const knowledgeRequestingIds = new Set<number>();

  const loading = computed(
    () => agentsLoading.value || conversationsLoading.value,
  );

  const recentConversationAgentIds = computed(() => {
    return new Set(
      conversations.value
        .map((conversation) => conversation.agent_id)
        .filter((agentId): agentId is number => typeof agentId === 'number'),
    );
  });

  const recommendedAgents = computed(() => {
    return [...agents.value]
      .toSorted(
        (left, right) =>
          scoreAgent(right, recentConversationAgentIds.value) -
          scoreAgent(left, recentConversationAgentIds.value),
      )
      .slice(0, 6);
  });

  const stats = computed(() => {
    const visionReadyAgents = agents.value.filter(
      (agent) => agent.model_capabilities?.supports_vision,
    ).length;
    const starterReadyAgents = agents.value.filter(
      (agent) =>
        normalizeStarterQuestions(agent.suggested_questions).length > 0,
    ).length;

    return {
      accessibleAgents: agents.value.length,
      recentConversations: conversations.value.length,
      starterReadyAgents,
      visionReadyAgents,
    };
  });

  async function loadWorkspace(
    options: LoadWorkspaceOptions = {},
  ): Promise<void> {
    const { agentPageSize = 100, conversationPageSize = 20 } = options;

    agentsLoading.value = true;
    conversationsLoading.value = true;

    const [agentsResult, conversationsResult] = await Promise.allSettled([
      getChatAgentsApi<UserPortalAgent>(USER_API_PREFIX),
      getGlobalConversationsApi<ConversationItem>(
        USER_API_PREFIX,
        conversationPageSize,
      ),
    ]);

    if (agentsResult.status === 'fulfilled') {
      agents.value = agentsResult.value.items
        .slice(0, agentPageSize)
        .map((agent) => normalizePortalAgent(agent));
    }
    if (conversationsResult.status === 'fulfilled') {
      conversations.value = conversationsResult.value.items;
    }

    agentsLoading.value = false;
    conversationsLoading.value = false;
  }

  async function ensureKnowledgeSignals(agentIds: number[]): Promise<void> {
    const targetIds = [...new Set(agentIds)].filter(
      (agentId) =>
        agentId > 0 &&
        knowledgeSignals.value[agentId] === undefined &&
        !knowledgeRequestingIds.has(agentId),
    );

    if (targetIds.length === 0) {
      return;
    }

    targetIds.forEach((agentId) => knowledgeRequestingIds.add(agentId));

    const results = await Promise.allSettled(
      targetIds.map(async (agentId) => {
        const bindings = await getChatAgentKBBindingsApi(
          USER_API_PREFIX,
          agentId,
        );
        return { agentId, bindings };
      }),
    );

    const nextSignals = { ...knowledgeSignals.value };

    results.forEach((result, index) => {
      const agentId = targetIds[index];
      if (!agentId) {
        return;
      }

      nextSignals[agentId] =
        result.status === 'fulfilled'
          ? {
              bindings: result.value.bindings,
              count: result.value.bindings.length,
              hasKnowledge: result.value.bindings.length > 0,
            }
          : {
              bindings: [],
              count: 0,
              hasKnowledge: false,
            };

      knowledgeRequestingIds.delete(agentId);
    });

    knowledgeSignals.value = nextSignals;
  }

  return {
    agents,
    agentsLoading,
    conversations,
    conversationsLoading,
    ensureKnowledgeSignals,
    knowledgeSignals,
    loadWorkspace,
    loading,
    recommendedAgents,
    recentConversationAgentIds,
    stats,
  };
}
