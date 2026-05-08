<script lang="ts" setup>
/**
 * 管理端智能体新建/编辑表单抽屉
 *
 * 系统智能体编辑时锁定核心字段（name / scope / execution_mode），
 * 仅允许修改调优参数（model_id / system_prompt / temperature / max_tokens）。
 * 技能绑定统一在详情页中处理，不在抽屉表单内处理。
 */
import type { AIAgentInfo } from '#/api/admin/ai-agents';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Alert } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getAIAgentDetailApi } from '#/api/admin/ai-agents';
import { getAIModelListApi } from '#/api/admin/ai-models';
import { scopeNeedsAssignment } from '#/components/business/scope-select/use-scope-fields';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AdminAgentForm' });

const emits = defineEmits<{ success: [] }>();
const router = useRouter();

const isSystemAgent = ref(false);
const isPluginManagedAgent = ref(false);
const modelMaxOutputTokensMap = ref<Record<number, number | undefined>>({});

function resolveModelMaxOutputTokens(
  modelId: null | number | undefined,
): number | undefined {
  if (modelId === null || modelId === undefined) return undefined;
  return modelMaxOutputTokensMap.value[modelId];
}

function buildSchema(edit = false, isSystem = false, isCreate = false) {
  return useFormSchema(
    edit,
    isSystem,
    isCreate,
    resolveModelMaxOutputTokens,
    isPluginManagedAgent.value,
  );
}

const [Form, formApi] = useVbenForm({
  schema: buildSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, recordId, rowData, openNew, openEdit } =
  useCrudDrawer<AIAgentInfo>({
    formApi,
    apiPath: '/admin/ai/agents',
    schema: (edit) => buildSchema(edit, edit && isSystemAgent.value, !edit),
    defaults: getFormDefaults,
    transform: (values, edit) => {
      const sqArray = parseStarterQuestionsInput(
        values.suggested_questions as string | undefined,
      );

      const result: Record<string, unknown> = {
        avatar: values.avatar || null,
        description: values.description || null,
        model_id: values.model_id,
        system_prompt: values.system_prompt || null,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
        top_p: values.top_p ?? null,
        welcome_message: values.welcome_message || null,
        suggested_questions: sqArray,
      };
      if (!edit || !isSystemAgent.value) {
        result.name = values.name;
        result.execution_mode = values.execution_mode;
        const scope = values.scope as string;
        result.scope = scope;
        result.tenant_ids = scopeNeedsAssignment(scope)
          ? ((values.tenant_ids as number[]) ?? [])
          : [];
      } else if (isPluginManagedAgent.value) {
        result.tenant_ids = (values.tenant_ids as number[]) ?? [];
      }
      return result;
    },
    toFormValues: (data) => {
      return {
        name: data.name,
        avatar: data.avatar || '',
        description: data.description,
        scope: data.scope,
        tenant_id: data.tenant_id ?? null,
        tenant_ids:
          ((data as unknown as Record<string, unknown>)
            .assigned_tenant_ids as number[]) ?? [],
        model_id: data.model_id,
        execution_mode: data.execution_mode,
        system_prompt: data.system_prompt,
        temperature: data.temperature,
        max_tokens: data.max_tokens,
        top_p: data.top_p,
        welcome_message: data.welcome_message || '',
        suggested_questions: formatStarterQuestionsInput(
          data.suggested_questions as null | unknown[],
        ),
      };
    },
    afterOpen: () => {
      const currentRow =
        (rowData.value as Record<string, unknown> | undefined) || {};
      const sys = !!currentRow.is_system;
      isPluginManagedAgent.value = Boolean(currentRow.source_plugin);
      isSystemAgent.value = sys;
      formApi.setState({
        schema: buildSchema(isEdit.value, sys, !isEdit.value),
      });
      if (!isEdit.value) {
        isPluginManagedAgent.value = false;
      }
    },
    onSuccess: async () => {
      const agentId = recordId.value as number | undefined;
      emits('success');
      if (!isEdit.value && agentId) {
        await router.push(`/admin/ai/agents/${agentId}`);
      }
    },
    detailApi: async (id) => {
      const agent = await getAIAgentDetailApi(id as number);
      isPluginManagedAgent.value = Boolean(agent.source_plugin);
      isSystemAgent.value = Boolean(agent.is_system);
      return agent;
    },
  });

defineExpose({ openNew, openEdit });

const title = computed(() => {
  if (isSystemAgent.value && isEdit.value) {
    return $t('admin.ai.agent.systemAgent');
  }
  return isEdit.value ? $t('admin.common.edit') : $t('admin.ai.agent.create');
});

const pluginSourceLabel = computed(() => {
  const currentRow =
    (rowData.value as Record<string, unknown> | undefined) || {};
  return (
    (currentRow.source_plugin_display_name as string | undefined) ||
    (currentRow.source_plugin as string | undefined) ||
    ''
  );
});

const pluginSourceDisabled = computed(() => {
  const currentRow =
    (rowData.value as Record<string, unknown> | undefined) || {};
  return currentRow.source_plugin_enabled === false;
});

async function loadModelLimits() {
  try {
    const res = await getAIModelListApi({
      'page[size]': 200,
      'filter[type][eq]': 'chat',
    });
    const next: Record<number, number | undefined> = {};
    for (const item of res.items || []) {
      next[item.id] = item.max_output_tokens ?? undefined;
    }
    modelMaxOutputTokensMap.value = next;
    formApi.setState({
      schema: buildSchema(isEdit.value, isSystemAgent.value, !isEdit.value),
    });
  } catch {
    modelMaxOutputTokensMap.value = {};
  }
}

onMounted(() => {
  void loadModelLimits();
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
    <Alert
      v-if="isPluginManagedAgent && isEdit"
      type="info"
      show-icon
      class="mb-4"
      :message="`${$t('admin.ai.skillPackage.sourcePlugin')}：${pluginSourceLabel}`"
      :description="
        pluginSourceDisabled
          ? `${$t('admin.ai.agent.sourcePluginManagedDesc')} ${$t('admin.ai.agent.sourcePluginDisabled')}`
          : $t('admin.ai.agent.sourcePluginManagedDesc')
      "
    />
    <Form />
  </Drawer>
</template>
