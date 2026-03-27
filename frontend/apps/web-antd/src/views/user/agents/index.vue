<script setup lang="ts">
import type { UserPortalAgent } from '#/views/user/modules/portal-data';

import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Empty, Input, Spin } from 'ant-design-vue';

import { $t } from '#/locales';
import { useUserPortalWorkspace } from '#/views/user/modules/portal-data';
import PortalAgentCard from '#/views/user/modules/PortalAgentCard.vue';

defineOptions({ name: 'UserAgents' });

type AgentFilterKey = 'all' | 'knowledge' | 'recent' | 'tenant' | 'vision';

const PAGE_SIZE = 9;

const router = useRouter();

const searchValue = ref('');
const activeFilter = ref<AgentFilterKey>('all');
const currentPage = ref(1);

const {
  agents,
  ensureKnowledgeSignals,
  knowledgeSignals,
  loadWorkspace,
  loading,
  recentConversationAgentIds,
  stats,
} = useUserPortalWorkspace();

const filterOptions = computed(() => {
  return [
    { key: 'all' as const, label: $t('user.agents.filters.all') },
    { key: 'recent' as const, label: $t('user.agents.filters.recent') },
    { key: 'vision' as const, label: $t('user.agents.filters.vision') },
    { key: 'knowledge' as const, label: $t('user.agents.filters.knowledge') },
    { key: 'tenant' as const, label: $t('user.agents.filters.tenant') },
  ];
});

const agentStats = computed(() => {
  return [
    {
      icon: 'lucide:bot',
      key: 'agents',
      label: $t('user.agents.stats.agents'),
      value: String(stats.value.accessibleAgents),
    },
    {
      icon: 'lucide:history',
      key: 'recent',
      label: $t('user.agents.stats.recent'),
      value: String(recentConversationAgentIds.value.size),
    },
    {
      icon: 'lucide:image-up',
      key: 'vision',
      label: $t('user.agents.stats.vision'),
      value: String(stats.value.visionReadyAgents),
    },
    {
      icon: 'lucide:sparkles',
      key: 'starter',
      label: $t('user.agents.stats.starter'),
      value: String(stats.value.starterReadyAgents),
    },
  ];
});

const filteredAgents = computed(() => {
  const keyword = searchValue.value.trim().toLowerCase();

  return agents.value.filter((agent) => {
    const matchesKeyword =
      keyword.length === 0 ||
      agent.name.toLowerCase().includes(keyword) ||
      (agent.description || '').toLowerCase().includes(keyword) ||
      (agent.model_name || '').toLowerCase().includes(keyword);

    if (!matchesKeyword) {
      return false;
    }

    switch (activeFilter.value) {
      case 'knowledge': {
        return knowledgeSignals.value[agent.id]?.hasKnowledge === true;
      }
      case 'recent': {
        return recentConversationAgentIds.value.has(agent.id);
      }
      case 'tenant': {
        return agent.owner_type === 'tenant';
      }
      case 'vision': {
        return agent.model_capabilities?.supports_vision === true;
      }
      default: {
        return true;
      }
    }
  });
});

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(filteredAgents.value.length / PAGE_SIZE));
});

const pagedAgents = computed(() => {
  const startIndex = (currentPage.value - 1) * PAGE_SIZE;
  return filteredAgents.value.slice(startIndex, startIndex + PAGE_SIZE);
});

watch(
  [activeFilter, searchValue],
  () => {
    currentPage.value = 1;
  },
  { flush: 'post' },
);

watch(
  pagedAgents,
  (items) => {
    void ensureKnowledgeSignals(items.map((agent) => agent.id));
  },
  { immediate: true },
);

watch(totalPages, (value) => {
  if (currentPage.value > value) {
    currentPage.value = value;
  }
});

function navigateTo(path: string) {
  void router.push(path);
}

function openAgent(agent: UserPortalAgent) {
  void router.push({
    path: '/ai-chat',
    query: { agentId: String(agent.id) },
  });
}

function handleQuestion(payload: { agent: UserPortalAgent; question: string }) {
  void router.push({
    path: '/ai-chat',
    query: {
      agentId: String(payload.agent.id),
      prompt: payload.question,
    },
  });
}

function getKnowledgeCount(agentId: number): number {
  return knowledgeSignals.value[agentId]?.count ?? 0;
}

function hasKnowledge(agentId: number): boolean {
  return knowledgeSignals.value[agentId]?.hasKnowledge ?? false;
}

onMounted(async () => {
  await loadWorkspace({ conversationPageSize: 12 });
});
</script>

