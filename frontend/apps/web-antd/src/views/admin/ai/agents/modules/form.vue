<script lang="ts" setup>
import type { PkgOption } from '../data';

/**
 * 管理端智能体新建/编辑表单抽屉
 *
 * 系统智能体编辑时锁定核心字段（name / scope / execution_mode），
 * 仅允许修改调优参数（model_id / system_prompt / temperature / max_tokens）。
 */
import type { AIAgentInfo, AIAgentSkillBindingInfo } from '#/api/admin/ai';

import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Alert, Select as ASelect, Tag as ATag } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import {
  batchBindAIAgentSkillsApi,
  getAIAgentDetailApi,
  getAIAgentSkillsApi,
  getAIModelListApi,
} from '#/api/admin/ai';
import { getRecommendedSkillPackagesApi } from '#/api/admin/skill-packages';
import { scopeNeedsAssignment } from '#/components/business/scope-select/use-scope-fields';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';
import { getScopeColor } from '#/utils/scope-helpers';
import { getAudienceColor } from '#/views/admin/ai/skill-packages/data';

import {
  getFormDefaults,
  getPackageSelectOptions,
  useFormSchema,
} from '../data';

defineOptions({ name: 'AdminAgentForm' });

const emits = defineEmits<{ success: [] }>();
const router = useRouter();

const isSystemAgent = ref(false);
const pendingPackageIds = ref<number[]>([]);
const consentModes = ref<Record<string, string>>({});
const selectedPackages = ref<Array<{ label: string; value: number }>>([]);
const packageOptions = ref<PkgOption[]>([]);
const packageLoading = ref(false);
const autoBindPackages = ref<AIAgentSkillBindingInfo[]>([]);
const recommendedPackageIds = ref<number[]>([]);
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
      // rowData is set before afterOpen; detailData is not yet loaded
      const sys = !!(rowData.value as Record<string, unknown> | undefined)
        ?.is_system;
      isSystemAgent.value = sys;
      // Re-apply schema: initial schema() call ran before isSystemAgent was detected
      formApi.setState({ schema: buildSchema(isEdit.value, sys, !isEdit.value) });
      // Pre-populate recommended packages for new agent creation
      if (!isEdit.value && recommendedPackageIds.value.length > 0) {
        const recOpts = packageOptions.value
          .filter((p) => recommendedPackageIds.value.includes(p.value))
          .map((p) => ({ label: p.label, value: p.value }));
        if (recOpts.length > 0) {
          selectedPackages.value = recOpts;
          pendingPackageIds.value = recOpts.map((p) => p.value);
        }
      }
    },
    onSuccess: async () => {
      const agentId = recordId.value as number | undefined;
      if (agentId && pendingPackageIds.value.length >= 0) {
        try {
          await batchBindAIAgentSkillsApi(agentId, {
            package_ids: pendingPackageIds.value,
            consent_modes:
              Object.keys(consentModes.value).length > 0
                ? consentModes.value
                : undefined,
          });
        } catch {
          // package binding errors are non-fatal
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
        const bindings = await getAIAgentSkillsApi(id as number);
        // Separate auto-bind vs manual bindings
        const autoBind: AIAgentSkillBindingInfo[] = [];
        const manualBind: AIAgentSkillBindingInfo[] = [];
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
  return isEdit.value ? $t('admin.common.edit') : $t('admin.ai.agent.create');
});

async function loadPackageOptions() {
  packageLoading.value = true;
  try {
    const [opts, recommended] = await Promise.all([
      getPackageSelectOptions(),
      getRecommendedSkillPackagesApi().catch(() => []),
    ]);
    packageOptions.value = opts;
    recommendedPackageIds.value = recommended.map((p) => p.id);
  } finally {
    packageLoading.value = false;
  }
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
  void loadPackageOptions();
  void loadModelLimits();
});

// Filter out auto-bound packages from the manual selection dropdown
const manualPackageOptions = computed(() => {
  const autoIds = new Set(autoBindPackages.value.map((b) => b.package_id));
  return packageOptions.value.filter((p) => !autoIds.has(p.value));
});

