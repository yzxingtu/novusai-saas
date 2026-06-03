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
  <div class="space-y-5">
    <UserAIChatWorkspaceHero />
    <div
      class="flex min-h-[72vh] overflow-hidden rounded-[28px] border border-border/40 bg-card shadow-[0_24px_48px_-42px_hsl(var(--foreground)/0.14)]"
    >
      <UserAIChatVarsModal />
      <UserAIChatSidebar />
      <UserAIChatWorkspace />
      <UserAIChatMobileDrawer />
    </div>
  </div>
</template>