<template>
  <div class="space-y-6">
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
        class="absolute left-0 top-1/2 size-56 -translate-y-1/2 rounded-full bg-sky-500/10 blur-3xl"
      ></div>

      <div
        class="relative grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]"
      >
        <div class="space-y-5">
          <div
            class="bg-primary/8 inline-flex items-center gap-2 rounded-full border border-primary/20 px-3 py-1 text-xs font-medium text-primary"
          >
            <IconifyIcon icon="lucide:bot" class="size-3.5" />
            {{ $t('user.agents.badge') }}
          </div>
          <div>
            <h1
              class="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
            >
              {{ $t('user.agents.title') }}
            </h1>
            <p
              class="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base"
            >
              {{ $t('user.agents.description') }}
            </p>
          </div>

          <div class="flex flex-wrap gap-3">
            <button
              class="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:scale-[1.01] hover:shadow-xl hover:shadow-primary/20"
              type="button"
              @click="navigateTo('/ai-chat')"
            >
              {{ $t('user.agents.primaryCta') }}
              <IconifyIcon icon="lucide:arrow-up-right" class="size-4" />
            </button>
            <button
              class="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary"
              type="button"
              @click="navigateTo('/help')"
            >
              <IconifyIcon icon="lucide:life-buoy" class="size-4" />
              {{ $t('user.agents.secondaryCta') }}
            </button>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <div
            v-for="stat in agentStats"
            :key="stat.key"
            class="rounded-[24px] border border-border/60 bg-background/90 p-4 shadow-sm"
          >
            <div class="flex items-center justify-between">
              <span
                class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
              >
                <IconifyIcon :icon="stat.icon" class="size-4.5" />
              </span>
              <span
                class="text-3xl font-semibold tracking-tight text-foreground"
              >
                {{ stat.value }}
              </span>
            </div>
            <div class="mt-4 text-sm text-muted-foreground">
              {{ stat.label }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <section
      class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
    >
      <div
        class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
      >
        <div>
          <h2 class="text-xl font-semibold text-foreground">
            {{ $t('user.agents.directoryTitle') }}
          </h2>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t('user.agents.directoryDesc') }}
          </p>
        </div>
        <div class="w-full max-w-xl">
          <Input
            v-model:value="searchValue"
            :placeholder="$t('user.agents.searchPlaceholder')"
            allow-clear
            class="!rounded-full"
          >
            <template #prefix>
              <IconifyIcon
                icon="lucide:search"
                class="size-4 text-muted-foreground"
              />
            </template>
          </Input>
        </div>
      </div>

      <div class="mt-5 flex flex-wrap gap-2">
        <button
          v-for="filter in filterOptions"
          :key="filter.key"
          class="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all"
          :class="
            activeFilter === filter.key
              ? 'border-primary/20 bg-primary/10 text-primary'
              : 'border-border/70 bg-background/80 text-muted-foreground hover:border-primary/15 hover:text-foreground'
          "
          type="button"
          @click="activeFilter = filter.key"
        >
          {{ filter.label }}
        </button>
      </div>

      <Spin :spinning="loading">
        <div
          v-if="pagedAgents.length > 0"
          class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3"
        >
          <PortalAgentCard
            v-for="agent in pagedAgents"
            :key="agent.id"
            :agent="agent"
            :has-knowledge="hasKnowledge(agent.id)"
            :knowledge-count="getKnowledgeCount(agent.id)"
            :last-used-label="
              recentConversationAgentIds.has(agent.id)
                ? $t('user.agents.lastUsed')
                : ''
            "
            @chat="openAgent"
            @question="handleQuestion"
          />
        </div>

        <Empty
          v-else
          :description="$t('user.agents.empty')"
          class="mt-5 rounded-[24px] border border-dashed border-border/70 bg-background/60 py-12"
        />
      </Spin>

      <div
        v-if="pagedAgents.length > 0 && totalPages > 1"
        class="mt-6 flex flex-wrap items-center justify-between gap-3"
      >
        <span class="text-sm text-muted-foreground">
          {{
            $t('user.agents.pagination', {
              current: currentPage,
              total: totalPages,
            })
          }}
        </span>
        <div class="flex items-center gap-2">
          <button
            class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            type="button"
            :disabled="currentPage === 1"
            @click="currentPage -= 1"
          >
            <IconifyIcon icon="lucide:arrow-left" class="size-4" />
            {{ $t('user.agents.prevPage') }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-full border border-border/70 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-primary/25 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
            type="button"
            :disabled="currentPage === totalPages"
            @click="currentPage += 1"
          >
            {{ $t('user.agents.nextPage') }}
            <IconifyIcon icon="lucide:arrow-right" class="size-4" />
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
