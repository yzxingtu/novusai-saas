<script lang="ts" setup>
import { useUserAIChatWorkspace } from '../composables/use-user-ai-chat-workspace';
import { provideUserAIChatWorkspaceContext } from './user-ai-chat-workspace-context';
import UserAIChatWorkspaceComposer from './UserAIChatWorkspaceComposer.vue';
import UserAIChatWorkspaceHeader from './UserAIChatWorkspaceHeader.vue';
import UserAIChatWorkspaceImagePreview from './UserAIChatWorkspaceImagePreview.vue';
import UserAIChatWorkspaceMemoryPanel from './UserAIChatWorkspaceMemoryPanel.vue';
import UserAIChatWorkspaceMessages from './UserAIChatWorkspaceMessages.vue';
import UserAIChatWorkspaceTokenUsage from './UserAIChatWorkspaceTokenUsage.vue';

const workspace = useUserAIChatWorkspace();

provideUserAIChatWorkspaceContext(workspace);
</script>

<template>
  <div class="flex flex-1 flex-col overflow-hidden">
    <UserAIChatWorkspaceHeader />
    <UserAIChatWorkspaceMemoryPanel />
    <UserAIChatWorkspaceMessages />
    <UserAIChatWorkspaceTokenUsage />
    <UserAIChatWorkspaceComposer />
    <UserAIChatWorkspaceImagePreview />
  </div>
</template>
