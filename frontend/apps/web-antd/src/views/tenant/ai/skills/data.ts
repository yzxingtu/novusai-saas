/**
 * 租户端技能管理 - 表格列、搜索配置、表单 Schema
 */
import type { VbenFormSchema } from '#/adapter/form';
import type { OnActionClickFn, VxeTableGridOptions } from '#/adapter/vxe-table';
import type { SkillInfo, SkillTypeOption } from '#/api/tenant/skills';

import { ref } from 'vue';

import {
  inputField,
  numberField,
  searchInput,
  select,
  switchField,
  textareaField,
} from '#/adapter/form';
import { getKnowledgeBaseListApi } from '#/api/tenant/knowledge-bases';
import { getSkillPackageSelectApi } from '#/api/tenant/skill-packages';
import { getTenantTablePoliciesApi } from '#/api/tenant/ai';
import { getSkillTypesApi, parseToolkitApi } from '#/api/tenant/skills';
import { $t } from '#/locales';

const _currentValvesSchema = ref<Record<string, unknown> | null>(null);

// ============ 知识库下拉 ============

export async function getKnowledgeBaseSelectOptions() {
  try {
    const res = await getKnowledgeBaseListApi({ 'page[size]': 100 });
    return res.items.map((kb) => ({
      label: kb.name,
      value: kb.id,
    }));
  } catch {
    return [];
  }
}

// ============ 表策略下拉 ============

export async function getTablePolicySelectOptions() {
  try {
    const data = await getTenantTablePoliciesApi();
    return data.map((p) => ({
      label: `${p.label} (${p.table_name})`,
      value: p.id,
    }));
  } catch {
    return [];
  }
}

// ============ RAG 辅助选项 ============

function getSearchModeOptions() {
  return [
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.searchModeOptions.vector'), value: 'vector' },
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.searchModeOptions.keyword'), value: 'keyword' },
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.searchModeOptions.hybrid'), value: 'hybrid' },
  ];
}

function getRewriteStrategyOptions() {
  return [
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.rewriteOptions.none'), value: 'none' },
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.rewriteOptions.hypothetical'), value: 'hypothetical' },
    { label: $t('tenant.ai.skill.knowledgeBaseConfig.rewriteOptions.step_back'), value: 'step_back' },
  ];
}


/** 缓存技能类型列表 */
const skillTypesCache = ref<SkillTypeOption[]>([]);

/** 加载技能类型 */
export async function loadSkillTypes(): Promise<SkillTypeOption[]> {
  if (skillTypesCache.value.length > 0) return skillTypesCache.value;
  try {
    const data = await getSkillTypesApi();
    skillTypesCache.value = data;
    return data;
  } catch {
    return [
      { value: 'toolkit', label: 'Toolkit' },
      { value: 'knowledge_base', label: 'Knowledge Base' },
      { value: 'data_intelligence', label: 'Data Intelligence' },
      { value: 'builtin', label: 'Builtin' },
    ];
  }
}

/**
 * 获取技能类型下拉选项
 */
export function getSkillTypeOptions() {
  const types = skillTypesCache.value;
  if (types.length > 0) {
    return types.map((t) => ({
      label: t.label,
      value: t.value,
    }));
  }
  return [
    { label: $t('tenant.ai.skill.type_options.toolkit'), value: 'toolkit' },
    { label: $t('tenant.ai.skill.type_options.knowledge_base'), value: 'knowledge_base' },
    { label: $t('tenant.ai.skill.type_options.data_intelligence'), value: 'data_intelligence' },
    { label: $t('tenant.ai.skill.type_options.builtin'), value: 'builtin' },
  ];
}

/**
 * 获取技能类型文本
 */
export function getSkillTypeText(type: string | undefined): string {
  if (!type) return '-';
  const cached = skillTypesCache.value.find((t) => t.value === type);
  if (cached) return cached.label;
  const key = `tenant.ai.skill.type_options.${type}`;
  const text = $t(key);
  return text === key ? type : text;
}

export { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';

/**
 * 表格列定义
 */
export function useColumns<T = SkillInfo>(
  onActionClick: OnActionClickFn<T>,
): VxeTableGridOptions['columns'] {
  return [
    {
      field: 'name',
      title: $t('tenant.ai.skill.name'),
      minWidth: 180,
      slots: { default: 'name_cell' },
    },
    {
      field: 'type',
      title: $t('tenant.ai.skill.type'),
      width: 140,
      align: 'center',
      slots: { default: 'type_cell' },
    },
    {
      field: 'description',
      title: $t('tenant.ai.skill.description'),
      minWidth: 200,
      slots: { default: 'description_cell' },
    },
    {
      field: 'is_active',
      title: $t('tenant.ai.skill.isActive'),
      width: 100,
      align: 'center',
      slots: { default: 'isActive_cell' },
    },
    {
      field: 'timeout',
      title: $t('tenant.ai.skill.timeout'),
      width: 100,
      align: 'right',
      slots: { default: 'timeout_cell' },
    },
    {
      field: 'created_at',
      title: $t('tenant.ai.skill.createdAt'),
      width: 170,
      sortable: true,
      slots: { default: 'createdAt_cell' },
    },
    {
      align: 'center',
      cellRender: {
        attrs: {
          resource: 'skill',
          nameField: 'name',
          nameTitle: $t('tenant.ai.skill.name'),
          onClick: onActionClick,
        },
        name: 'CellOperation',
        options: [
          { code: 'test', text: $t('tenant.ai.skill.testBtn'), icon: 'lucide:play' },
          'edit',
          'delete',
        ],
      },
      field: 'operation',
      fixed: 'right',
      title: $t('tenant.common.operation'),
      width: 160,
    },
  ];
}

/**
 * 搜索表单 Schema
 */
export function useGridFormSchema(): VbenFormSchema[] {
  return [
    searchInput('name', $t('tenant.ai.skill.name'), {
      placeholder: $t('tenant.ai.skill.placeholder.searchName'),
    }),
    select('filter[type][eq]', $t('tenant.ai.skill.type'), {
      options: getSkillTypeOptions(),
      placeholder: $t('tenant.ai.skill.placeholder.allTypes'),
    }),
  ];
}

/**
 * 技能表单 Schema
 */
export function useFormSchema(): VbenFormSchema[] {
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
        message: $t('tenant.ai.skill.createGuide'),
      },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: false,
        api: (params?: Record<string, unknown>) => getSkillPackageSelectApi(params),
        class: 'w-full',
        placeholder: $t('tenant.ai.skillPackage.placeholder.searchName'),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'package_id',
      label: $t('tenant.ai.skillPackage.name'),
      rules: 'required',
    },
    inputField('name', $t('tenant.ai.skill.name'), {
      required: true,
      placeholder: $t('tenant.ai.skill.placeholder.inputName'),
    }),
    {
      ...select('type', $t('tenant.ai.skill.type'), {
        options: getSkillTypeOptions(),
        required: true,
        placeholder: $t('tenant.ai.skill.placeholder.selectType'),
      }),
      help: $t('tenant.ai.skill.help.type'),
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
          message: $t(`tenant.ai.skill.typeDesc.${values.type as string}`),
        }),
      },
    },
    textareaField('description', $t('tenant.ai.skill.description'), {
      placeholder: $t('tenant.ai.skill.placeholder.inputDescription'),
    }),
    {
      ...numberField('timeout', $t('tenant.ai.skill.timeout'), {
        min: 1,
        max: 300,
        placeholder: $t('tenant.ai.skill.placeholder.inputTimeout'),
      }),
      help: $t('tenant.ai.skill.help.timeout'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) =>
          values.type !== 'builtin' && values.type !== 'knowledge_base',
      },
    },
    // ============ builtin 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_builtin_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('tenant.ai.skill.builtinTools.title') }),
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
        message: $t('tenant.ai.skill.builtinTools.hint'),
      },
      dependencies: { triggerFields: ['type'], if: (v: Record<string, unknown>) => v.type === 'builtin' },
    },
    // ============ knowledge_base 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_kb_config_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('tenant.ai.skill.knowledgeBaseConfig.title') }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getKnowledgeBaseSelectOptions,
        class: 'w-full',
        mode: 'multiple',
        placeholder: $t('tenant.ai.skill.knowledgeBaseConfig.selectKbPlaceholder'),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'kb_ids',
      label: $t('tenant.ai.skill.knowledgeBaseConfig.selectKb'),
      help: $t('tenant.ai.skill.knowledgeBaseConfig.selectKbHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...switchField('rag_enabled', $t('tenant.ai.skill.knowledgeBaseConfig.ragEnabled')),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...numberField('rag_top_k', $t('tenant.ai.skill.knowledgeBaseConfig.topK'), { min: 1, max: 20 }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...numberField('rag_score_threshold', $t('tenant.ai.skill.knowledgeBaseConfig.scoreThreshold'), { min: 0, max: 1 }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...select('rag_search_mode', $t('tenant.ai.skill.knowledgeBaseConfig.searchMode'), {
        options: getSearchModeOptions(),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...select('rag_rewrite_strategy', $t('tenant.ai.skill.knowledgeBaseConfig.rewriteStrategy'), {
        options: getRewriteStrategyOptions(),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...switchField('rag_reranker_enabled', $t('tenant.ai.skill.knowledgeBaseConfig.rerankerEnabled')),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    {
      ...numberField('rag_context_token_ratio', $t('tenant.ai.skill.knowledgeBaseConfig.contextTokenRatio'), { min: 0, max: 1 }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'knowledge_base',
      },
    },
    // ============ data_intelligence 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_di_config_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('tenant.ai.skill.dataIntelligenceConfig.title') }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'data_intelligence',
      },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getTablePolicySelectOptions,
        class: 'w-full',
        mode: 'multiple',
        placeholder: $t('tenant.ai.skill.dataIntelligenceConfig.tablePoliciesPlaceholder'),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'di_table_policy_ids',
      label: $t('tenant.ai.skill.dataIntelligenceConfig.tablePolicies'),
      help: $t('tenant.ai.skill.dataIntelligenceConfig.tablePoliciesHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'data_intelligence',
      },
    },
    {
      ...numberField('di_max_rows_override', $t('tenant.ai.skill.dataIntelligenceConfig.maxRowsOverride'), { min: 0, max: 10000 }),
      help: $t('tenant.ai.skill.dataIntelligenceConfig.maxRowsOverrideHelp'),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'data_intelligence',
      },
    },
    // ============ toolkit 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_toolkit_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({ default: () => $t('tenant.ai.skill.toolkitEditor.title') }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'toolkit',
      },
    },
    {
      component: 'ToolkitEditor',
      fieldName: 'toolkit_content',
      label: $t('tenant.ai.skill.toolkitEditor.sourceCode'),
      componentProps: {
        parseApi: parseToolkitApi,
        localePrefix: 'tenant.ai.skill',
        onParseComplete: (schema: Record<string, unknown> | null) => {
          _currentValvesSchema.value = schema;
        },
      },
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'toolkit',
      },
    },
    {
      component: 'ValvesConfigForm',
      fieldName: 'valves_config',
      label: $t('tenant.ai.skill.toolkitEditor.valves'),
      componentProps: () => ({
        schema: _currentValvesSchema.value,
        localePrefix: 'tenant.ai.skill',
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (values: Record<string, unknown>) => values.type === 'toolkit',
      },
    },
    switchField('is_active', $t('tenant.ai.skill.isActive'), {
      defaultValue: true,
    }),
  ];
}

/**
 * 技能表单默认值
 */
export function getFormDefaults(): Record<string, unknown> {
  return {
    type: 'toolkit',
    timeout: 30,
    is_active: true,
    toolkit_content: '',
    valves_config: {},
    // knowledge_base defaults
    kb_ids: [],
    rag_enabled: true,
    rag_top_k: 5,
    rag_score_threshold: 0.5,
    rag_search_mode: 'hybrid',
    rag_rewrite_strategy: 'none',
    rag_reranker_enabled: false,
    rag_context_token_ratio: 0.3,
    // data_intelligence defaults
    di_table_policy_ids: [],
    di_max_rows_override: 0,
  };
}
