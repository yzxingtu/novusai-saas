<script lang="ts" setup>
/**
 * 企业端智能体新建/编辑表单抽屉 / Tenant agent create/edit form drawer
 * 支持向导模式（新建）和经典模式（编辑）
 */
import type {
  AgentInfo,
  AgentListItem,
  AgentSkillGrantInfo,
} from '#/api/tenant/agents';

import { computed, nextTick, ref } from 'vue';
import { useRouter } from 'vue-router';

import {
  Button as AButton,
  Steps as ASteps,
  Tag as ATag,
} from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getAgentDetailApi, getAgentSkillsApi } from '#/api/tenant/agents';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';

import {
  getFormDefaults,
  getWizardSteps,
  getWizardStepSchema,
  useFormSchema,
} from '../data';

defineOptions({ name: 'TenantAgentForm' });

const emits = defineEmits<{ success: [] }>();
const router = useRouter();

const AStep = ASteps.Step;

const TOTAL_STEPS = 2;

const wizardMode = ref(false);
const currentStep = ref(0);
const grantedSkills = ref<AgentSkillGrantInfo[]>([]);
const modelMaxOutputTokensMap = ref<Record<number, number | undefined>>({});

function resolveModelMaxOutputTokens(
  modelId: null | number | undefined,
): number | undefined {
  if (modelId === null || modelId === undefined) return undefined;
  return modelMaxOutputTokensMap.value[modelId];
}

function buildSchema(isCreate = false) {
  return useFormSchema(isCreate, resolveModelMaxOutputTokens);
}

function buildWizardStepSchema(step: number) {
  return getWizardStepSchema(step, resolveModelMaxOutputTokens);
}

const [Form, formApi] = useVbenForm({
  schema: buildSchema(),
  showDefaultActions: false,
});

function goStep(step: number) {
  currentStep.value = step;
  formApi.setState({ schema: buildWizardStepSchema(step) });
}

function prevStep() {
  if (currentStep.value > 0) goStep(currentStep.value - 1);
}

function nextStep() {
  if (currentStep.value < TOTAL_STEPS - 1) goStep(currentStep.value + 1);
}

const wizardSteps = computed(() => getWizardSteps());

const {
  Drawer,
  isEdit,
  recordId,
  openNew: _openNew,
  openEdit: _openEdit,
} = useCrudDrawer<AgentInfo>({
  formApi,
  schema: (edit) => buildSchema(!edit),
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/agents',
  transform: (values) => {
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
      suggested_questions: parseStarterQuestionsInput(
        values.suggested_questions_str,
      ),
    };
  },
  toFormValues: (data) => {
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
      suggested_questions_str: formatStarterQuestionsInput(
        data.suggested_questions as null | unknown[],
      ),
    };
  },
  onSuccess: async () => {
    emits('success');
    const agentId = recordId.value as number | undefined;
    if (!isEdit.value && agentId) {
      await router.push(`/tenant/ai/agents/${agentId}`);
    }
  },
  detailApi: async (id) => {
    const agent = await getAgentDetailApi(id as number);
    try {
      grantedSkills.value = await getAgentSkillsApi(id as number);
    } catch {
      grantedSkills.value = [];
    }
    return agent;
  },
});

async function openNew(extraData?: Record<string, unknown>) {
  wizardMode.value = true;
  currentStep.value = 0;
  _openNew(extraData);
  await nextTick();
  formApi.setState({ schema: buildWizardStepSchema(0) });
}

function openEdit(record: AgentListItem, extraData?: Record<string, unknown>) {
  wizardMode.value = false;
  formApi.setState({ schema: buildSchema() });
  _openEdit(record, extraData);
}

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value ? $t('common.edit') : $t('tenant.ai.agent.create'),
);

const isLastStep = computed(() => currentStep.value === TOTAL_STEPS - 1);
const isFirstStep = computed(() => currentStep.value === 0);

async function loadModelLimits() {
  try {
    const models = await getTenantAIModelsApi();
    const next: Record<number, number | undefined> = {};
    for (const item of models) {
      next[item.id] = item.max_output_tokens ?? undefined;
    }
    modelMaxOutputTokensMap.value = next;
    formApi.setState({
      schema: wizardMode.value
        ? buildWizardStepSchema(currentStep.value)
        : buildSchema(!isEdit.value),
    });
  } catch {
    modelMaxOutputTokensMap.value = {};
  }
}

void loadModelLimits();
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

    <!-- Skill grants (read-only, shown in edit mode) -->
    <div v-if="isEdit && grantedSkills.length > 0" class="mb-5">
      <div class="mb-2 text-sm font-medium text-foreground">
        {{ $t('tenant.ai.agent.skillBindings') }}
      </div>
      <div class="space-y-2">
        <div
          v-for="skill in grantedSkills"
          :key="`skill-${skill.skill_id}`"
          class="flex items-center gap-2 rounded-md border border-border px-3 py-2"
        >
          <span class="min-w-0 flex-1 truncate text-sm font-medium">{{
            skill.skill_name || `#${skill.skill_id}`
          }}</span>
          <ATag
            v-if="skill.package_name"
            color="blue"
            class="!m-0 shrink-0 !text-[10px]"
          >
            {{ skill.package_name }}
          </ATag>
          <ATag
            :color="
              skill.default_consent_mode === 'auto'
                ? 'green'
                : skill.default_consent_mode === 'ask'
                  ? 'orange'
                  : 'red'
            "
            class="!m-0 shrink-0 !text-[10px]"
          >
            {{
              $t(
                `tenant.ai.agent.consentModeOptions.${skill.default_consent_mode}`,
              )
            }}
          </ATag>
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
