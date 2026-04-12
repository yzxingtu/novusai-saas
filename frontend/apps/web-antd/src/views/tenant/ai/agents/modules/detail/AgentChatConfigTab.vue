<script lang="ts" setup>
import type { AgentInfo } from '#/api/tenant/agents';
import type { InputVariable } from '#/types/ai-chat';

import { nextTick, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, InputNumber, Switch, Textarea } from 'ant-design-vue';

import InputVariablesEditor from '#/components/business/input-variables-editor/InputVariablesEditor.vue';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';

const props = defineProps<{
  agent: AgentInfo;
  saving: boolean;
  active: boolean;
  isTenantOwned: boolean;
  onSaveFields: (fields: Record<string, unknown>) => Promise<void>;
}>();

const chatWelcome = ref('');
const chatSuggestions = ref('');
const chatInputVars = ref<InputVariable[]>([]);
const chatSystemPrompt = ref('');
const chatContextMessages = ref(20);
const chatContextTokens = ref(0);
const chatLongTermMemoryEnabled = ref(false);
const chatSystemPromptRef = ref<HTMLTextAreaElement | null>(null);

function formatVarChip(name: string) {
  return `{{${name}}}`;
}

function insertVarAtCursor(varName: string) {
  const el = chatSystemPromptRef.value;
  const token = `{{${varName}}}`;
  if (!el) {
    chatSystemPrompt.value += token;
    return;
  }
  const start = el.selectionStart ?? chatSystemPrompt.value.length;
  const end = el.selectionEnd ?? start;
  chatSystemPrompt.value =
    chatSystemPrompt.value.slice(0, Math.max(0, start)) +
    token +
    chatSystemPrompt.value.slice(Math.max(0, end));
  nextTick(() => {
    el.focus();
    const newPos = start + token.length;
    el.setSelectionRange(newPos, newPos);
  });
}

function initChatConfig() {
  chatSystemPrompt.value = props.agent.system_prompt || '';
  chatWelcome.value = props.agent.welcome_message || '';
  const sq = props.agent.suggested_questions;
  chatSuggestions.value = formatStarterQuestionsInput(sq as null | unknown[]);
  chatInputVars.value = Array.isArray(props.agent.input_variables)
    ? (props.agent.input_variables as InputVariable[])
    : [];
  const cc = (props.agent.context_config ?? {}) as Record<string, unknown>;
  chatContextMessages.value =
    typeof cc.max_history_messages === 'number' ? cc.max_history_messages : 20;
  chatContextTokens.value =
    typeof cc.max_history_tokens === 'number' ? cc.max_history_tokens : 0;
  chatLongTermMemoryEnabled.value = Boolean(cc.long_term_memory_enabled);
}

function buildMergedContextConfig(): Record<string, unknown> {
  const prev = (props.agent.context_config ?? {}) as Record<string, unknown>;
  return {
    ...prev,
    max_history_messages: chatContextMessages.value,
    max_history_tokens: chatContextTokens.value,
    long_term_memory_enabled: chatLongTermMemoryEnabled.value,
  };
}

async function saveChatConfig() {
  if (!props.isTenantOwned) return;
  await props.onSaveFields({
    ...(props.isTenantOwned ? { system_prompt: chatSystemPrompt.value || null } : {}),
    welcome_message: chatWelcome.value || null,
    suggested_questions: parseStarterQuestionsInput(chatSuggestions.value),
    input_variables: chatInputVars.value.length > 0 ? chatInputVars.value : null,
    context_config: buildMergedContextConfig(),
  });
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      initChatConfig();
    }
  },
  { immediate: true },
);

watch(
  () => props.agent.id,
  () => {
    if (props.active) {
      initChatConfig();
    }
  },
);
</script>

