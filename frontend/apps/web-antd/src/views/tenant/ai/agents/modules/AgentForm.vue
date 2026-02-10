<script lang="ts" setup>
defineOptions({ name: 'TenantAgentForm' });
/**
 * 租户端智能体新建/编辑表单抽屉
 */
import type { AgentInfo } from '#/api/tenant/agents';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getAgentDetailApi } from '#/api/tenant/agents';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

/**
 * 安全解析 JSON 数组字符串
 */
function safeJsonArrayParse(str: string | undefined): unknown[] | null {
  if (!str || str.trim() === '' || str.trim() === '[]') return null;
  try {
    const parsed = JSON.parse(str);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * 数组转 JSON 字符串（美化格式）
 */
function toJsonArrayString(arr: unknown[] | null | undefined): string {
  if (!arr || arr.length === 0) return '[]';
  return JSON.stringify(arr, null, 2);
}

const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<AgentInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/agents',
  transform: (values) => {
    return {
      name: values.name,
      model_id: values.model_id,
      execution_mode: values.execution_mode,
      system_prompt: values.system_prompt,
      description: values.description || null,
      temperature: values.temperature ?? 0.7,
      max_tokens: values.max_tokens || null,
      top_p: values.top_p ?? null,
      welcome_message: values.welcome_message || null,
      suggested_questions: safeJsonArrayParse(values.suggested_questions_str),
      tool_bindings: safeJsonArrayParse(values.tool_bindings_str),
      input_variables: safeJsonArrayParse(values.input_variables_str),
      context_config: {
        max_history_messages: values.context_max_history_messages ?? 20,
        max_history_tokens: values.context_max_history_tokens ?? 0,
      },
      quota_config: {
        conversations_per_day: values.quota_conversations_per_day ?? 0,
        daily_token_limit: values.quota_tokens_per_day ?? 0,
        monthly_token_limit: values.quota_tokens_per_month ?? 0,
        max_turns_per_conversation: values.quota_max_turns ?? 50,
        max_concurrent: values.quota_max_concurrent ?? 10,
        user_conversations_per_day: values.quota_user_conversations_per_day ?? 0,
      },
    };
  },
  toFormValues: (data) => {
    const qc = (data.quota_config ?? {}) as Record<string, number>;
    const cc = (data.context_config ?? {}) as Record<string, number>;
    return {
      name: data.name,
      model_id: data.model_id,
      execution_mode: data.execution_mode,
      system_prompt: data.system_prompt,
      description: data.description,
      temperature: data.temperature,
      max_tokens: data.max_tokens,
      top_p: data.top_p,
      welcome_message: data.welcome_message,
      suggested_questions_str: toJsonArrayString(data.suggested_questions as unknown[] | null),
      tool_bindings_str: toJsonArrayString(data.tool_bindings as unknown[] | null),
      input_variables_str: toJsonArrayString(data.input_variables as unknown[] | null),
      context_max_history_messages: cc.max_history_messages ?? 20,
      context_max_history_tokens: cc.max_history_tokens ?? 0,
      quota_conversations_per_day: qc.conversations_per_day ?? 0,
      quota_tokens_per_day: qc.daily_token_limit ?? 0,
      quota_tokens_per_month: qc.monthly_token_limit ?? 0,
      quota_max_turns: qc.max_turns_per_conversation ?? 50,
      quota_max_concurrent: qc.max_concurrent ?? 10,
      quota_user_conversations_per_day: qc.user_conversations_per_day ?? 0,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: async (id) => {
    return await getAgentDetailApi(id as number);
  },
});

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value
    ? $t('common.edit')
    : $t('tenant.ai.agent.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[640px]">
    <Form />
  </Drawer>
</template>
