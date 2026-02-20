<script lang="ts" setup>
defineOptions({ name: 'AdminAgentForm' });
/**
 * 管理端智能体新建/编辑表单抽屉
 *
 * 系统智能体编辑时锁定核心字段（name / scope / execution_mode），
 * 仅允许修改调优参数（model_id / system_prompt / temperature / max_tokens）。
 */
import type { AIAgentInfo } from '#/api/admin/ai';

import { computed, ref } from 'vue';

import { useVbenForm } from '#/adapter/form';
import {
  batchBindAIAgentSkillsApi,
  getAIAgentDetailApi,
  getAIAgentSkillsApi,
} from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { Alert, Select as ASelect } from 'ant-design-vue';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const isSystemAgent = ref(false);
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

const { Drawer, isEdit, recordId, rowData, openNew, openEdit } = useCrudDrawer<AIAgentInfo>({
  formApi,
  apiPath: '/admin/ai/agents',
  schema: (edit) => useFormSchema(edit, isSystemAgent.value),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const rawPkgIds = values.package_ids as Array<number | { label: string; value: number }>;
    const resolved = (rawPkgIds || []).map((p) =>
      typeof p === 'object' && p !== null ? p.value : p,
    );
    pendingPackageIds.value = resolved;
    selectedPackages.value = (rawPkgIds || []).map((p) =>
      typeof p === 'object' && p !== null ? p : { label: `#${p}`, value: p as number },
    );
    // suggested_questions: newline-separated text → JSON array
    const sqText = (values.suggested_questions as string) || '';
    const sqArray = sqText
      .split('\n')
      .map((s: string) => s.trim())
      .filter((s: string) => s.length > 0);

    const result: Record<string, unknown> = {
      avatar: values.avatar || null,
      description: values.description || null,
      model_id: values.model_id,
      system_prompt: values.system_prompt || null,
      temperature: values.temperature,
      max_tokens: values.max_tokens,
      welcome_message: values.welcome_message || null,
      suggested_questions: sqArray.length > 0 ? sqArray : null,
    };
    if (!edit || !isSystemAgent.value) {
      result.name = values.name;
      result.scope = values.scope;
      result.execution_mode = values.execution_mode;
      result.tenant_id = values.scope === 'tenant' ? values.tenant_id : null;
    }
    return result;
  },
  toFormValues: (data) => {
    const ext = data as AIAgentInfo & { _package_options?: { label: string; value: number }[] };
    return {
      name: data.name,
      avatar: data.avatar || '',
      description: data.description,
      scope: data.scope,
      tenant_id: data.tenant_id,
      model_id: data.model_id,
      execution_mode: data.execution_mode,
      system_prompt: data.system_prompt,
      temperature: data.temperature,
      max_tokens: data.max_tokens,
      welcome_message: data.welcome_message || '',
      suggested_questions: Array.isArray(data.suggested_questions)
        ? data.suggested_questions.join('\n')
        : '',
      package_ids: ext._package_options || [],
    };
  },
  afterOpen: () => {
    // rowData is set before afterOpen; detailData is not yet loaded
    const sys = !!(rowData.value as Record<string, unknown> | undefined)?.is_system;
    isSystemAgent.value = sys;
    // Re-apply schema: initial schema() call ran before isSystemAgent was detected
    formApi.setState({ schema: useFormSchema(isEdit.value, sys) });
  },
  onSuccess: async () => {
    const agentId = recordId.value as number | undefined;
    if (agentId && pendingPackageIds.value.length >= 0) {
      try {
        await batchBindAIAgentSkillsApi(agentId, {
          package_ids: pendingPackageIds.value,
          consent_modes: Object.keys(consentModes.value).length > 0
            ? consentModes.value
            : undefined,
        });
      } catch {
        // package binding errors are non-fatal
      }
    }
    emits('success');
  },
  detailApi: async (id) => {
    const agent = await getAIAgentDetailApi(id as number);
    try {
      const bindings = await getAIAgentSkillsApi(id as number);
      const ext = agent as AIAgentInfo & { _package_options?: { label: string; value: number }[] };
      ext._package_options = bindings.map((b) => ({
        label: b.package_name || `#${b.package_id}`,
        value: b.package_id,
      }));
      const modes: Record<string, string> = {};
      for (const b of bindings) {
        if (b.consent_mode && b.consent_mode !== 'auto') {
          modes[String(b.package_id)] = b.consent_mode;
        }
      }
      consentModes.value = modes;
      selectedPackages.value = ext._package_options;
    } catch {
      (agent as AIAgentInfo & { _package_options?: { label: string; value: number }[] })._package_options = [];
    }
    return agent;
  },
});

defineExpose({ openNew, openEdit });

const consentModeOptions = computed(() => [
  { label: $t('admin.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('admin.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('admin.ai.agent.consentModeOptions.reject'), value: 'reject' },
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


const title = computed(() => {
  if (isSystemAgent.value && isEdit.value) {
    return $t('admin.ai.agent.systemAgent');
  }
  return isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.agent.create');
});
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Alert
      v-if="isSystemAgent && isEdit"
      type="warning"
      show-icon
      :message="$t('admin.ai.agent.systemAgentDesc')"
      class="mb-4"
    />
    <Form />

    <!-- Consent mode per skill package -->
    <div v-if="selectedPackages.length > 0" class="mt-4">
      <div class="mb-2 text-sm font-medium text-foreground">
        {{ $t('admin.ai.agent.consentMode') }}
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
  </Drawer>
</template>
