<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Spin, Tooltip } from 'ant-design-vue';

import ChatMessageAgentAvatar from '#/components/business/ai-chat-panel/ChatMessageAgentAvatar.vue';
import { $t } from '#/locales';

import { useUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';

const workspace = useUserAIChatWorkspaceContext();
const {
  page: {
    chat,
    chatHeaderSubtitle,
    headerHasVariables,
    headerVarsConfigured,
    showMemoryPanel,
    onToggleMemory,
    onStartNewChat,
    openHeaderVarsModal,
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
      class="border-border/16 flex shrink-0 items-start justify-between gap-3 border-b px-3.5 py-2.5"
    >
      <div class="flex min-w-0 items-start gap-3">
        <button
          data-testid="user-ai-chat-mobile-sidebar-button"
          class="size-7.5 flex items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
          @click="workspace.openMobileSidebar"
        >
          <IconifyIcon icon="lucide:panel-left" class="size-3.5" />
        </button>

        <div class="flex min-w-0 items-center gap-3">
          <div
            v-if="selectedAgent"
            data-testid="user-ai-chat-agent-profile-trigger"
            class="shrink-0"
          >
            <ChatMessageAgentAvatar
              :agent-avatar="selectedAgent.avatar"
              :agent-description="selectedAgent.description"
              :agent-id="selectedAgent.id"
              :agent-knowledge-base-ids="selectedAgent.knowledge_base_ids"
              :agent-knowledge-bases="selectedAgent.knowledge_bases"
              :agent-name="selectedAgent.name"
              :agent-skills="selectedAgent.skills"
              :model-name="selectedAgent.model_name"
            />
          </div>
          <div class="min-w-0">
            <div
              data-testid="user-ai-chat-workspace-title"
              class="text-foreground/86 text-[13px] font-semibold"
            >
              {{ $t('user.aiChat.title') }}
            </div>
            <div
              v-if="chatHeaderSubtitle"
              data-testid="user-ai-chat-workspace-subtitle"
              class="text-muted-foreground/68 mt-0.5 truncate text-[10px]"
            >
              {{ chatHeaderSubtitle }}
            </div>
          </div>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <Tooltip
          v-if="headerHasVariables"
          :title="$t('user.aiChat.varsModal.editVars')"
        >
          <button
            data-testid="user-ai-chat-vars-button"
            class="hover:bg-primary/8 flex h-7 items-center gap-1 rounded-[12px] px-2 text-[10px] font-medium text-primary transition-colors"
            @click="openHeaderVarsModal"
          >
            <IconifyIcon icon="lucide:sliders-horizontal" class="size-3" />
            <span class="hidden sm:inline">{{
              $t('user.aiChat.varsModal.editVars')
            }}</span>
            <span
              v-if="headerVarsConfigured"
              class="size-1.5 rounded-full bg-green-500"
            ></span>
          </button>
        </Tooltip>

        <Tooltip :title="$t('common.aiPanel.newChat')">
          <button
            data-testid="user-ai-chat-new-chat-button"
            class="flex size-7 items-center justify-center rounded-[12px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            @click="onStartNewChat"
          >
            <IconifyIcon icon="lucide:plus" class="size-3.25" />
          </button>
        </Tooltip>

        <Tooltip
          v-if="activeConversationId"
          :title="$t('common.aiPanel.memory')"
        >
          <button
            data-testid="user-ai-chat-memory-button"
            class="flex h-7 items-center gap-1 rounded-[12px] px-2 text-[10px] transition-colors hover:bg-muted disabled:opacity-40"
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
            <IconifyIcon v-else icon="lucide:brain" class="size-3.25" />
            <span class="hidden sm:inline">{{
              $t('common.aiPanel.memory')
            }}</span>
            <span
              v-if="lastMemoryUpdated && !showMemoryPanel"
              class="size-1.5 rounded-full bg-primary"
            ></span>
          </button>
        </Tooltip>
      </div>
    </div>

    <div v-if="streaming" class="h-px w-full overflow-hidden bg-primary/10">
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
