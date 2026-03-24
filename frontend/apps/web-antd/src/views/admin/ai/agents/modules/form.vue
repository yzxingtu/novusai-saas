<script lang="ts" setup>
/**
 * 管理端智能体新建/编辑表单抽屉
 *
 * 系统智能体编辑时锁定核心字段（name / scope / execution_mode），
 * 仅允许修改调优参数（model_id / system_prompt / temperature / max_tokens）。
 */
import type { AIAgentInfo } from '#/api/admin/ai';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Select as ASelect,
  Tag as ATag,
} from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import {
  batchBindAIAgentSkillsApi,
  getAIAgentDetailApi,
  getAIAgentSkillsApi,
  getAIModelListApi,
} from '#/api/admin/ai';
import {
  AgentSkillBindingPicker,
  draftsToBatchPayload,
  grantsToDrafts,
  type AgentSkillBindingDraftItem,
} from '#/components/business/agent-skill-binding-picker';
import { scopeNeedsAssignment } from '#/components/business/scope-select/use-scope-fields';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';
import { getSkillTypeColor } from '#/utils/ai-helpers';
import { showRequestError } from '#/utils/error-helpers';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'AdminAgentForm' });

const emits = defineEmits<{ success: [] }>();
const router = useRouter();

const isSystemAgent = ref(false);
const skillDrafts = ref<AgentSkillBindingDraftItem[]>([]);
const skillPickerOpen = ref(false);
const modelMaxOutputTokensMap = ref<Record<number, number | undefined>>({});

function resolveModelMaxOutputTokens(
  modelId: null | number | undefined,
): number | undefined {
  if (modelId == null) return undefined;
  return modelMaxOutputTokensMap.value[modelId];
}

function buildSchema(edit = false, isSystem = false, isCreate = false) {
  return useFormSchema(
    edit,
    isSystem,
    isCreate,
    resolveModelMaxOutputTokens,
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
        if (scopeNeedsAssignment(scope)) {
          result.tenant_ids = (values.tenant_ids as number[]) ?? [];
        } else {
          result.tenant_ids = [];
        }
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
      const sys = !!(rowData.value as Record<string, unknown> | undefined)
        ?.is_system;
      isSystemAgent.value = sys;
      formApi.setState({ schema: buildSchema(isEdit.value, sys, !isEdit.value) });
      if (!isEdit.value) {
        skillDrafts.value = [];
      }
    },
    onSuccess: async () => {
      const agentId = recordId.value as number | undefined;
      if (agentId) {
        try {
          const payload = draftsToBatchPayload(skillDrafts.value);
          await batchBindAIAgentSkillsApi(agentId, payload);
        } catch (error) {
          console.error('[AdminAgentForm] batchBind skills', error);
          showRequestError(error, 'common.saveFailed');
        }
      }
      emits('success');
      if (!isEdit.value && agentId) {
        await router.push(`/admin/ai/agents/${agentId}`);
      }
    },
    detailApi: async (id) => {
      const agent = await getAIAgentDetailApi(id as number);
      try {
        const grants = await getAIAgentSkillsApi(id as number);
        skillDrafts.value = grantsToDrafts(grants);
      } catch (error) {
        console.error('[AdminAgentForm] load agent skills', error);
        showRequestError(error, 'common.loadFailed');
        skillDrafts.value = [];
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

const title = computed(() => {
  if (isSystemAgent.value && isEdit.value) {
    return $t('admin.ai.agent.systemAgent');
  }
  return isEdit.value ? $t('admin.common.edit') : $t('admin.ai.agent.create');
});

function setDraftConsent(skillId: number, mode: string) {
  const idx = skillDrafts.value.findIndex((d) => d.skill_id === skillId);
  if (idx < 0) return;
  const cur = skillDrafts.value[idx]!;
  if (mode === 'auto' || mode === 'ask' || mode === 'reject') {
    skillDrafts.value.splice(idx, 1, { ...cur, default_consent_mode: mode });
  }
}

function removeDraftSkill(skillId: number) {
  skillDrafts.value = skillDrafts.value.filter((d) => d.skill_id !== skillId);
}

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
    <Form />

    <div class="mb-5">
      <AgentSkillBindingPicker
        v-model:open="skillPickerOpen"
        v-model="skillDrafts"
      />

      <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-foreground">{{
                $t('admin.ai.agent.skillBindings')
              }}</span>
              <ATag class="!m-0 !rounded-full !px-2 !text-[11px]">
                {{
                  $t('admin.ai.agent.skillPicker.selectedCount', {
                    count: skillDrafts.length,
                  })
                }}
              </ATag>
            </div>
            <p class="mt-1 text-xs leading-5 text-muted-foreground">
              {{ $t('admin.ai.agent.help.skillBindings') }}
            </p>
          </div>
          <Button type="primary" @click="skillPickerOpen = true">
            <template #icon>
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.skillPicker.openPicker') }}
          </Button>
        </div>

        <div
          v-if="skillDrafts.length === 0"
          class="mt-4 flex items-center gap-3 rounded-2xl border border-dashed border-border/70 bg-background/70 px-4 py-4"
        >
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:puzzle" class="size-5" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-foreground">
              {{ $t('admin.ai.agent.skillPicker.emptySelected') }}
            </div>
            <div class="mt-1 text-xs leading-5 text-muted-foreground">
              {{ $t('admin.ai.agent.skillPicker.formEmptyHint') }}
            </div>
          </div>
        </div>

        <div v-else class="mt-4 space-y-3">
          <div
            v-for="d in skillDrafts"
            :key="`skill-${d.skill_id}`"
            class="rounded-2xl border border-border/70 bg-background px-4 py-3 shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-foreground">
                  {{ d.skill_name }}
                </div>
                <div
                  v-if="d.package_name"
                  class="mt-1 truncate text-xs text-muted-foreground"
                >
                  {{ d.package_name }}
                </div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <ATag
                    v-if="d.skill_type"
                    class="!m-0 !text-[10px]"
                    :color="getSkillTypeColor(d.skill_type)"
                  >
                    {{ d.skill_type }}
                  </ATag>
                  <ATag v-if="d.is_system" color="red" class="!m-0 !text-[10px]">
                    {{ $t('admin.ai.skillPackage.system') }}
                  </ATag>
                  <ATag
                    v-if="d.source_plugin"
                    color="purple"
                    class="!m-0 !text-[10px]"
                  >
                    {{ d.source_plugin }}
                  </ATag>
                </div>
              </div>
              <Button
                type="text"
                danger
                size="small"
                @click="removeDraftSkill(d.skill_id)"
              >
                {{ $t('admin.ai.agent.skillPicker.remove') }}
              </Button>
            </div>
            <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                {{ $t('admin.ai.agent.skillPicker.defaultConsentMode') }}
              </div>
              <ASelect
                :value="d.default_consent_mode"
                :options="consentModeOptions"
                size="small"
                class="w-[140px] shrink-0"
                @update:value="(v) => setDraftConsent(d.skill_id, String(v))"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </Drawer>
</template>
