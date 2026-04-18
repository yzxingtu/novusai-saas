<script lang="ts" setup>
import type { AIAgentInfo, AIAgentMemoryConfig } from '#/api/admin/ai';

import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, message, Spin, Switch, Tag, Textarea } from 'ant-design-vue';

import {
  getAIAgentMemoryConfigApi,
  updateAIAgentMemoryConfigApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getExecutionModeText, getStatusText } from '../../data';

const props = defineProps<{
  active: boolean;
  agent: AIAgentInfo;
  agentId: number;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}>();

const editingPrompt = ref(false);
const promptDraft = ref('');

const memoryLoading = ref(false);
const memorySaving = ref(false);
const memoryConfig = ref<AIAgentMemoryConfig | null>(null);
const adminMemoryEnabled = ref(true);

function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'disabled': {
      return 'red';
    }
    case 'draft': {
      return 'default';
    }
    case 'published': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

function initPrompt() {
  promptDraft.value = props.agent.system_prompt || '';
  editingPrompt.value = false;
}

async function savePrompt() {
  await props.onSaveFields({ system_prompt: promptDraft.value });
  editingPrompt.value = false;
}

async function loadMemoryConfig() {
  memoryLoading.value = true;
  try {
    memoryConfig.value = await getAIAgentMemoryConfigApi(props.agentId);
    adminMemoryEnabled.value = memoryConfig.value.admin_agent_memory_enabled;
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
  } finally {
    memoryLoading.value = false;
  }
}

async function updateAdminMemoryEnabled(checked: boolean) {
  const previous = adminMemoryEnabled.value;
  adminMemoryEnabled.value = checked;
  memorySaving.value = true;
  try {
    memoryConfig.value = await updateAIAgentMemoryConfigApi(props.agentId, {
      enabled: checked,
    });
    adminMemoryEnabled.value = memoryConfig.value.admin_agent_memory_enabled;
    message.success($t('admin.ai.agent.memory.saveSuccess'));
  } catch (error) {
    adminMemoryEnabled.value = previous;
    showRequestError(error, 'common.saveFailed');
  } finally {
    memorySaving.value = false;
  }
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initPrompt();
      void loadMemoryConfig();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initPrompt();
      void loadMemoryConfig();
    }
  },
);
</script>

<template>
  <div class="flex flex-col gap-5 p-5 pt-3">
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div class="rounded-xl border bg-accent/30 p-4">
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            icon="lucide:activity"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">{{
            $t('admin.ai.agent.status')
          }}</span>
        </div>
        <Tag :color="getStatusColor(agent.status)" class="!mr-0 !text-xs">
          {{ getStatusText(agent.status) }}
        </Tag>
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            icon="lucide:workflow"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">{{
            $t('admin.ai.agent.executionMode')
          }}</span>
        </div>
        <span class="text-sm font-medium">{{
          getExecutionModeText(agent.execution_mode)
        }}</span>
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            icon="lucide:brain"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">{{
            $t('admin.ai.agent.modelName')
          }}</span>
        </div>
        <span class="text-sm font-medium">{{ agent.model_name || '-' }}</span>
      </div>
      <div class="rounded-xl border bg-accent/30 p-4">
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            icon="lucide:globe"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">{{
            $t('common.scope.label')
          }}</span>
        </div>
        <Tag :color="getScopeColor(agent.scope)" class="!mr-0 !text-xs">
          {{ getScopeText(agent.scope) }}
        </Tag>
      </div>
    </div>

    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="mb-1 flex items-center gap-2">
            <div
              class="flex size-7 items-center justify-center rounded-lg bg-indigo-500/10"
            >
              <IconifyIcon
                icon="lucide:brain-circuit"
                class="size-4 text-indigo-500"
              />
            </div>
            <span class="text-sm font-semibold">{{
              $t('admin.ai.agent.memory.title')
            }}</span>
          </div>
          <p class="text-xs text-muted-foreground">
            {{ $t('admin.ai.agent.memory.desc') }}
          </p>
        </div>
        <Switch
          :checked="adminMemoryEnabled"
          :loading="memorySaving"
          :aria-label="$t('admin.ai.agent.memory.agentSwitch')"
          @change="(val) => updateAdminMemoryEnabled(Boolean(val))"
        />
      </div>
      <Spin :spinning="memoryLoading" class="mt-3 block">
        <div
          v-if="memoryConfig"
          class="grid grid-cols-1 gap-2 text-xs md:grid-cols-3"
        >
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('admin.ai.agent.memory.platformDefault') }}
            </div>
            <div class="mt-1 font-medium">
              {{
                memoryConfig.platform_default_memory_enabled
                  ? $t('admin.ai.agent.memory.enabled')
                  : $t('admin.ai.agent.memory.disabled')
              }}
            </div>
          </div>
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('admin.ai.agent.memory.agentSwitch') }}
            </div>
            <div class="mt-1 font-medium">
              {{
                memoryConfig.admin_agent_memory_enabled
                  ? $t('admin.ai.agent.memory.enabled')
                  : $t('admin.ai.agent.memory.disabled')
              }}
            </div>
          </div>
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('admin.ai.agent.memory.effective') }}
            </div>
            <div
              class="mt-1 font-semibold"
              :class="
                memoryConfig.effective_memory_enabled
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-amber-600 dark:text-amber-400'
              "
            >
              {{
                memoryConfig.effective_memory_enabled
                  ? $t('admin.ai.agent.memory.enabled')
                  : $t('admin.ai.agent.memory.disabled')
              }}
            </div>
          </div>
        </div>
      </Spin>
    </div>

    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="mb-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div
            class="flex size-7 items-center justify-center rounded-lg bg-primary/10"
          >
            <IconifyIcon
              icon="lucide:message-square-code"
              class="size-4 text-primary"
            />
          </div>
          <span class="text-sm font-semibold">{{
            $t('admin.ai.agent.systemPrompt')
          }}</span>
        </div>
        <Button
          v-if="!editingPrompt"
          size="small"
          type="link"
          @click="editingPrompt = true"
        >
          <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
          {{ $t('common.edit') }}
        </Button>
        <div v-else class="flex gap-2">
          <Button size="small" @click="initPrompt">
            {{ $t('common.cancel') }}
          </Button>
          <Button
            size="small"
            type="primary"
            :loading="saving"
            @click="savePrompt"
          >
            {{ $t('common.save') }}
          </Button>
        </div>
      </div>
      <div
        v-if="!editingPrompt"
        class="min-h-[60px] whitespace-pre-wrap text-sm leading-relaxed text-foreground"
      >
        {{ agent.system_prompt || '-' }}
      </div>
      <Textarea v-else v-model:value="promptDraft" :rows="8" class="w-full" />
    </div>
  </div>
</template>
