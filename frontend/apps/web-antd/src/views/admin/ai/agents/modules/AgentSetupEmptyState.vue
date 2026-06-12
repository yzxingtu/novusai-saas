<script lang="ts" setup>
import type { AdminAgentSetupState } from '../composables/setup-state';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AgentSetupEmptyState' });

const props = defineProps<{
  canSeedSystem: boolean;
  loading: boolean;
  seedLoading: boolean;
  state: AdminAgentSetupState;
}>();

const emit = defineEmits<{
  goModels: [];
  goProviders: [];
  refresh: [];
  seedSystem: [];
}>();

const viewMeta = computed(() => {
  switch (props.state) {
    case 'error': {
      return {
        desc: 'admin.ai.agent.setup.errorDesc',
        icon: 'lucide:circle-alert',
        title: 'admin.ai.agent.setup.errorTitle',
        tone: 'bg-red-500/10 text-red-600 dark:text-red-300',
      };
    }
    case 'missing-model': {
      return {
        desc: 'admin.ai.agent.setup.missingModelDesc',
        icon: 'lucide:box',
        title: 'admin.ai.agent.setup.missingModelTitle',
        tone: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
      };
    }
    case 'missing-provider': {
      return {
        desc: 'admin.ai.agent.setup.missingProviderDesc',
        icon: 'lucide:plug-zap',
        title: 'admin.ai.agent.setup.missingProviderTitle',
        tone: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
      };
    }
    case 'seed-system': {
      return {
        desc: 'admin.ai.agent.setup.seedDesc',
        icon: 'lucide:sparkles',
        title: 'admin.ai.agent.setup.seedTitle',
        tone: 'bg-primary/10 text-primary',
      };
    }
    default: {
      return {
        desc: 'admin.ai.agent.setup.checkingDesc',
        icon: 'lucide:loader-2',
        title: 'admin.ai.agent.setup.checkingTitle',
        tone: 'bg-muted text-muted-foreground',
      };
    }
  }
});
</script>

<template>
  <section
    class="flex min-h-[300px] items-center justify-center rounded-lg border border-border bg-muted/30 px-4 py-6"
  >
    <div class="flex w-full max-w-2xl items-start gap-4">
      <div
        class="flex size-11 shrink-0 items-center justify-center rounded-lg"
        :class="viewMeta.tone"
      >
        <IconifyIcon
          :icon="viewMeta.icon"
          class="size-5"
          :class="{ 'animate-spin': props.state === 'checking' }"
        />
      </div>

      <div class="min-w-0 flex-1 space-y-3">
        <div>
          <h3 class="text-base font-semibold text-foreground">
            {{ $t(viewMeta.title) }}
          </h3>
          <p class="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">
            {{ $t(viewMeta.desc) }}
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <Button
            v-if="props.state === 'missing-provider'"
            type="primary"
            @click="emit('goProviders')"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plug-zap" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.setup.goProvider') }}
          </Button>

          <Button
            v-else-if="props.state === 'missing-model'"
            type="primary"
            @click="emit('goModels')"
          >
            <template #icon>
              <IconifyIcon icon="lucide:box" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.setup.goModel') }}
          </Button>

          <Button
            v-else-if="props.state === 'seed-system' && props.canSeedSystem"
            v-access:code="['ai_agent:seed_system']"
            :loading="props.seedLoading"
            type="primary"
            @click="emit('seedSystem')"
          >
            <template #icon>
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.setup.seedButton') }}
          </Button>

          <span
            v-else-if="props.state === 'seed-system'"
            class="text-sm text-muted-foreground"
          >
            {{ $t('admin.ai.agent.setup.seedPermissionHint') }}
          </span>

          <Button
            v-if="props.state === 'error'"
            :loading="props.loading"
            @click="emit('refresh')"
          >
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.setup.retry') }}
          </Button>
        </div>
      </div>
    </div>
  </section>
</template>
