<script lang="ts" setup>
import type {
  AgentKnowledgeBaseBindingSummary,
  AgentSkillBindingSummary,
} from './types';

import ChatMessageAgentAvatar from './ChatMessageAgentAvatar.vue';

withDefaults(
  defineProps<{
    agentAvatar?: null | string;
    agentDescription?: null | string;
    agentId?: null | number;
    agentKnowledgeBaseIds?: null | number[];
    agentKnowledgeBases?: AgentKnowledgeBaseBindingSummary[] | null;
    agentName?: null | string;
    agentSkills?: AgentSkillBindingSummary[] | null;
    compact?: boolean;
    modelName?: null | string;
  }>(),
  {
    agentAvatar: null,
    agentDescription: null,
    agentId: null,
    agentKnowledgeBaseIds: null,
    agentKnowledgeBases: null,
    agentName: null,
    agentSkills: null,
    compact: false,
    modelName: null,
  },
);
</script>

<template>
  <div
    data-testid="agent-identity-rail"
    class="agent-identity-rail"
    :class="
      compact ? 'agent-identity-rail-compact' : 'agent-identity-rail-relaxed'
    "
  >
    <div class="agent-identity-orbit" :class="compact ? 'p-0.5' : 'p-[3px]'">
      <ChatMessageAgentAvatar
        :agent-avatar="agentAvatar"
        :agent-description="agentDescription"
        :agent-id="agentId"
        :agent-knowledge-base-ids="agentKnowledgeBaseIds"
        :agent-knowledge-bases="agentKnowledgeBases"
        :agent-name="agentName"
        :agent-skills="agentSkills"
        :compact="compact"
        :model-name="modelName"
      />
    </div>
  </div>
</template>

<style scoped>
.agent-identity-rail {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  isolation: isolate;
}

.agent-identity-rail::before {
  display: none;
  content: none;
}

.agent-identity-rail::after {
  display: none;
  content: none;
}

.agent-identity-rail-compact::after {
  width: 2.15rem;
  height: 2.15rem;
}

.agent-identity-orbit {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: hsl(var(--background) / 72%);
  border: 1px solid hsl(var(--border) / 16%);
  border-radius: 999px;
  box-shadow: none;
}

.agent-identity-orbit::after {
  display: none;
  content: none;
}
</style>
