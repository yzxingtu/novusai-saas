<script lang="ts" setup>
import type { AIAgentInfo } from '#/api/admin/ai-agents';

import { IconifyIcon } from '@vben/icons';

import { Button, Empty, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import AgentListCard from './AgentListCard.vue';

defineOptions({ name: 'AgentListGrid' });

defineProps<{
  agents: AIAgentInfo[];
  loading: boolean;
}>();

const emit = defineEmits<{
  createAgent: [];
  delete: [agent: AIAgentInfo];
  edit: [agent: AIAgentInfo];
  publish: [agent: AIAgentInfo];
  toggleStatus: [agent: AIAgentInfo];
  versions: [agent: AIAgentInfo];
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
        @toggle-status="emit('toggleStatus', $event)"
        @versions="emit('versions', $event)"
      />
    </div>

    <div
      v-else-if="!loading"
      class="flex min-h-[300px] items-center justify-center"
    >
      <Empty :description="$t('admin.common.noData')">
        <Button
          v-access:code="['ai_agent:create']"
          type="primary"
          @click="emit('createAgent')"
        >
          <template #icon>
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </template>
          {{ $t('admin.ai.agent.create') }}
        </Button>
      </Empty>
    </div>
  </Spin>
</template>
