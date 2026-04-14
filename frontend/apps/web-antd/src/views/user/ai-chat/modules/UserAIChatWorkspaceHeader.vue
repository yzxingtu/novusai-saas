<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Spin, Tooltip } from 'ant-design-vue';

import { $t } from '#/locales';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const workspace = useUserAIChatWorkspaceContext();
const {
  page: {
    chat,
    showWorkspaceHero,
    chatHeaderSubtitle,
    selectedAgentHasVariables,
    selectedAgentVarsConfigured,
    showMemoryPanel,
    onToggleMemory,
    onStartNewChat,
    openSelectedAgentVarsModal,
  },
} = workspace;
const {
  selectedAgent,
  activeConversationId,
  streaming,
  memoryLoading,
  clearingMemory,
  lastMemoryUpdated,
} = chat;
</script>

<template>
  <div>
    <div
      class="flex shrink-0 items-start justify-between gap-3 border-b border-border/40 px-4 py-3"
    >
      <div class="flex min-w-0 items-start gap-3">
        <button
          class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
          @click="workspace.openMobileSidebar"
        >
          <IconifyIcon icon="lucide:panel-left" class="size-4" />
        </button>

        <div
          v-if="!showWorkspaceHero && selectedAgent"
          class="flex min-w-0 items-center gap-3"
        >
          <div
            class="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-xs font-medium text-primary"
          >
            <img
              v-if="selectedAgent.avatar"
              :src="selectedAgent.avatar"
              :alt="selectedAgent.name"
              class="size-9 rounded-xl object-cover"
            />
            <span v-else>{{ selectedAgent.name.charAt(0).toUpperCase() }}</span>
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-foreground">
              {{ selectedAgent.name }}
            </div>
            <div
              v-if="chatHeaderSubtitle"
              class="truncate text-[11px] text-muted-foreground"
            >
              {{ chatHeaderSubtitle }}
            </div>
          </div>
        </div>

        <div v-else class="min-w-0">
          <div class="text-sm font-semibold text-foreground">
            {{ $t('user.aiChat.title') }}
          </div>
          <div
            v-if="chatHeaderSubtitle"
            class="truncate text-[11px] text-muted-foreground"
          >
            {{ chatHeaderSubtitle }}
          </div>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <Tooltip
          v-if="selectedAgentHasVariables"
          :title="$t('user.aiChat.varsModal.editVars')"
        >
          <button
            class="flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-medium text-primary transition-colors hover:bg-primary/8"
            @click="openSelectedAgentVarsModal"
          >
            <IconifyIcon icon="lucide:sliders-horizontal" class="size-3.5" />
            <span class="hidden sm:inline">{{
              $t('user.aiChat.varsModal.editVars')
            }}</span>
            <span
              v-if="selectedAgentVarsConfigured"
              class="size-1.5 rounded-full bg-green-500"
            ></span>
          </button>
        </Tooltip>

        <Tooltip :title="$t('common.aiPanel.newChat')">
          <button
            class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </button>
        </Tooltip>

        <Tooltip
          v-if="activeConversationId"
          :title="$t('common.globalAiChat.memoryUpdated')"
        >
          <button
            class="flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-muted disabled:opacity-40"
            :class="
              showMemoryPanel
                ? 'bg-primary/10 text-primary'
                : lastMemoryUpdated
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
            "
            :disabled="clearingMemory"
            @click="onToggleMemory"
          >
            <Spin v-if="memoryLoading" size="small" />
            <IconifyIcon v-else icon="lucide:brain" class="size-4" />
          </button>
        </Tooltip>
      </div>
    </div>

    <div v-if="streaming" class="h-0.5 w-full overflow-hidden bg-primary/10">
      <div class="streaming-bar h-full bg-primary/60"></div>
    </div>
  </div>
</template>

<style scoped>
@keyframes streaming-slide {
  0% {
    transform: translateX(-100%);
  }

  50% {
    transform: translateX(233%);
  }

  100% {
    transform: translateX(-100%);
  }
}

.streaming-bar {
  width: 30%;
  background: linear-gradient(
    90deg,
    transparent,
    hsl(var(--primary) / 60%),
    hsl(var(--primary)),
    hsl(var(--primary) / 60%),
    transparent
  );
  border-radius: 9999px;
  animation: streaming-slide 1.5s ease-in-out infinite;
}
</style>