function getOptionTags(value: number): Array<{ color: string; text: string }> {
  const opt = packageOptions.value.find((o) => o.value === value);
  if (!opt) return [];
  const tags: Array<{ color: string; text: string }> = [];
  if (opt.isSystem)
    tags.push({ text: $t('admin.ai.skillPackage.system'), color: 'red' });
  if (opt.sourcePlugin)
    tags.push({
      text: $t('admin.ai.skillPackage.sourcePlugin'),
      color: 'purple',
    });
  if (opt.scope)
    tags.push({ text: opt.scope, color: getScopeColor(opt.scope) });
  return tags;
}

function onPackageChange(val: unknown) {
  const raw = (val || []) as Array<unknown>;
  const items = raw.map((item) => {
    if (typeof item === 'object' && item !== null) {
      const obj = item as Record<string, unknown>;
      return {
        label: String(obj.label || ''),
        value: Number(obj.value || obj.key || 0),
      };
    }
    return { label: `#${item}`, value: Number(item) };
  });
  selectedPackages.value = items;
  pendingPackageIds.value = items.map((p) => p.value);
  formApi.setValues({ package_ids: items });
}
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

    <!-- Skill package binding section (unified: auto-bind + manual + consent mode) -->
    <div class="mb-5">
      <div class="mb-2 text-sm font-medium text-foreground">
        {{ $t('admin.ai.agent.skillPackageBindings') }}
      </div>

      <!-- Manual package selector -->
      <ASelect
        :value="selectedPackages"
        mode="multiple"
        label-in-value
        :loading="packageLoading"
        :options="manualPackageOptions"
        :placeholder="$t('admin.ai.agent.placeholder.selectSkillPackages')"
        show-search
        option-filter-prop="label"
        class="w-full"
        @change="onPackageChange"
      >
        <template #option="{ label: optLabel, value: optValue }">
          <div class="flex items-center justify-between gap-2">
            <span class="truncate">{{ optLabel }}</span>
            <span class="flex shrink-0 gap-1">
              <ATag
                v-for="tag in getOptionTags(optValue as number)"
                :key="tag.text"
                :color="tag.color"
                class="!m-0 !text-[10px]"
              >
                {{ tag.text }}
              </ATag>
            </span>
          </div>
        </template>
      </ASelect>

      <!-- Unified binding list: auto-bind + manual, each with consent mode -->
      <div
        v-if="autoBindPackages.length > 0 || selectedPackages.length > 0"
        class="mt-3 space-y-2"
      >
        <!-- Auto-bind packages (locked, with consent mode) -->
        <div
          v-for="pkg in autoBindPackages"
          :key="`auto-${pkg.package_id}`"
          class="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2"
        >
          <IconifyIcon
            icon="lucide:lock"
            class="size-3.5 shrink-0 text-primary/60"
          />
          <span class="min-w-0 flex-1 truncate text-sm font-medium">{{
            pkg.package_name
          }}</span>
          <ATag
            v-if="pkg.package_is_system"
            color="red"
            class="!m-0 shrink-0 !text-[10px]"
          >
            {{ $t('admin.ai.skillPackage.system') }}
          </ATag>
          <ATag
            v-if="pkg.package_target_audience"
            :color="getAudienceColor(pkg.package_target_audience)"
            class="!m-0 shrink-0 !text-[10px]"
          >
            {{ pkg.package_target_audience }}
          </ATag>
          <ATag color="green" class="!m-0 shrink-0 !text-[10px]">
            {{ $t('admin.ai.agent.consentModeOptions.auto') }}
          </ATag>
        </div>

        <!-- Manual-bind packages (with consent mode) -->
        <div
          v-for="pkg in selectedPackages"
          :key="`manual-${pkg.value}`"
          class="flex items-center gap-2 rounded-md border border-border px-3 py-2"
        >
          <span class="min-w-0 flex-1 truncate text-sm font-medium">{{
            pkg.label
          }}</span>
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
  </Drawer>
</template>
