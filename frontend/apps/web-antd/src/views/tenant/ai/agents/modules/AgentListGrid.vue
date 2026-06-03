<script lang="ts" setup>
import type { AgentListItem } from '#/api/tenant/agents';

import { IconifyIcon } from '@vben/icons';

import { Button, Empty, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import AgentListCard from './AgentListCard.vue';

defineOptions({ name: 'TenantAgentListGrid' });

defineProps<{
  agents: AgentListItem[];
  loading: boolean;
}>();

const emit = defineEmits<{
  createAgent: [];
  delete: [agent: AgentListItem];
  edit: [agent: AgentListItem];
  publish: [agent: AgentListItem];
  versions: [agent: AgentListItem];
}>();
</script>

<template>
  <Spin :spinning="loading">
    <div
      v-if="agents.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <AgentListCard
        v-for="agent in agents"
        :key="agent.id"
        :agent="agent"
        @delete="emit('delete', $event)"
        @edit="emit('edit', $event)"
        @publish="emit('publish', $event)"
        @versions="emit('versions', $event)"
      />
    </div>

    <div
      v-else-if="!loading"
      class="flex min-h-[300px] items-center justify-center"
    >
      <Empty :description="$t('common.noData')">
        <Button
          v-access:code="['agent:create']"
          type="primary"
          @click="emit('createAgent')"
        >
          <template #icon>
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </template>
          {{ $t('tenant.ai.agent.create') }}
        </Button>
      </Empty>
    </div>
  </Spin>
</template>
