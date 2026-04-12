<script lang="ts" setup>
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

import { useUserAIChatContext } from './ai-chat-context';

const router = useRouter();
const { showWorkspaceHero, workspaceHighlights, chat, onStartNewChat } =
  useUserAIChatContext();
const { selectedAgent } = chat;
</script>

<template>
  <section
    v-if="showWorkspaceHero"
    class="relative overflow-hidden rounded-[28px] border border-border/70 bg-card px-5 py-5 shadow-sm sm:px-6"
  >
    <div
      class="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
    ></div>
    <div
      class="absolute -right-24 top-0 size-72 rounded-full bg-primary/10 blur-3xl"
    ></div>
    <div
      class="absolute left-0 top-1/2 size-48 -translate-y-1/2 rounded-full bg-sky-500/10 blur-3xl"
    ></div>

    <div
      class="relative grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]"
    >
      <div class="space-y-4">
        <div
          class="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/8 px-3 py-1 text-xs font-medium text-primary"
        >
          <IconifyIcon icon="lucide:messages-square" class="size-3.5" />
          {{ $t('user.aiChat.workspace.badge') }}
        </div>

        <div>
          <h1
            class="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl"
          >
            {{ $t('user.aiChat.workspace.title') }}
          </h1>
          <p
            class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
          >
            {{ $t('user.aiChat.workspace.description') }}
          </p>
        </div>

        <div class="flex flex-wrap gap-3">
          <button
            class="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
            type="button"
            @click="router.push('/agents')"
          >
            {{ $t('user.aiChat.workspace.primaryCta') }}
            <IconifyIcon icon="lucide:arrow-up-right" class="size-4" />
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
            type="button"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-4" />
            {{ $t('user.aiChat.workspace.secondaryCta') }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border border-transparent px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            type="button"
            @click="router.push('/help')"
          >
            <IconifyIcon icon="lucide:life-buoy" class="size-4" />
            {{ $t('user.aiChat.workspace.helpCta') }}
          </button>
        </div>
      </div>

      <div class="space-y-4">
        <div
          class="rounded-[22px] border border-border/60 bg-background/70 px-4 py-4 shadow-sm"
        >
          <div class="flex items-start gap-3">
            <div
              class="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-sm font-semibold text-primary"
            >
              <img
                v-if="selectedAgent?.avatar"
                :src="selectedAgent.avatar"
                :alt="selectedAgent.name"
                class="size-12 rounded-2xl object-cover"
              />
              <span v-else>
                {{ (selectedAgent?.name || 'AI').charAt(0).toUpperCase() }}
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <div
                class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground"
              >
                {{ $t('user.aiChat.workspace.signals.agent') }}
              </div>
              <div class="mt-2 text-base font-semibold text-foreground">
                {{
                  selectedAgent?.name ||
                  $t('user.aiChat.workspace.noAgentSelected')
                }}
              </div>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{
                  selectedAgent?.description ||
                  $t('user.aiChat.workspace.agentSummaryFallback')
                }}
              </p>
            </div>
          </div>

          <div class="mt-4 space-y-2">
            <div
              v-for="signal in workspaceHighlights"
              :key="signal.key"
              class="flex items-start gap-3 rounded-2xl border border-border/50 bg-card/70 px-3 py-2.5"
            >
              <span
                class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="signal.icon" class="size-4" />
              </span>
              <div class="min-w-0 flex-1">
                <div
                  class="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground"
                >
                  {{ signal.label }}
                </div>
                <div class="mt-1 text-sm font-medium leading-6 text-foreground">
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
