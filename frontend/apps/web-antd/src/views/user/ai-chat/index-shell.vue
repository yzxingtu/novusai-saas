<script lang="ts" setup>
import UserAIChatMobileDrawer from './modules/UserAIChatMobileDrawer.vue';
import UserAIChatSidebar from './modules/UserAIChatSidebar.vue';
import UserAIChatVarsModal from './modules/UserAIChatVarsModal.vue';
import UserAIChatWorkspace from './modules/UserAIChatWorkspace.vue';
import UserAIChatWorkspaceHero from './modules/UserAIChatWorkspaceHero.vue';
import { useUserAIChatPage } from './use-user-ai-chat-page';

defineOptions({ name: 'UserAIChat' });

useUserAIChatPage();
</script>

<template>
  <div class="space-y-4">
    <UserAIChatWorkspaceHero />
    <div
      class="flex min-h-[72vh] overflow-hidden rounded-xl border border-border bg-card"
    >
      <UserAIChatVarsModal />
      <UserAIChatSidebar />
      <UserAIChatWorkspace />
      <UserAIChatMobileDrawer />
    </div>
  </div>
</template>
