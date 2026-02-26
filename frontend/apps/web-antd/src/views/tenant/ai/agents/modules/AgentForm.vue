<script lang="ts" setup>
defineOptions({ name: 'TenantAgentForm' });
/**
 * 租户端智能体新建/编辑表单抽屉
 * 支持向导模式（新建）和经典模式（编辑）
 */
import type { AgentInfo, AgentListItem, AgentSkillBindingInfo } from '#/api/tenant/agents';

import { computed, onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useVbenForm } from '#/adapter/form';
import {
  batchBindPackagesApi,
  getAgentDetailApi,
  getAgentSkillsApi,
} from '#/api/tenant/agents';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { Button as AButton, Select as ASelect, Steps as ASteps, Tag as ATag } from 'ant-design-vue';

const AStep = ASteps.Step;

import {
  getFormDefaults,
  getPackageSelectOptions,
  getWizardSteps,
  useFormSchema,
  useWizardFormSchema,
} from '../data';

const TOTAL_STEPS = 2;

const emits = defineEmits<{ success: [] }>();

const wizardMode = ref(false);
const currentStep = ref(0);
const pendingPackageIds = ref<number[]>([]);
const consentModes = ref<Record<string, string>>({});
const selectedPackages = ref<Array<{ label: string; value: number }>>([]); 
const autoBindPackages = ref<AgentSkillBindingInfo[]>([]);

interface TenantPkgOption {
  label: string;
  value: number;
  scope?: string;
  source_plugin?: string;
}
const tenantPackageOptions = ref<TenantPkgOption[]>([]);
const tenantPackageLoading = ref(false);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
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
      suggested_questions_str: toJsonArrayString(data.suggested_questions as unknown[] | null),
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
      const autoBind: AgentSkillBindingInfo[] = [];
      const manualBind: AgentSkillBindingInfo[] = [];
      for (const b of bindings) {
        if (b.is_auto_bound) {
          autoBind.push(b);
        } else {
          manualBind.push(b);
        }
      }
      autoBindPackages.value = autoBind;

      const manualOptions = manualBind.map((b) => ({
        label: b.package_name || `#${b.package_id}`,
        value: b.package_id,
      }));
      const modes: Record<string, string> = {};
      for (const b of manualBind) {
        if (b.consent_mode && b.consent_mode !== 'auto') {
          modes[String(b.package_id)] = b.consent_mode;
        }
      }
      consentModes.value = modes;
      selectedPackages.value = manualOptions;
      pendingPackageIds.value = manualOptions.map((p) => p.value);
    } catch {
      autoBindPackages.value = [];
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

async function loadTenantPackageOptions() {
  tenantPackageLoading.value = true;
  try {
    tenantPackageOptions.value = await getPackageSelectOptions() as TenantPkgOption[];
  } finally {
    tenantPackageLoading.value = false;
  }
}

onMounted(loadTenantPackageOptions);

// Filter out auto-bound packages from the manual selection dropdown
const manualTenantPackageOptions = computed(() => {
  const autoIds = new Set(autoBindPackages.value.map((b) => b.package_id));
  return tenantPackageOptions.value.filter((p) => !autoIds.has(p.value));
});

function onTenantPackageChange(val: unknown) {
  const raw = (val || []) as Array<unknown>;
  const items = raw.map((item) => {
    if (typeof item === 'object' && item !== null) {
      const obj = item as Record<string, unknown>;
      return { label: String(obj.label || ''), value: Number(obj.value || obj.key || 0) };
    }
    return { label: `#${item}`, value: Number(item) };
  });
  selectedPackages.value = items;
  pendingPackageIds.value = items.map((p) => p.value);
  formApi.setValues({ package_ids: items });
}
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

    <!-- Skill package binding (unified: auto-bind + manual + consent mode) -->
    <div class="mb-5">
      <div class="mb-2 text-sm font-medium text-foreground">
        {{ $t('tenant.ai.agent.skillPackageBindings') }}
      </div>
      <ASelect
        :value="selectedPackages"
        mode="multiple"
        label-in-value
        :loading="tenantPackageLoading"
        :options="manualTenantPackageOptions"
        :placeholder="$t('tenant.ai.agent.placeholder.selectSkillPackages')"
        show-search
        option-filter-prop="label"
        class="w-full"
        @change="onTenantPackageChange"
      />

      <!-- Unified binding list: auto-bind + manual, each with consent mode -->
      <div v-if="autoBindPackages.length > 0 || selectedPackages.length > 0" class="mt-3 space-y-2">
        <!-- Auto-bind packages (locked, with consent mode) -->
        <div
          v-for="pkg in autoBindPackages"
          :key="`auto-${pkg.package_id}`"
          class="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2"
        >
          <IconifyIcon icon="lucide:lock" class="size-3.5 shrink-0 text-primary/60" />
          <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ pkg.package_name }}</span>
          <ATag v-if="pkg.package_is_system" color="red" class="!m-0 shrink-0 !text-[10px]">
            {{ $t('tenant.ai.skillPackage.system') }}
          </ATag>
          <ATag v-if="pkg.package_scope" :color="getScopeColor(pkg.package_scope)" class="!m-0 shrink-0 !text-[10px]">
            {{ getScopeText(pkg.package_scope) }}
          </ATag>
          <ATag color="green" class="!m-0 shrink-0 !text-[10px]">
            {{ $t('tenant.ai.agent.consentModeOptions.auto') }}
          </ATag>
        </div>

        <!-- Manual-bind packages (with consent mode) -->
        <div
          v-for="pkg in selectedPackages"
          :key="`manual-${pkg.value}`"
          class="flex items-center gap-2 rounded-md border border-border px-3 py-2"
        >
          <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ pkg.label }}</span>
          <ASelect
            :value="getConsentMode(pkg.value)"
            :options="consentModeOptions"
            size="small"
            class="w-[120px] shrink-0"
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
