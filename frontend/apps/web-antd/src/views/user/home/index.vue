<script setup lang="ts">
import type { ConversationItem } from '#/components/business/ai-chat-panel/types';
import type { UserPortalAgent } from '#/views/user/modules/portal-data';

import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { VbenAvatar } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

import { Empty, Spin } from 'ant-design-vue';

import { USER_HOME_PATH, USER_LOGIN_PATH } from '#/constants/endpoints';
import { $t } from '#/locales';
import { useMultiAuthStore, usePublicConfigStore } from '#/store';
import { formatDate } from '#/utils/common';
import {
  buildHelpFaqs,
  buildHelpJourneys,
  buildHelpResources,
} from '#/views/user/modules/help-center';
import { useUserPortalWorkspace } from '#/views/user/modules/portal-data';
import PortalAgentCard from '#/views/user/modules/PortalAgentCard.vue';

defineOptions({ name: 'UserHome' });

const router = useRouter();
const publicConfigStore = usePublicConfigStore();
const multiAuthStore = useMultiAuthStore();
const userStore = useUserStore();
const hasUserSession = ref(
  multiAuthStore.isAuthenticated('user') &&
    userStore.userInfo?.homePath === USER_HOME_PATH &&
    Boolean(userStore.userInfo?.username),
);

const isLoggedIn = computed(() => {
  return hasUserSession.value;
});

const brandName = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteName ||
    publicConfigStore.tenantConfig?.tenantName ||
    preferences.app.name
  );
});

const brandDescription = computed(() => {
  return (
    publicConfigStore.tenantBrand?.siteDescription ||
    $t('user.portal.tenantWelcomeFallback')
  );
});

const brandLogo = computed(() => {
  return publicConfigStore.tenantBrand?.logo || preferences.logo.source;
});

const userName = computed(() => {
  return userStore.userInfo?.realName || userStore.userInfo?.username || '';
});

const userAvatar = computed(() => {
  return userStore.userInfo?.avatar || preferences.app.defaultAvatar;
});

const registrationEnabled = computed(
  () => publicConfigStore.isRegistrationEnabled,
);

const {
  conversations,
  conversationsLoading,
  ensureKnowledgeSignals,
  knowledgeSignals,
  loadWorkspace,
  loading,
  recommendedAgents,
  stats,
} = useUserPortalWorkspace();

const portalMetrics = computed(() => {
  return [
    {
      icon: 'lucide:bot',
      key: 'agents',
      label: $t('user.portal.metrics.agents'),
      value: String(stats.value.accessibleAgents),
    },
    {
      icon: 'lucide:history',
      key: 'sessions',
      label: $t('user.portal.metrics.sessions'),
      value: String(stats.value.recentConversations),
    },
    {
      icon: 'lucide:image-up',
      key: 'vision',
      label: $t('user.portal.metrics.vision'),
      value: String(stats.value.visionReadyAgents),
    },
    {
      icon: 'lucide:messages-square',
      key: 'starters',
      label: $t('user.portal.metrics.starters'),
      value: String(stats.value.starterReadyAgents),
    },
  ];
});

const helpJourneys = computed(() => buildHelpJourneys($t));
const helpResources = computed(() => buildHelpResources($t));
const helpFaqs = computed(() => buildHelpFaqs($t));

const capabilityBands = computed(() => {
  return [
    {
      description: $t('user.portal.capabilityBands.agent.desc'),
      icon: 'lucide:bot',
      title: $t('user.portal.capabilityBands.agent.title'),
    },
    {
      description: $t('user.portal.capabilityBands.workflow.desc'),
      icon: 'lucide:route',
      title: $t('user.portal.capabilityBands.workflow.title'),
    },
    {
      description: $t('user.portal.capabilityBands.help.desc'),
      icon: 'lucide:life-buoy',
      title: $t('user.portal.capabilityBands.help.title'),
    },
  ];
});

const recentConversationList = computed(() => conversations.value.slice(0, 5));

watch(
  recommendedAgents,
  (agents) => {
    void ensureKnowledgeSignals(agents.map((agent) => agent.id));
  },
  { immediate: true },
);

function navigateTo(path: string) {
  void router.push(path);
}

function navigateToProtected(path: string) {
  if (isLoggedIn.value) {
    void router.push(path);
    return;
  }
  void router.push({
    path: USER_LOGIN_PATH,
    query: { redirect: path },
  });
}

function openAgent(agent: UserPortalAgent) {
  void router.push({
    path: '/ai-chat',
    query: { agentId: String(agent.id) },
  });
}

function openConversation(conversation: ConversationItem) {
  void router.push({
    path: '/ai-chat',
    query: {
      agentId: String(conversation.agent_id),
      conversationId: String(conversation.id),
    },
  });
}

