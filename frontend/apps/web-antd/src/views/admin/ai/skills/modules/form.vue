<script lang="ts" setup>
defineOptions({ name: 'AdminSkillForm' });
/**
 * 管理端技能新建/编辑表单抽屉
 */
import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, ref } from 'vue';

import {
  inputField,
  numberField,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { useVbenForm } from '#/adapter/form';
import { getAITablePolicyListApi } from '#/api/admin/ai';
import { getAdminKnowledgeBaseListApi } from '#/api/admin/knowledge-bases';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import {
  getSkillDetailApi,
  parseToolkitApi,
} from '#/api/admin/skills';
import { useCrudDrawer } from '#/composables';
import { Divider, Tag } from 'ant-design-vue';

import { $t } from '#/locales';


async function getKbSelectOptions() {
  try {
    const res = await getAdminKnowledgeBaseListApi({ 'page[size]': 100 });
    return res.items.map((kb) => ({ label: kb.name, value: kb.id }));
  } catch {
    return [];
  }
}

async function getTablePolicySelectOptions() {
  try {
    const res = await getAITablePolicyListApi({ 'page[size]': 200 });
    return res.items.map((p) => ({
      label: `${p.label} (${p.table_name})`,
      value: p.id,
    }));
  } catch {
    return [];
  }
}

function getSearchModeOptions() {
  return [
    { label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.vector'), value: 'vector' },
    { label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.keyword'), value: 'keyword' },
    { label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.hybrid'), value: 'hybrid' },
  ];
}

function getRewriteStrategyOptions() {
  return [
    { label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.none'), value: 'none' },
    { label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.hypothetical'), value: 'hypothetical' },
    { label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.step_back'), value: 'step_back' },
  ];
}


const emits = defineEmits<{ success: [] }>();

function getSkillTypeOptions() {
  return [
    { label: $t('admin.ai.skill.type_options.toolkit'), value: 'toolkit' },
    { label: $t('admin.ai.skill.type_options.knowledge_base'), value: 'knowledge_base' },
    { label: $t('admin.ai.skill.type_options.data_intelligence'), value: 'data_intelligence' },
    { label: $t('admin.ai.skill.type_options.builtin'), value: 'builtin' },
  ];
}

async function getSkillPackageSelectOptions(params?: Record<string, unknown>) {
  try {
    return await getSkillPackageSelectApi(params);
  } catch {
    return [];
  }
}

const currentValvesSchema = ref<Record<string, unknown> | null>(null);

interface BuiltinToolInfo {
  name: string;
  description: string;
  parameters?: { properties?: Record<string, { type?: string; description?: string }> };
}
const builtinTools = ref<BuiltinToolInfo[]>([]);

const isToolkit = (v: Record<string, unknown>) => v.type === 'toolkit';
const isKb = (v: Record<string, unknown>) => v.type === 'knowledge_base';
const isDi = (v: Record<string, unknown>) => v.type === 'data_intelligence';
const isDiNonSystem = (v: Record<string, unknown>) =>
  v.type === 'data_intelligence' && !isSystemSkill.value;

const isSystemSkill = ref(false);

interface DiToolInfo {
  name: string;
  description: string;
  tables: string[];
}
const diTools = ref<DiToolInfo[]>([]);

function useFormSchema() {
  return [
    {
      component: 'Alert',
      fieldName: '_create_guide',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        banner: true,
        message: $t('admin.ai.skill.createGuide'),
      },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: false,
        api: getSkillPackageSelectOptions,
        class: 'w-full',
        placeholder: $t('admin.ai.skillPackage.placeholder.searchName'),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'package_id',
      label: $t('admin.ai.skillPackage.name'),
      rules: 'required',
    },
    inputField('name', $t('admin.ai.skill.name'), {
      required: true,
      placeholder: $t('admin.ai.skill.placeholder.inputName'),
    }),
    {
      ...select('type', $t('admin.ai.skill.type'), {
        options: getSkillTypeOptions(),
        required: true,
        placeholder: $t('admin.ai.skill.placeholder.selectType'),
      }),
      help: $t('admin.ai.skill.help.type'),
    },
    {
      component: 'Alert',
      fieldName: '_type_desc',
      label: '',
      componentProps: {
        type: 'info',
        showIcon: true,
        message: '',
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => !!values.type,
        componentProps: (values: Record<string, unknown>) => ({
          type: 'info',
          showIcon: true,
          message: $t(`admin.ai.skill.typeDesc.${values.type as string}`),
        }),
      },
    },
    textareaField('description', $t('admin.ai.skill.description'), {
      placeholder: $t('admin.ai.skill.placeholder.inputDescription'),
    }),
    {
      ...numberField('timeout', $t('admin.ai.skill.timeout'), {
        min: 1,
        max: 300,
        placeholder: $t('admin.ai.skill.placeholder.inputTimeout'),
      }),
      help: $t('admin.ai.skill.help.timeout'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) =>
          values.type !== 'builtin' && values.type !== 'knowledge_base',
      },
    },
    switchField('is_active', $t('admin.ai.skill.isActive'), {
      defaultValue: true,
    }),
    // ============ toolkit 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_toolkit_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('admin.ai.skill.toolkitEditor.title') }),
      dependencies: { triggerFields: ['type'], if: isToolkit },
    },
    {
      component: 'ToolkitEditor',
      fieldName: 'toolkit_content',
      label: $t('admin.ai.skill.toolkitEditor.sourceCode'),
      componentProps: {
        parseApi: parseToolkitApi,
        localePrefix: 'admin.ai.skill',
        onParseComplete: (schema: Record<string, unknown> | null) => {
          currentValvesSchema.value = schema;
        },
      },
      dependencies: { triggerFields: ['type'], if: isToolkit },
    },
    {
      component: 'ValvesConfigForm',
      fieldName: 'valves_config',
      label: $t('admin.ai.skill.toolkitEditor.valves'),
      componentProps: () => ({
        schema: currentValvesSchema.value,
        localePrefix: 'admin.ai.skill',
      }),
      dependencies: {
        triggerFields: ['type'],
        if: isToolkit,
      },
    },
    // ============ knowledge_base 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_kb_config_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('admin.ai.skill.knowledgeBaseConfig.title') }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true, api: getKbSelectOptions, class: 'w-full', mode: 'multiple',
        placeholder: $t('admin.ai.skill.knowledgeBaseConfig.selectKbPlaceholder'),
        showSearch: true, optionFilterProp: 'label',
      },
      fieldName: 'kb_ids',
      label: $t('admin.ai.skill.knowledgeBaseConfig.selectKb'),
      help: $t('admin.ai.skill.knowledgeBaseConfig.selectKbHelp'),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...switchField('rag_enabled', $t('admin.ai.skill.knowledgeBaseConfig.ragEnabled')),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField('rag_top_k', $t('admin.ai.skill.knowledgeBaseConfig.topK'), { min: 1, max: 20 }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField('rag_score_threshold', $t('admin.ai.skill.knowledgeBaseConfig.scoreThreshold'), { min: 0, max: 1 }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...select('rag_search_mode', $t('admin.ai.skill.knowledgeBaseConfig.searchMode'), { options: getSearchModeOptions() }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...select('rag_rewrite_strategy', $t('admin.ai.skill.knowledgeBaseConfig.rewriteStrategy'), { options: getRewriteStrategyOptions() }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...switchField('rag_reranker_enabled', $t('admin.ai.skill.knowledgeBaseConfig.rerankerEnabled')),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField('rag_context_token_ratio', $t('admin.ai.skill.knowledgeBaseConfig.contextTokenRatio'), { min: 0, max: 1 }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    // ============ builtin 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_builtin_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('admin.ai.skill.builtinTools.title') }),
      dependencies: { triggerFields: ['type'], if: (v: Record<string, unknown>) => v.type === 'builtin' },
    },
    {
      component: 'Alert',
      fieldName: '_builtin_tools_info',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.builtinTools.hint'),
      },
      dependencies: { triggerFields: ['type'], if: (v: Record<string, unknown>) => v.type === 'builtin' },
    },
    // ============ data_intelligence 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_di_config_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('admin.ai.skill.dataIntelligenceConfig.title') }),
      dependencies: { triggerFields: ['type'], if: isDi },
    },
    {
      component: 'Alert',
      fieldName: '_di_system_hint',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.dataIntelligenceConfig.systemHint'),
      },
      dependencies: {
        triggerFields: ['type'],
        if: (v: Record<string, unknown>) =>
          v.type === 'data_intelligence' && isSystemSkill.value,
      },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true, api: getTablePolicySelectOptions, class: 'w-full', mode: 'multiple',
        placeholder: $t('admin.ai.skill.dataIntelligenceConfig.tablePoliciesPlaceholder'),
        showSearch: true, optionFilterProp: 'label',
      },
      fieldName: 'di_table_policy_ids',
      label: $t('admin.ai.skill.dataIntelligenceConfig.tablePolicies'),
      help: $t('admin.ai.skill.dataIntelligenceConfig.tablePoliciesHelp'),
      dependencies: { triggerFields: ['type'], if: isDiNonSystem },
    },
    {
      ...numberField('di_max_rows_override', $t('admin.ai.skill.dataIntelligenceConfig.maxRowsOverride'), { min: 0, max: 10000 }),
      help: $t('admin.ai.skill.dataIntelligenceConfig.maxRowsOverrideHelp'),
      dependencies: { triggerFields: ['type'], if: isDiNonSystem },
    },
  ];
}

function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'toolkit',
    timeout: 30,
    is_active: true,
    toolkit_content: '',
    valves_config: {},
    kb_ids: [],
    rag_enabled: true,
    rag_top_k: 5,
    rag_score_threshold: 0.5,
    rag_search_mode: 'hybrid',
    rag_rewrite_strategy: 'none',
    rag_reranker_enabled: false,
    rag_context_token_ratio: 0.3,
    di_table_policy_ids: [],
    di_max_rows_override: 0,
  };
}

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<AdminSkillInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/admin/ai/skills',
  transform: (values) => {
    let config: Record<string, unknown> | null = null;
    const type = values.type as string;

    if (type === 'knowledge_base') {
      config = {
        knowledge_base_ids: values.kb_ids || [],
        rag_config: {
          enabled: values.rag_enabled ?? true,
          top_k: values.rag_top_k ?? 5,
          score_threshold: values.rag_score_threshold ?? 0.5,
          search_mode: values.rag_search_mode || 'hybrid',
          rewrite_strategy: values.rag_rewrite_strategy || 'none',
          reranker_enabled: values.rag_reranker_enabled ?? false,
          context_token_ratio: values.rag_context_token_ratio ?? 0.3,
        },
      };
    } else if (type === 'data_intelligence') {
      config = {
        table_policy_ids: values.di_table_policy_ids || [],
        max_rows_override: values.di_max_rows_override ?? 0,
      };
    } else if (type === 'toolkit') {
      const valvesConfig = values.valves_config as Record<string, unknown> | undefined;
      config = valvesConfig && Object.keys(valvesConfig).length > 0
        ? { valves: valvesConfig }
        : null;
    }

    const result: Record<string, unknown> = {
      package_id: values.package_id,
      name: values.name,
      type,
      description: values.description || null,
      timeout: values.timeout ?? 30,
      is_active: values.is_active ?? true,
      config,
    };

    if (type === 'toolkit') {
      result.toolkit_content = values.toolkit_content || '';
    }

    return result;
  },
  toFormValues: (data) => {
    const cfg = (data.config ?? {}) as Record<string, unknown>;
    const ragCfg = (cfg.rag_config ?? {}) as Record<string, unknown>;

    isSystemSkill.value = !!data.is_system;

    if (data.type === 'builtin' && Array.isArray(cfg.tools)) {
      builtinTools.value = cfg.tools as BuiltinToolInfo[];
    } else {
      builtinTools.value = [];
    }

    // 加载数据智能技能的可用工具信息
    if (data.type === 'data_intelligence') {
      loadDiTools(data.is_system, cfg.table_policy_ids as number[] | undefined);
    } else {
      diTools.value = [];
    }

    return {
      package_id: data.package_id,
      name: data.name,
      type: data.type,
      description: data.description,
      timeout: data.timeout,
      is_active: data.is_active,
      toolkit_content: data.toolkit_content || '',
      valves_config: (cfg.valves as Record<string, unknown>) || {},
      kb_ids: (cfg.knowledge_base_ids as number[]) || [],
      rag_enabled: (ragCfg.enabled as boolean) ?? true,
      rag_top_k: (ragCfg.top_k as number) ?? 5,
      rag_score_threshold: (ragCfg.score_threshold as number) ?? 0.5,
      rag_search_mode: (ragCfg.search_mode as string) || 'hybrid',
      rag_rewrite_strategy: (ragCfg.rewrite_strategy as string) || 'none',
      rag_reranker_enabled: (ragCfg.reranker_enabled as boolean) ?? false,
      rag_context_token_ratio: (ragCfg.context_token_ratio as number) ?? 0.3,
      di_table_policy_ids: (cfg.table_policy_ids as number[]) || [],
      di_max_rows_override: (cfg.max_rows_override as number) ?? 0,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: async (id) => {
    return await getSkillDetailApi(id as number);
  },
});

async function loadDiTools(
  isSystem: boolean,
  tablePolicyIds?: number[],
) {
  try {
    const res = await getAITablePolicyListApi({ 'page[size]': 200 });
    let policies = res.items.filter((p) => p.is_active);
    if (!isSystem && tablePolicyIds && tablePolicyIds.length > 0) {
      policies = policies.filter((p) => tablePolicyIds.includes(p.id));
    }
    const tools: DiToolInfo[] = [];
    const readTables = policies
      .filter((p) => p.allow_read)
      .map((p) => `${p.label} (${p.table_name})`);
    if (readTables.length > 0) {
      tools.push({
        name: 'data_query',
        description: $t('admin.ai.skill.dataIntelligenceConfig.tools.dataQuery'),
        tables: readTables,
      });
    }
    const createTables = policies
      .filter((p) => p.allow_create)
      .map((p) => `${p.label} (${p.table_name})`);
    if (createTables.length > 0) {
      tools.push({
        name: 'data_create',
        description: $t('admin.ai.skill.dataIntelligenceConfig.tools.dataCreate'),
        tables: createTables,
      });
    }
    const updateTables = policies
      .filter((p) => p.allow_update)
      .map((p) => `${p.label} (${p.table_name})`);
    if (updateTables.length > 0) {
      tools.push({
        name: 'data_update',
        description: $t('admin.ai.skill.dataIntelligenceConfig.tools.dataUpdate'),
        tables: updateTables,
      });
    }
    const deleteTables = policies
      .filter((p) => p.allow_delete)
      .map((p) => `${p.label} (${p.table_name})`);
    if (deleteTables.length > 0) {
      tools.push({
        name: 'data_delete',
        description: $t('admin.ai.skill.dataIntelligenceConfig.tools.dataDelete'),
        tables: deleteTables,
      });
    }
    diTools.value = tools;
  } catch {
    diTools.value = [];
  }
}

const title = computed(() =>
  isEdit.value
    ? $t('admin.common.edit')
    : $t('admin.ai.skill.create'),
);

</script>

<template>
  <Drawer :title="title" class="w-[800px]">
    <Form />

    <!-- data_intelligence 工具列表只读展示 -->
    <template v-if="diTools.length > 0">
      <Divider orientation="left" dashed>
        {{ $t('admin.ai.skill.dataIntelligenceConfig.toolListTitle') }}
        <Tag color="blue" class="ml-2">{{ diTools.length }}</Tag>
      </Divider>
      <div class="flex flex-col gap-2">
        <div
          v-for="tool in diTools"
          :key="tool.name"
          class="rounded-lg border border-border/60 p-3"
        >
          <div class="mb-1 flex items-center gap-2">
            <Tag color="processing">{{ tool.name }}</Tag>
            <span class="text-xs text-muted-foreground">{{ tool.description }}</span>
          </div>
          <div class="mt-1 flex flex-wrap gap-1">
            <Tag
              v-for="table in tool.tables"
              :key="table"
              class="!text-[10px]"
            >
              {{ table }}
            </Tag>
          </div>
        </div>
      </div>
    </template>

    <!-- builtin 工具列表只读展示 -->
    <template v-if="builtinTools.length > 0">
      <Divider orientation="left" dashed>
        {{ $t('admin.ai.skill.builtinTools.toolList') }}
        <Tag color="blue" class="ml-2">{{ builtinTools.length }}</Tag>
      </Divider>
      <div class="flex flex-col gap-2">
        <div
          v-for="tool in builtinTools"
          :key="tool.name"
          class="rounded-lg border border-border/60 p-3"
        >
          <div class="mb-1 flex items-center gap-2">
            <Tag color="processing">{{ tool.name }}</Tag>
          </div>
          <p class="mb-0 text-xs text-muted-foreground">
            {{ tool.description }}
          </p>
          <div
            v-if="tool.parameters?.properties"
            class="mt-2 flex flex-wrap gap-1"
          >
            <Tag
              v-for="(pInfo, pName) in tool.parameters.properties"
              :key="String(pName)"
              class="!text-[10px]"
            >
              {{ pName }}: {{ pInfo.type || 'string' }}
            </Tag>
          </div>
        </div>
      </div>
    </template>
  </Drawer>
</template>
