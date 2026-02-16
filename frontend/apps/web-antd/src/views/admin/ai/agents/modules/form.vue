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

import { Alert } from 'ant-design-vue';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const isSystemAgent = ref(false);
const pendingPackageIds = ref<number[]>([]);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, recordId, rowData, openNew, openEdit } = useCrudDrawer<AIAgentInfo>({
  formApi,
  apiPath: '/admin/ai/agents',
  schema: (edit) => useFormSchema(edit, isSystemAgent.value),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const rawPkgIds = values.package_ids as Array<number | { label: string; value: number }>;
    pendingPackageIds.value = (rawPkgIds || []).map((p) =>
      typeof p === 'object' && p !== null ? p.value : p,
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
    } catch {
      (agent as AIAgentInfo & { _package_options?: { label: string; value: number }[] })._package_options = [];
    }
    return agent;
  },
});

defineExpose({ openNew, openEdit });

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
  </Drawer>
</template>
