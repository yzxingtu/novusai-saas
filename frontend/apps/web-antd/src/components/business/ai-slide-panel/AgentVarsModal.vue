<script lang="ts" setup>
import type { InputVariable } from '#/components/business/ai-chat-panel/types';

import { IconifyIcon } from '@vben/icons';

import { Input, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

interface SingleAgentVarsState {
  id: number;
  name: string;
  vars: InputVariable[];
}

interface MultiAgentVarsState {
  id: number;
  input_variables?: InputVariable[];
  name: string;
}

defineOptions({ name: 'AgentVarsModal' });

const props = withDefaults(
  defineProps<{
    multiAgents: MultiAgentVarsState[];
    multiOpen: boolean;
    multiPersist: boolean;
    multiValues: Record<number, Record<string, string>>;
    singleAgent?: null | SingleAgentVarsState;
    singleOpen: boolean;
    singlePersist: boolean;
    singleValues: Record<string, string>;
  }>(),
  {
    singleAgent: null,
  },
);

const emit = defineEmits<{
  multiCancel: [];
  multiConfirm: [];
  multiPersistChange: [value: boolean];
  multiValueChange: [payload: { agentId: number; name: string; value: string }];
  singleCancel: [];
  singleConfirm: [];
  singlePersistChange: [value: boolean];
  singleValueChange: [payload: { name: string; value: string }];
}>();

function onSinglePersistChange(event: Event) {
  emit(
    'singlePersistChange',
    (event.target as HTMLInputElement | null)?.checked ?? false,
  );
}

function onMultiPersistChange(event: Event) {
  emit(
    'multiPersistChange',
    (event.target as HTMLInputElement | null)?.checked ?? false,
  );
}

function onSingleValueChange(name: string, value: null | string | undefined) {
  emit('singleValueChange', {
    name,
    value: value ?? '',
  });
}

function onMultiValueChange(
  agentId: number,
  name: string,
  value: null | string | undefined,
) {
  emit('multiValueChange', {
    agentId,
    name,
    value: value ?? '',
  });
}

function getMultiValue(agentId: number, name: string) {
  return props.multiValues[agentId]?.[name] ?? '';
}
</script>

<template>
  <Modal
    :open="singleOpen"
    :title="
      $t('user.aiChat.varsModal.title', {
        name: singleAgent?.name ?? '',
      })
    "
    :mask-closable="false"
    :ok-text="$t('user.aiChat.varsModal.confirm')"
    :cancel-text="$t('common.cancel')"
    @ok="emit('singleConfirm')"
    @cancel="emit('singleCancel')"
  >
    <p class="mb-4 text-sm text-muted-foreground">
      {{ $t('user.aiChat.varsModal.desc') }}
    </p>
    <div v-if="singleAgent" class="space-y-4">
      <div
        v-for="variable in singleAgent.vars"
        :key="variable.name"
        class="flex flex-col gap-1"
      >
        <label class="text-sm font-medium">
          {{ variable.label || variable.name }}
          <span v-if="variable.required" class="ml-0.5 text-destructive">
            *
          </span>
        </label>
        <Input
          :value="singleValues[variable.name] ?? ''"
          :placeholder="variable.default || variable.label || variable.name"
          allow-clear
          @update:value="onSingleValueChange(variable.name, $event)"
        />
      </div>
      <label
        class="flex cursor-pointer items-center gap-2 pt-1 text-xs text-muted-foreground"
      >
        <input
          :checked="singlePersist"
          type="checkbox"
          class="size-3.5 cursor-pointer rounded accent-primary"
          @change="onSinglePersistChange"
        />
        <span class="font-medium text-foreground/70">{{
          $t('user.aiChat.varsModal.persistLabel')
        }}</span>
        <span class="text-[11px]">{{
          $t('user.aiChat.varsModal.persistHint')
        }}</span>
      </label>
    </div>
  </Modal>

  <Modal
    :open="multiOpen"
    :title="$t('user.aiChat.varsModal.editVars')"
    :ok-text="$t('common.save')"
    :cancel-text="$t('common.cancel')"
    @ok="emit('multiConfirm')"
    @cancel="emit('multiCancel')"
  >
    <div class="space-y-6">
      <div v-for="agent in multiAgents" :key="agent.id">
        <div class="mb-3 flex items-center gap-2">
          <IconifyIcon icon="lucide:bot" class="size-4 text-primary" />
          <span class="text-sm font-semibold">{{ agent.name }}</span>
        </div>
        <div class="space-y-3 pl-6">
          <div
            v-for="variable in agent.input_variables"
            :key="variable.name"
            class="flex flex-col gap-1"
          >
            <label class="text-sm font-medium">
              {{ variable.label || variable.name }}
              <span v-if="variable.required" class="ml-0.5 text-destructive">
                *
              </span>
            </label>
            <Input
              :value="getMultiValue(agent.id, variable.name)"
              :placeholder="variable.default || variable.label || variable.name"
              allow-clear
              @update:value="
                onMultiValueChange(agent.id, variable.name, $event)
              "
            />
          </div>
        </div>
      </div>
      <label
        class="flex cursor-pointer items-center gap-2 border-t border-border/40 pt-3 text-xs text-muted-foreground"
      >
        <input
          :checked="multiPersist"
          type="checkbox"
          class="size-3.5 cursor-pointer rounded accent-primary"
          @change="onMultiPersistChange"
        />
        <span class="font-medium text-foreground/70">{{
          $t('user.aiChat.varsModal.persistLabel')
        }}</span>
        <span class="text-[11px]">{{
          $t('user.aiChat.varsModal.persistHint')
        }}</span>
      </label>
    </div>
  </Modal>
</template>
