<script lang="ts" setup>
defineOptions({ name: 'TenantAgentForm' });
/**
 * 租户端智能体新建/编辑表单抽屉
 * 支持向导模式（新建）和经典模式（编辑）
 */
import type { AgentInfo, AgentListItem } from '#/api/tenant/agents';

interface AgentDetailWithBindings extends AgentInfo {
  _package_options?: { label: string; value: number }[];
}

import { computed, ref } from 'vue';

import { useVbenForm } from '#/adapter/form';
import {
  batchBindPackagesApi,
  getAgentDetailApi,
  getAgentSkillsApi,
} from '#/api/tenant/agents';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { Button as AButton, Select as ASelect, Steps as ASteps } from 'ant-design-vue';

const AStep = ASteps.Step;

import {
  getFormDefaults,
  getWizardSteps,
  useFormSchema,
  useWizardFormSchema,
} from '../data';

const TOTAL_STEPS = 4;

const emits = defineEmits<{ success: [] }>();

const wizardMode = ref(false);
const currentStep = ref(0);
const pendingPackageIds = ref<number[]>([]);
const consentModes = ref<Record<string, string>>({});
const selectedPackages = ref<Array<{ label: string; value: number }>>([]);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
  handleValuesChange: (values, changedFields) => {
    if (changedFields.includes('package_ids')) {
      const rawPkgIds = values.package_ids as Array<number | { label: string; value: number }>;
      if (rawPkgIds) {
        selectedPackages.value = rawPkgIds.map((p: number | { label: string; value: number }) =>
          typeof p === 'object' && p !== null ? p : { label: `#${p}`, value: p as number },
        );
      } else {
        selectedPackages.value = [];
      }
    }
  },
});

function goStep(step: number) {
  currentStep.value = step;
  formApi.setValues({ _wizard_step: step });
}

function prevStep() {
  if (currentStep.value > 0) goStep(currentStep.value - 1);
}

function nextStep() {
  if (currentStep.value < TOTAL_STEPS - 1) goStep(currentStep.value + 1);
}

const wizardSteps = computed(() => getWizardSteps());

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

const { Drawer, isEdit, recordId, openNew: _openNew, openEdit: _openEdit } = useCrudDrawer<AgentInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/agents',
  transform: (values) => {
    const rawPkgIds = values.package_ids as Array<number | { label: string; value: number }>;
    const resolved = (rawPkgIds || []).map((p) =>
      typeof p === 'object' && p !== null ? p.value : p,
    );
    pendingPackageIds.value = resolved;
    selectedPackages.value = (rawPkgIds || []).map((p) =>
      typeof p === 'object' && p !== null ? p : { label: `#${p}`, value: p as number },
    );
    return {
      name: values.name,
      avatar: values.avatar || null,
      model_id: values.model_id,
      execution_mode: values.execution_mode,
      system_prompt: values.system_prompt,
      description: values.description || null,
      temperature: values.temperature ?? 0.7,
      max_tokens: values.max_tokens || null,
      top_p: values.top_p ?? null,
      welcome_message: values.welcome_message || null,
      suggested_questions: safeJsonArrayParse(values.suggested_questions_str),
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
      avatar: data.avatar || '',
      model_id: data.model_id,
      execution_mode: data.execution_mode,
      system_prompt: data.system_prompt,
      description: data.description,
      temperature: data.temperature,
      max_tokens: data.max_tokens,
      top_p: data.top_p,
      welcome_message: data.welcome_message,
      suggested_questions_str: toJsonArrayString(data.suggested_questions as unknown[] | null),
      input_variables_str: toJsonArrayString(data.input_variables as unknown[] | null),
      context_max_history_messages: cc.max_history_messages ?? 20,
      context_max_history_tokens: cc.max_history_tokens ?? 0,
      package_ids: (data as AgentDetailWithBindings)._package_options || [],
      quota_conversations_per_day: qc.conversations_per_day ?? 0,
      quota_tokens_per_day: qc.daily_token_limit ?? 0,
      quota_tokens_per_month: qc.monthly_token_limit ?? 0,
      quota_max_turns: qc.max_turns_per_conversation ?? 50,
      quota_max_concurrent: qc.max_concurrent ?? 10,
      quota_user_conversations_per_day: qc.user_conversations_per_day ?? 0,
    };
  },
  onSuccess: async () => {
    const agentId = recordId.value as number | undefined;
    if (agentId && pendingPackageIds.value.length >= 0) {
      try {
        await batchBindPackagesApi(
          agentId,
          pendingPackageIds.value,
          Object.keys(consentModes.value).length > 0
            ? consentModes.value
            : undefined,
        );
      } catch {
        // package binding errors are non-fatal
      }
    }
    emits('success');
  },
  detailApi: async (id) => {
    const agent = await getAgentDetailApi(id as number);
    try {
      const bindings = await getAgentSkillsApi(id as number);
      (agent as AgentDetailWithBindings)._package_options = bindings.map((b) => ({
        label: b.package?.name || `#${b.package_id}`,
        value: b.package_id,
      }));
      const modes: Record<string, string> = {};
      for (const b of bindings) {
        if (b.consent_mode && b.consent_mode !== 'auto') {
          modes[String(b.package_id)] = b.consent_mode;
        }
      }
      consentModes.value = modes;
      selectedPackages.value = (agent as AgentDetailWithBindings)._package_options!;
    } catch {
      (agent as AgentDetailWithBindings)._package_options = [];
    }
    return agent;
  },
});

