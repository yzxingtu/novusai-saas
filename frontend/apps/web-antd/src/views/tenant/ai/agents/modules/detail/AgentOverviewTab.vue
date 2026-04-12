<script lang="ts" setup>
import type { AgentInfo, AgentMemoryConfig } from '#/api/tenant/agents';

import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Spin, Switch, Tag, Textarea, message } from 'ant-design-vue';

import {
  getAgentMemoryConfigApi,
  updateAgentMemoryConfigApi,
} from '#/api/tenant/agents';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

import { getExecutionModeText, getStatusColor, getStatusText } from '../../data';

const props = defineProps<{
  agent: AgentInfo;
  agentId: number;
  saving: boolean;
  active: boolean;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
}>();

const editingPrompt = ref(false);
const promptDraft = ref('');

const memoryLoading = ref(false);
const memorySaving = ref(false);
const memoryConfig = ref<AgentMemoryConfig | null>(null);
const tenantMemoryDisabled = ref(false);

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
    memoryConfig.value = await getAgentMemoryConfigApi(props.agentId);
    tenantMemoryDisabled.value =
      memoryConfig.value.tenant_agent_memory_disabled;
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
  } finally {
    memoryLoading.value = false;
  }
}

async function updateTenantMemoryDisabled(disabled: boolean) {
  if (!props.isTenantOwned) return;
  const previous = tenantMemoryDisabled.value;
  tenantMemoryDisabled.value = disabled;
  memorySaving.value = true;
  try {
    memoryConfig.value = await updateAgentMemoryConfigApi(props.agentId, {
      disabled,
    });
    tenantMemoryDisabled.value =
      memoryConfig.value.tenant_agent_memory_disabled;
    message.success($t('tenant.ai.agent.memory.saveSuccess'));
  } catch (error) {
    tenantMemoryDisabled.value = previous;
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
    <div class="grid grid-cols-2 gap-3 md:grid-cols-3">
      <div class="rounded-xl border bg-accent/30 p-4">
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            icon="lucide:activity"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">{{
            $t('tenant.ai.agent.status')
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
            $t('tenant.ai.agent.executionMode')
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
            $t('tenant.ai.agent.modelName')
          }}</span>
        </div>
        <span class="text-sm font-medium">{{ agent.model_code || '-' }}</span>
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
              $t('tenant.ai.agent.memory.title')
            }}</span>
          </div>
          <p class="text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.memory.desc') }}
          </p>
          <p v-if="!isTenantOwned" class="mt-1 text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.memory.readonlyHint') }}
          </p>
        </div>
        <Switch
          :checked="tenantMemoryDisabled"
          :loading="memorySaving"
          :disabled="!isTenantOwned"
          :aria-label="$t('tenant.ai.agent.memory.tenantSwitch')"
          @change="(val) => updateTenantMemoryDisabled(Boolean(val))"
        />
      </div>
      <Spin :spinning="memoryLoading" class="mt-3 block">
        <div
          v-if="memoryConfig"
          class="grid grid-cols-1 gap-2 text-xs md:grid-cols-4"
        >
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('tenant.ai.agent.memory.platformDefault') }}
            </div>
            <div class="mt-1 font-medium">
              {{
                memoryConfig.platform_default_memory_enabled
                  ? $t('tenant.ai.agent.memory.enabled')
                  : $t('tenant.ai.agent.memory.disabled')
              }}
            </div>
          </div>
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('tenant.ai.agent.memory.adminSwitch') }}
            </div>
            <div class="mt-1 font-medium">
              {{
                memoryConfig.admin_agent_memory_enabled
                  ? $t('tenant.ai.agent.memory.enabled')
                  : $t('tenant.ai.agent.memory.disabled')
              }}
            </div>
          </div>
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('tenant.ai.agent.memory.tenantSwitch') }}
            </div>
            <div class="mt-1 font-medium">
              {{
                memoryConfig.tenant_agent_memory_disabled
                  ? $t('tenant.ai.agent.memory.disabled')
                  : $t('tenant.ai.agent.memory.enabled')
              }}
            </div>
          </div>
          <div class="rounded-lg border bg-background px-3 py-2">
            <div class="text-muted-foreground">
              {{ $t('tenant.ai.agent.memory.effective') }}
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
                  ? $t('tenant.ai.agent.memory.enabled')
                  : $t('tenant.ai.agent.memory.disabled')
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
            $t('tenant.ai.agent.systemPrompt')
          }}</span>
        </div>
        <Button
          v-if="!editingPrompt && isTenantOwned"
          size="small"
          type="link"
          @click="editingPrompt = true"
        >
          <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
          {{ $t('common.edit') }}
        </Button>
        <div v-else-if="editingPrompt" class="flex gap-2">
          <Button size="small" @click="initPrompt">
            {{ $t('common.cancel') }}
          </Button>
          <Button size="small" type="primary" :loading="saving" @click="savePrompt">
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