function openQuestion(agent: UserPortalAgent, question: string) {
  void router.push({
    path: '/ai-chat',
    query: {
      agentId: String(agent.id),
      prompt: question,
    },
  });
}

function handleAgentQuestion(payload: {
  agent: UserPortalAgent;
  question: string;
}) {
  openQuestion(payload.agent, payload.question);
}

function getKnowledgeCount(agentId: number): number {
  return knowledgeSignals.value[agentId]?.count ?? 0;
}

function hasKnowledge(agentId: number): boolean {
  return knowledgeSignals.value[agentId]?.hasKnowledge ?? false;
}

async function hydrateUserPortalSession() {
  if (!multiAuthStore.isAuthenticated('user')) {
    hasUserSession.value = false;
    return;
  }

  try {
    const shouldHydrateUserInfo =
      userStore.userInfo?.homePath !== USER_HOME_PATH ||
      !userStore.userInfo?.username;
    const userInfo = shouldHydrateUserInfo
      ? await multiAuthStore.fetchUserInfo('user')
      : userStore.userInfo;

    hasUserSession.value = Boolean(userInfo?.username);

    if (hasUserSession.value) {
      await loadWorkspace({ conversationPageSize: 8 });
    }
  } catch {
    hasUserSession.value = false;
  }
}

onMounted(async () => {
  await publicConfigStore.loadTenantConfig();
  await hydrateUserPortalSession();
});
</script>