function openNew() {
  wizardMode.value = true;
  currentStep.value = 0;
  formApi.setState({ schema: useWizardFormSchema() });
  _openNew();
  setTimeout(() => formApi.setValues({ _wizard_step: 0 }), 50);
}

function openEdit(record: AgentListItem) {
  wizardMode.value = false;
  formApi.setState({ schema: useFormSchema() });
  _openEdit(record);
}

defineExpose({ openNew, openEdit });

const consentModeOptions = computed(() => [
  { label: $t('tenant.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('tenant.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('tenant.ai.agent.consentModeOptions.reject'), value: 'reject' },
]);

function getConsentMode(pkgId: number): string {
  return consentModes.value[String(pkgId)] || 'auto';
}

function setConsentMode(pkgId: number, mode: string) {
  if (mode === 'auto') {
    const { [String(pkgId)]: _, ...rest } = consentModes.value;
    consentModes.value = rest;
  } else {
    consentModes.value = { ...consentModes.value, [String(pkgId)]: mode };
  }
}


const title = computed(() =>
  isEdit.value
    ? $t('common.edit')
    : $t('tenant.ai.agent.create'),
);

const isLastStep = computed(() => currentStep.value === TOTAL_STEPS - 1);
const isFirstStep = computed(() => currentStep.value === 0);
</script>

<template>
  <Drawer :title="title" class="w-[640px]">
    <div v-if="wizardMode" class="mb-6">
      <ASteps :current="currentStep" size="small">
        <AStep
          v-for="(step, idx) in wizardSteps"
          :key="idx"
          :title="step.title"
          :description="step.description"
        />
      </ASteps>
    </div>
    <Form />

    <!-- Consent mode per skill package -->
    <div v-if="selectedPackages.length > 0" class="mt-4">
      <div class="mb-2 text-sm font-medium text-foreground">
        {{ $t('tenant.ai.agent.consentMode') }}
      </div>
      <div class="space-y-2">
        <div
          v-for="pkg in selectedPackages"
          :key="pkg.value"
          class="flex items-center gap-3 rounded-md border border-border px-3 py-2"
        >
          <span class="flex-1 truncate text-sm">{{ pkg.label }}</span>
          <ASelect
            :value="getConsentMode(pkg.value)"
            :options="consentModeOptions"
            size="small"
            class="w-[140px]"
            @change="(v: unknown) => setConsentMode(pkg.value, v as string)"
          />
        </div>
      </div>
    </div>
    <div v-if="wizardMode" class="mt-4 flex justify-between">
      <AButton :disabled="isFirstStep" @click="prevStep">
        {{ $t('shared.common.prevStep') }}
      </AButton>
      <AButton v-if="!isLastStep" type="primary" @click="nextStep">
        {{ $t('shared.common.nextStep') }}
      </AButton>
    </div>
  </Drawer>
</template>
