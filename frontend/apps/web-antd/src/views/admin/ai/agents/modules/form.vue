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
import { getAIAgentDetailApi } from '#/api/admin/ai';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { Alert } from 'ant-design-vue';

import { getFormDefaults, useFormSchema } from '../data';

const emits = defineEmits<{ success: [] }>();

const isSystemAgent = ref(false);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, rowData, openNew, openEdit } = useCrudDrawer<AIAgentInfo>({
  formApi,
  apiPath: '/admin/ai/agents',
  schema: (edit) => useFormSchema(edit, isSystemAgent.value),
  defaults: getFormDefaults,
  transform: (values, edit) => {
    const result: Record<string, unknown> = {
      avatar: values.avatar || null,
      description: values.description || null,
      model_id: values.model_id,
      system_prompt: values.system_prompt || null,
      temperature: values.temperature,
      max_tokens: values.max_tokens,
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
    };
  },
  afterOpen: () => {
    // rowData is set before afterOpen; detailData is not yet loaded
    const sys = !!(rowData.value as Record<string, unknown> | undefined)?.is_system;
    isSystemAgent.value = sys;
    // Re-apply schema: initial schema() call ran before isSystemAgent was detected
    formApi.setState({ schema: useFormSchema(isEdit.value, sys) });
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getAIAgentDetailApi(id as number),
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
