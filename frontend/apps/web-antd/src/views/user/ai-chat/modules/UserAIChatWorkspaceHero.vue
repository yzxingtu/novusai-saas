<script lang="ts" setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import ChatMessageAgentAvatar from '#/components/business/ai-chat-panel/ChatMessageAgentAvatar.vue';
import { $t } from '#/locales';

import { useUserAIChatContext } from './ai-chat-context';

const router = useRouter();
const { showWorkspaceHero, workspaceHighlights, chat, onStartNewChat } =
  useUserAIChatContext();
const { selectedAgent } = chat;

const selectedAgentSkillCount = computed(
  () => selectedAgent.value?.skills?.filter((item) => item.enabled !== false).length ?? 0,
);
const selectedKnowledgeBaseCount = computed(
  () =>
    selectedAgent.value?.knowledge_bases?.filter((item) => item.enabled !== false)
      .length ??
    selectedAgent.value?.knowledge_base_ids?.length ??
    0,
);
const selectedAgentLead = computed(
  () =>
    selectedAgent.value?.description ||
    $t('user.aiChat.workspace.agentSummaryFallback'),
);
</script>

<template>
  <section
    v-if="showWorkspaceHero"
    class="relative overflow-hidden rounded-[24px] border border-border/60 bg-card px-4 py-4 shadow-[0_20px_42px_-36px_hsl(var(--foreground)/0.16)] sm:px-5"
  >
    <div
      class="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-primary/70 to-transparent"
    ></div>
    <div
      class="absolute -right-20 top-0 size-64 rounded-full bg-primary/12 blur-3xl"
    ></div>
    <div
      class="absolute left-0 top-1/2 size-44 -translate-y-1/2 rounded-full bg-sky-500/10 blur-3xl"
    ></div>

    <div
      class="relative grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(320px,0.88fr)]"
    >
      <div class="space-y-3.5">
        <div
          class="inline-flex items-center gap-2 rounded-full border border-primary/18 bg-primary/[0.07] px-2.5 py-0.5 text-[10px] font-medium tracking-[0.08em] text-primary"
        >
          <IconifyIcon icon="lucide:messages-square" class="size-3.5" />
          {{ $t('user.aiChat.workspace.badge') }}
        </div>

        <div>
          <h1
            class="text-[1.55rem] font-semibold tracking-[-0.025em] text-foreground sm:text-[1.9rem]"
          >
            {{ $t('user.aiChat.workspace.title') }}
          </h1>
          <p
            class="mt-2.5 max-w-2xl text-[13px] leading-6 text-muted-foreground sm:text-[13.5px]"
          >
            {{ $t('user.aiChat.workspace.description') }}
          </p>
        </div>

        <div class="flex flex-wrap gap-2.5">
          <button
            class="inline-flex items-center gap-2 rounded-full bg-primary px-3.5 py-2 text-[12px] font-medium text-primary-foreground shadow-[0_14px_24px_-18px_hsl(var(--primary)/0.45)] transition-all hover:translate-y-[-1px] hover:shadow-[0_16px_28px_-18px_hsl(var(--primary)/0.5)]"
            type="button"
            @click="router.push('/agents')"
          >
            {{ $t('user.aiChat.workspace.primaryCta') }}
            <IconifyIcon icon="lucide:arrow-up-right" class="size-3.5" />
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/92 px-3.5 py-2 text-[12px] font-medium text-foreground transition-colors hover:border-primary/22 hover:text-primary"
            type="button"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-3.5" />
            {{ $t('user.aiChat.workspace.secondaryCta') }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border border-transparent px-1.5 py-2 text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            type="button"
            @click="router.push('/help')"
          >
            <IconifyIcon icon="lucide:life-buoy" class="size-3.5" />
            {{ $t('user.aiChat.workspace.helpCta') }}
          </button>
        </div>
      </div>

      <div class="space-y-3">
        <div
          class="rounded-[22px] border border-border/55 bg-background/76 px-3.5 py-3.5 shadow-[0_18px_36px_-34px_hsl(var(--foreground)/0.18)]"
        >
          <div class="flex items-start gap-3">
            <div class="shrink-0">
              <ChatMessageAgentAvatar
                v-if="selectedAgent"
                :agent-avatar="selectedAgent.avatar"
                :agent-description="selectedAgent.description"
                :agent-id="selectedAgent.id"
                :agent-knowledge-base-ids="selectedAgent.knowledge_base_ids"
                :agent-knowledge-bases="selectedAgent.knowledge_bases"
                :agent-name="selectedAgent.name"
                :agent-skills="selectedAgent.skills"
                :model-name="selectedAgent.model_name"
              />
              <span
                v-else
                class="flex size-8 items-center justify-center rounded-2xl border border-border/35 bg-primary/8 text-[11px] font-semibold text-primary"
              >
                AI
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/78"
              >
                {{ $t('user.aiChat.workspace.signals.agent') }}
              </div>
              <p class="mt-1.5 text-[12.5px] leading-6 text-foreground/78">
                {{ selectedAgentLead }}
              </p>

              <div class="mt-2 flex flex-wrap gap-1.5">
                <span
                  class="inline-flex items-center gap-1 rounded-full border border-border/45 bg-card/78 px-2 py-1 text-[10px] text-muted-foreground/78"
                >
                  <IconifyIcon icon="lucide:package" class="size-3 text-primary/75" />
                  {{ $t('common.globalAiChat.skillPackages') }}
                  <strong class="font-semibold text-foreground/82">
                    {{ selectedAgentSkillCount }}
                  </strong>
                </span>
                <span
                  class="inline-flex items-center gap-1 rounded-full border border-border/45 bg-card/78 px-2 py-1 text-[10px] text-muted-foreground/78"
                >
                  <IconifyIcon icon="lucide:book-open" class="size-3 text-primary/75" />
                  {{ $t('common.globalAiChat.mentionSectionKbs') }}
                  <strong class="font-semibold text-foreground/82">
                    {{ selectedKnowledgeBaseCount }}
                  </strong>
                </span>
                <span
                  class="inline-flex items-center gap-1 rounded-full border border-border/45 bg-card/78 px-2 py-1 text-[10px] text-muted-foreground/78"
                >
                  <IconifyIcon icon="lucide:cpu" class="size-3 text-primary/75" />
                  {{
                    selectedAgent?.model_name ||
                    $t('user.aiChat.workspace.noAgentSelected')
                  }}
                </span>
              </div>
            </div>
          </div>

          <div class="mt-3 space-y-2">
            <div
              v-for="signal in workspaceHighlights"
              :key="signal.key"
              class="flex items-start gap-2.5 rounded-[18px] border border-border/45 bg-card/72 px-2.5 py-2"
            >
              <span
                class="mt-0.5 flex size-7.5 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="signal.icon" class="size-3.5" />
              </span>
              <div class="min-w-0 flex-1">
                <div
                  class="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground/76"
                >
                  {{ signal.label }}
                </div>
                <div class="mt-1 text-[12px] font-medium leading-5 text-foreground/84">
                  {{ signal.value }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