<template>
  <div class="space-y-6">
    <template v-if="isLoggedIn">
      <section
        class="relative overflow-hidden rounded-[32px] border border-border/70 bg-card px-6 py-7 shadow-sm sm:px-8"
      >
        <div
          class="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
        ></div>
        <div
          class="absolute -right-24 top-0 size-72 rounded-full bg-primary/10 blur-3xl"
        ></div>
        <div
          class="absolute -left-16 bottom-0 size-56 rounded-full bg-sky-500/10 blur-3xl"
        ></div>

        <div
          class="relative grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]"
        >
          <div class="space-y-5">
            <div
              class="bg-primary/8 inline-flex items-center gap-2 rounded-full border border-primary/20 px-3 py-1 text-xs font-medium text-primary"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-3.5" />
              {{ $t('user.portal.heroBadge') }}
            </div>

            <div class="flex items-start gap-4">
              <VbenAvatar
                :src="userAvatar"
                :alt="userName"
                class="size-14 shrink-0 rounded-2xl shadow-lg ring-2 ring-background sm:size-16"
              />
              <div class="min-w-0">
                <p class="text-sm font-medium text-muted-foreground">
                  {{ $t('user.portal.greetingEyebrow', { brand: brandName }) }}
                </p>
                <h1
                  class="mt-2 text-3xl font-semibold tracking-tight text-foreground"
                >
                  {{ $t('user.portal.greetingTitle', { name: userName }) }}
                </h1>
                <p
                  class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
                >
                  {{ $t('user.portal.greetingDesc') }}
                </p>
              </div>
            </div>

            <div class="flex flex-wrap gap-3">
              <button
                class="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
                type="button"
                @click="navigateTo('/agents')"
              >
                {{ $t('user.portal.primaryCta') }}
                <IconifyIcon icon="lucide:arrow-up-right" class="size-4" />
              </button>
              <button
                class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-5 py-2.5 text-sm font-medium text-foreground transition-all hover:border-primary/25 hover:text-primary"
                type="button"
                @click="navigateTo('/ai-chat')"
              >
                <IconifyIcon icon="lucide:messages-square" class="size-4" />
                {{ $t('user.portal.secondaryCta') }}
              </button>
              <button
                class="inline-flex items-center gap-2 rounded-full border border-transparent px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                type="button"
                @click="navigateTo('/help')"
              >
                <IconifyIcon icon="lucide:life-buoy" class="size-4" />
                {{ $t('user.portal.helpCta') }}
              </button>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div
              v-for="metric in portalMetrics"
              :key="metric.key"
              class="rounded-[24px] border border-border/60 bg-background/90 p-4 shadow-sm backdrop-blur"
            >
              <div class="flex items-center justify-between">
                <span
                  class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon :icon="metric.icon" class="size-4.5" />
                </span>
                <span
                  class="text-3xl font-semibold tracking-tight text-foreground"
                >
                  {{ metric.value }}
                </span>
              </div>
              <div class="mt-4 text-sm text-muted-foreground">
                {{ metric.label }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        class="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]"
      >
        <div
          class="space-y-4 rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('user.portal.recommendedAgentsTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('user.portal.recommendedAgentsDesc') }}
              </p>
            </div>
            <button
              class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
              type="button"
              @click="navigateTo('/agents')"
            >
              {{ $t('user.portal.viewAllAgents') }}
              <IconifyIcon icon="lucide:arrow-right" class="size-4" />
            </button>
          </div>

          <Spin :spinning="loading">
            <div
              v-if="recommendedAgents.length > 0"
              class="grid gap-4 lg:grid-cols-2"
            >
              <PortalAgentCard
                v-for="agent in recommendedAgents"
                :key="agent.id"
                :agent="agent"
                :has-knowledge="hasKnowledge(agent.id)"
                :knowledge-count="getKnowledgeCount(agent.id)"
                @chat="openAgent"
                @question="handleAgentQuestion"
              />
            </div>
            <Empty
              v-else
              :description="$t('user.portal.emptyAgents')"
              class="rounded-[24px] border border-dashed border-border/70 bg-background/60 py-12"
            />
          </Spin>
        </div>

        <div
          class="space-y-4 rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('user.portal.recentSessionsTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('user.portal.recentSessionsDesc') }}
              </p>
            </div>
            <button
              class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
              type="button"
              @click="navigateTo('/ai-chat')"
            >
              {{ $t('user.portal.openWorkspace') }}
            </button>
          </div>

          <Spin :spinning="conversationsLoading">
            <div v-if="recentConversationList.length > 0" class="space-y-3">
              <button
                v-for="conversation in recentConversationList"
                :key="conversation.id"
                class="group flex w-full items-start gap-3 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4 text-left transition-all hover:border-primary/25 hover:bg-primary/5"
                type="button"
                @click="openConversation(conversation)"
              >
                <span
                  class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon icon="lucide:message-square" class="size-4.5" />
                </span>
                <span class="min-w-0 flex-1">
                  <span
                    class="line-clamp-2 text-sm font-medium text-foreground"
                  >
                    {{
                      conversation.title ||
                      $t('user.portal.untitledConversation')
                    }}
                  </span>
                  <span
                    class="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                  >
                    <span>{{
                      conversation.agent_name ||
                      $t('user.portal.agentFallbackName')
                    }}</span>
                    <span class="size-1 rounded-full bg-border"></span>
                    <span>{{
                      formatDate(conversation.created_at, 'YYYY-MM-DD HH:mm')
                    }}</span>
                  </span>
                </span>
                <IconifyIcon
                  icon="lucide:arrow-up-right"
                  class="mt-1 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                />
              </button>
            </div>
            <Empty
              v-else
              :description="$t('user.portal.emptySessions')"
              class="rounded-[24px] border border-dashed border-border/70 bg-background/60 py-12"
            />
          </Spin>
        </div>
      </section>

      <section
        class="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]"
      >
        <div
          class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <div class="flex items-center gap-3">
            <span
              class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:rocket" class="size-5" />
            </span>
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('user.portal.quickStartTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('user.portal.quickStartDesc') }}
              </p>
            </div>
          </div>

          <div class="mt-5 grid gap-3">
            <button
              v-for="(journey, index) in helpJourneys"
              :key="journey.path"
              class="group flex items-start gap-4 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4 text-left transition-all hover:border-primary/25 hover:bg-primary/5"
              type="button"
              @click="navigateTo(journey.path)"
            >
              <span
                class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="journey.icon" class="size-4.5" />
              </span>
              <span class="min-w-0 flex-1">
                <span
                  class="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground"
                >
                  {{ $t('user.portal.stepLabel', { index: index + 1 }) }}
                </span>
                <span
                  class="mt-2 block text-base font-semibold text-foreground"
                >
                  {{ journey.title }}
                </span>
                <span
                  class="mt-1 block text-sm leading-6 text-muted-foreground"
                >
                  {{ journey.description }}
                </span>
              </span>
              <IconifyIcon
                icon="lucide:arrow-right"
                class="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
              />
            </button>
          </div>
        </div>

        <div
          class="space-y-4 rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-xl font-semibold text-foreground">
                {{ $t('user.portal.helpSnapshotTitle') }}
              </h2>
              <p class="mt-1 text-sm text-muted-foreground">
                {{ $t('user.portal.helpSnapshotDesc') }}
              </p>
            </div>
            <button
              class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
              type="button"
              @click="navigateTo('/help')"
            >
              {{ $t('user.portal.viewHelpCenter') }}
            </button>
          </div>

          <div class="space-y-3">
            <div
              v-for="faq in helpFaqs.slice(0, 3)"
              :key="faq.question"
              class="rounded-[22px] border border-border/60 bg-background/80 p-4"
            >
              <div class="flex items-start gap-3">
                <span
                  class="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon :icon="faq.icon" class="size-4.5" />
                </span>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-foreground">
                    {{ faq.question }}
                  </h3>
                  <p class="mt-2 text-sm leading-6 text-muted-foreground">
                    {{ faq.answer }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <template v-else>
      <section
        class="relative overflow-hidden rounded-[32px] border border-border/70 bg-card px-6 py-8 shadow-sm sm:px-8"
      >
        <div
          class="bg-primary/12 absolute -right-20 top-0 size-72 rounded-full blur-3xl"
        ></div>
        <div
          class="absolute -left-16 bottom-0 size-60 rounded-full bg-emerald-500/10 blur-3xl"
        ></div>

        <div
          class="relative grid gap-8 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]"
        >
          <div class="space-y-5">
            <div
              class="bg-primary/8 inline-flex items-center gap-2 rounded-full border border-primary/20 px-3 py-1 text-xs font-medium text-primary"
            >
              <IconifyIcon icon="lucide:badge-check" class="size-3.5" />
              {{ $t('user.portal.tenantBadge') }}
            </div>
            <div class="flex items-center gap-4">
              <img
                v-if="brandLogo"
                :src="brandLogo"
                :alt="brandName"
                class="size-16 rounded-[20px] object-contain shadow-lg"
              />
              <div>
                <h1
                  class="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
                >
                  {{ $t('user.portal.tenantHeroTitle', { brand: brandName }) }}
                </h1>
                <p
                  class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
                >
                  {{ brandDescription }}
                </p>
              </div>
            </div>
            <div class="flex flex-wrap gap-3">
              <button
                class="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
                type="button"
                @click="navigateTo(USER_LOGIN_PATH)"
              >
                {{ $t('user.home.signIn') }}
                <IconifyIcon icon="lucide:log-in" class="size-4" />
              </button>
              <button
                v-if="registrationEnabled"
                class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
                type="button"
                @click="navigateTo('/auth/register')"
              >
                <IconifyIcon icon="lucide:user-plus" class="size-4" />
                {{ $t('user.home.signUp') }}
              </button>
              <button
                class="inline-flex items-center gap-2 rounded-full border border-transparent px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                type="button"
                @click="navigateToProtected('/help')"
              >
                <IconifyIcon icon="lucide:life-buoy" class="size-4" />
                {{ $t('user.portal.helpCta') }}
              </button>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div
              v-for="band in capabilityBands"
              :key="band.title"
              class="rounded-[24px] border border-border/60 bg-background/90 p-4 shadow-sm"
            >
              <span
                class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="band.icon" class="size-5" />
              </span>
              <h2 class="mt-4 text-base font-semibold text-foreground">
                {{ band.title }}
              </h2>
              <p class="mt-2 text-sm leading-6 text-muted-foreground">
                {{ band.description }}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div
          class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <h2 class="text-xl font-semibold text-foreground">
            {{ $t('user.portal.quickStartTitle') }}
          </h2>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('user.portal.tenantQuickStartDesc') }}
          </p>
          <div class="mt-5 grid gap-3">
            <button
              v-for="journey in helpJourneys"
              :key="journey.path"
              class="flex items-start gap-4 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4 text-left transition-all hover:border-primary/25 hover:bg-primary/5"
              type="button"
              @click="navigateToProtected(journey.path)"
            >
              <span
                class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="journey.icon" class="size-4.5" />
              </span>
              <span class="min-w-0">
                <span class="block text-base font-semibold text-foreground">
                  {{ journey.title }}
                </span>
                <span
                  class="mt-1 block text-sm leading-6 text-muted-foreground"
                >
                  {{ journey.description }}
                </span>
              </span>
            </button>
          </div>
        </div>

        <div
          class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
        >
          <h2 class="text-xl font-semibold text-foreground">
            {{ $t('user.portal.helpSnapshotTitle') }}
          </h2>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('user.portal.tenantHelpSnapshotDesc') }}
          </p>
          <div class="mt-5 space-y-3">
            <div
              v-for="resource in helpResources"
              :key="resource.path"
              class="rounded-[22px] border border-border/60 bg-background/80 p-4"
            >
              <div class="flex items-start gap-3">
                <span
                  class="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon :icon="resource.icon" class="size-4.5" />
                </span>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-foreground">
                    {{ resource.title }}
                  </h3>
                  <p class="mt-2 text-sm leading-6 text-muted-foreground">
                    {{ resource.description }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <button
            class="mt-5 inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
            type="button"
            @click="navigateTo(USER_LOGIN_PATH)"
          >
            <IconifyIcon icon="lucide:log-in" class="size-4" />
            {{ $t('user.home.signIn') }}
          </button>
        </div>
      </section>
    </template>
  </div>
</template>
