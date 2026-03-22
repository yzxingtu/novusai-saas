<script setup lang="ts">
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';
import { normalizeStarterQuestions } from '#/utils/ai-starter-questions';

import type { UserPortalAgent } from './portal-data';

interface PortalAgentCardProps {
  agent: UserPortalAgent;
  hasKnowledge?: boolean;
  knowledgeCount?: number;
  lastUsedLabel?: string;
  questionLimit?: number;
}

const props = withDefaults(defineProps<PortalAgentCardProps>(), {
  hasKnowledge: false,
  knowledgeCount: 0,
  lastUsedLabel: '',
  questionLimit: 2,
});

const emit = defineEmits<{
  chat: [agent: UserPortalAgent];
  question: [payload: { agent: UserPortalAgent; question: string }];
}>();

const starterQuestions = computed(() => {
  return normalizeStarterQuestions(props.agent.suggested_questions).slice(
    0,
    props.questionLimit,
  );
});

const signalTags = computed(() => {
  const tags: Array<{
    icon: string;
    key: string;
    label: string;
    tone: string;
  }> = [];

  if (props.agent.model_capabilities?.supports_vision) {
    tags.push({
      icon: 'lucide:image-plus',
      key: 'vision',
      label: $t('user.portal.badges.vision'),
      tone: 'bg-sky-500/10 text-sky-700 dark:text-sky-300',
    });
  }
  if (props.hasKnowledge) {
    tags.push({
      icon: 'lucide:book-open',
      key: 'knowledge',
      label: $t('user.portal.badges.knowledge', {
        count: props.knowledgeCount,
      }),
      tone: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    });
  }
  if (props.agent.execution_mode === 'workflow') {
    tags.push({
      icon: 'lucide:route',
      key: 'workflow',
      label: $t('user.portal.badges.workflow'),
      tone: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
    });
  }
  if (props.agent.owner_type === 'tenant') {
    tags.push({
      icon: 'lucide:building-2',
      key: 'tenant',
      label: $t('user.portal.badges.tenant'),
      tone: 'bg-primary/10 text-primary',
    });
  } else {
    tags.push({
      icon: 'lucide:globe-2',
      key: 'platform',
      label: $t('user.portal.badges.platform'),
      tone: 'bg-muted text-muted-foreground',
    });
  }

  return tags.slice(0, 4);
});

function emitQuestion(question: string) {
  emit('question', { agent: props.agent, question });
}
</script>

<template>
  <article
    class="group relative overflow-hidden rounded-[24px] border border-border/70 bg-card/95 p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
  >
    <div class="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
    <div class="absolute -right-14 top-2 size-28 rounded-full bg-primary/8 blur-2xl transition-all duration-300 group-hover:bg-primary/15" />

    <div class="relative flex items-start justify-between gap-4">
      <div class="flex min-w-0 items-center gap-3">
        <div
          class="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-sm font-semibold text-primary ring-1 ring-primary/10"
        >
          <img
            v-if="agent.avatar"
            :src="agent.avatar"
            :alt="agent.name"
            class="size-12 rounded-2xl object-cover"
          />
          <span v-else>{{ agent.name.charAt(0).toUpperCase() }}</span>
        </div>
        <div class="min-w-0">
          <div class="truncate text-base font-semibold text-foreground">
            {{ agent.name }}
          </div>
          <div class="mt-1 flex flex-wrap gap-1.5">
            <span
              v-for="tag in signalTags"
              :key="tag.key"
              class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium"
              :class="tag.tone"
            >
              <IconifyIcon :icon="tag.icon" class="size-3" />
              {{ tag.label }}
            </span>
          </div>
        </div>
      </div>

      <span
        v-if="lastUsedLabel"
        class="rounded-full border border-border/70 bg-background/90 px-2 py-1 text-[11px] text-muted-foreground"
      >
        {{ lastUsedLabel }}
      </span>
    </div>

    <p class="relative mt-4 line-clamp-2 min-h-[2.75rem] text-sm leading-6 text-muted-foreground">
      {{ agent.description || $t('user.portal.agentFallbackDescription') }}
    </p>

    <div
      v-if="starterQuestions.length > 0"
      class="relative mt-4 space-y-2 rounded-2xl border border-border/60 bg-background/70 p-3"
    >
      <div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <IconifyIcon icon="lucide:sparkles" class="size-3.5 text-primary" />
        {{ $t('user.portal.recommendedQuestions') }}
      </div>
      <button
        v-for="question in starterQuestions"
        :key="question"
        class="flex w-full items-center gap-2 rounded-xl border border-transparent bg-accent/60 px-3 py-2 text-left text-xs text-foreground transition-all hover:border-primary/20 hover:bg-primary/5"
        type="button"
        @click="emitQuestion(question)"
      >
        <IconifyIcon icon="lucide:message-circle-more" class="size-3.5 shrink-0 text-primary" />
        <span class="line-clamp-2">{{ question }}</span>
      </button>
    </div>

    <div class="relative mt-5 flex items-center justify-between gap-3">
      <div class="text-xs text-muted-foreground">
        {{
          agent.model_name
            ? $t('user.portal.agentModelLabel', { model: agent.model_name })
            : $t('user.portal.agentReady')
        }}
      </div>
      <button
        class="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
        type="button"
        @click="emit('chat', agent)"
      >
        {{ $t('user.portal.openAgent') }}
        <IconifyIcon icon="lucide:arrow-up-right" class="size-4" />
      </button>
    </div>
  </article>
</template>