<template>
  <div class="flex flex-col gap-4 p-5 pt-3">
    <div class="rounded-xl border border-primary/20 bg-primary/5 p-4">
      <div class="mb-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <IconifyIcon
            icon="lucide:message-square-code"
            class="size-4 text-primary"
          />
          <label class="text-sm font-semibold text-primary">{{
            $t('tenant.ai.agent.systemPrompt')
          }}</label>
        </div>
        <span
          v-if="!isTenantOwned"
          class="rounded-full bg-primary/10 px-2 py-px text-[10px] text-primary"
          >{{ $t('tenant.ai.agent.readonlyHint') }}</span
        >
      </div>
      <div v-if="chatInputVars.length > 0" class="mb-2 flex flex-wrap gap-1.5">
        <span class="text-xs text-muted-foreground"
          >{{ $t('tenant.ai.agent.detail.chatConfigPromptHint') }}:</span
        >
        <button
          v-for="v in chatInputVars"
          :key="v.name"
          :disabled="!isTenantOwned"
          class="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          @click="insertVarAtCursor(v.name)"
        >
          <span v-text="formatVarChip(v.name)"></span>
        </button>
      </div>
      <Textarea
        :ref="(el) => (chatSystemPromptRef.value = el as HTMLTextAreaElement | null)"
        v-model:value="chatSystemPrompt"
        :rows="6"
        :disabled="!isTenantOwned"
        :placeholder="$t('tenant.ai.agent.placeholder.inputSystemPrompt')"
        class="w-full text-xs"
      />
    </div>
    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="mb-3 flex items-center gap-2">
        <div class="flex size-7 items-center justify-center rounded-lg bg-green-500/10">
          <IconifyIcon icon="lucide:smile" class="size-4 text-green-500" />
        </div>
        <label class="text-sm font-medium">{{
          $t('tenant.ai.agent.welcomeMessage')
        }}</label>
      </div>
      <Textarea
        v-model:value="chatWelcome"
        :rows="3"
        :disabled="!isTenantOwned"
        :placeholder="$t('tenant.ai.agent.placeholder.inputWelcomeMessage')"
        class="w-full"
      />
    </div>
    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="mb-3 flex items-center gap-2">
        <div class="flex size-7 items-center justify-center rounded-lg bg-cyan-500/10">
          <IconifyIcon icon="lucide:help-circle" class="size-4 text-cyan-500" />
        </div>
        <label class="text-sm font-medium">{{
          $t('tenant.ai.agent.suggestedQuestions')
        }}</label>
      </div>
      <Textarea
        v-model:value="chatSuggestions"
        :rows="4"
        :disabled="!isTenantOwned"
        :placeholder="$t('tenant.ai.agent.placeholder.inputSuggestedQuestions')"
        class="w-full font-mono text-xs"
      />
      <p class="mt-1 text-xs text-muted-foreground">JSON</p>
    </div>
    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="mb-3 flex items-center gap-2">
        <div class="flex size-7 items-center justify-center rounded-lg bg-violet-500/10">
          <IconifyIcon icon="lucide:variable" class="size-4 text-violet-500" />
        </div>
        <label class="text-sm font-medium">{{
          $t('tenant.ai.agent.inputVariables.title')
        }}</label>
      </div>
      <InputVariablesEditor v-model="chatInputVars" :disabled="!isTenantOwned" />
    </div>
    <div class="rounded-xl border bg-accent/30 p-5">
      <div class="mb-3 flex items-center gap-2">
        <div class="flex size-7 items-center justify-center rounded-lg bg-amber-500/10">
          <IconifyIcon icon="lucide:history" class="size-4 text-amber-500" />
        </div>
        <label class="text-sm font-medium">{{
          $t('tenant.ai.agent.contextConfig.title')
        }}</label>
      </div>
      <div
        class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/60 bg-background/50 px-3 py-2"
      >
        <div class="min-w-0">
          <div class="text-sm font-medium">
            {{ $t('tenant.ai.agent.contextConfig.longTermMemoryEnabled') }}
          </div>
          <p class="mt-0.5 text-xs text-muted-foreground">
            {{ $t('tenant.ai.agent.contextConfig.longTermMemoryHint') }}
          </p>
        </div>
        <Switch v-model:checked="chatLongTermMemoryEnabled" :disabled="!isTenantOwned" />
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1 block text-xs text-muted-foreground">{{
            $t('tenant.ai.agent.contextConfig.maxHistoryMessages')
          }}</label>
          <InputNumber
            v-model:value="chatContextMessages"
            :min="0"
            :disabled="!isTenantOwned"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs text-muted-foreground">{{
            $t('tenant.ai.agent.contextConfig.maxHistoryTokens')
          }}</label>
          <InputNumber
            v-model:value="chatContextTokens"
            :min="0"
            :disabled="!isTenantOwned"
            class="w-full"
          />
        </div>
      </div>
    </div>
    <div v-if="isTenantOwned">
      <Button type="primary" :loading="saving" @click="saveChatConfig">
        {{ $t('common.save') }}
      </Button>
    </div>
  </div>
</template>
