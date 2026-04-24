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
    :class="compact ? 'agent-identity-rail-compact' : 'agent-identity-rail-relaxed'"
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
  position: absolute;
  top: calc(100% - 0.1rem);
  bottom: -0.9rem;
  left: 50%;
  width: 1px;
  content: '';
  transform: translateX(-50%);
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 0.16),
    hsl(var(--primary) / 0.02)
  );
  pointer-events: none;
}

.agent-identity-rail::after {
  position: absolute;
  top: 0.15rem;
  left: 50%;
  width: 2.4rem;
  height: 2.4rem;
  content: '';
  transform: translateX(-50%);
  border-radius: 999px;
  background: radial-gradient(
    circle,
    hsl(var(--primary) / 0.14),
    transparent 68%
  );
  filter: blur(8px);
  opacity: 0.9;
  pointer-events: none;
  z-index: -1;
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
  border: 1px solid hsl(var(--border) / 0.14);
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.94),
    hsl(var(--muted) / 0.12)
  );
  box-shadow:
    inset 0 1px 0 hsl(var(--background) / 0.72),
    0 12px 24px -30px hsl(var(--foreground) / 0.14);
}

.agent-identity-orbit::after {
  position: absolute;
  inset: 0.2rem;
  content: '';
  border: 1px solid hsl(var(--primary) / 0.08);
  border-radius: 999px;
  pointer-events: none;
}
</style>
