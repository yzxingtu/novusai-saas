<script lang="ts" setup>
import type { TenantAgentSetupState } from '../composables/setup-state';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'TenantAgentSetupEmptyState' });

const props = defineProps<{
  loading: boolean;
  state: TenantAgentSetupState;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

const viewMeta = computed(() => {
  if (props.state === 'missing-model') {
    return {
      desc: 'tenant.ai.agent.setup.missingModelDesc',
      icon: 'lucide:circle-alert',
      title: 'tenant.ai.agent.setup.missingModelTitle',
      tone: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
    };
  }

  return {
    desc: 'tenant.ai.agent.setup.checkingDesc',
    icon: 'lucide:loader-2',
    title: 'tenant.ai.agent.setup.checkingTitle',
    tone: 'bg-muted text-muted-foreground',
  };
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

        <Button
          v-if="props.state === 'missing-model'"
          :loading="props.loading"
          @click="emit('refresh')"
        >
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
          </template>
          {{ $t('tenant.ai.agent.setup.retry') }}
        </Button>
      </div>
    </div>
  </section>
</template>
