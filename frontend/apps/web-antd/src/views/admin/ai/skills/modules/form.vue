<script lang="ts" setup>
/**
 * 管理端技能新建/编辑表单抽屉
 */
import type { AdminSkillInfo, PluginToolDefinition } from '#/api/admin/skills';

import { computed, ref, watch } from 'vue';

import { Divider, Tag } from 'ant-design-vue';

import {
  inputField,
  numberField,
  select,
  switchField,
  textareaField,
  useVbenForm,
} from '#/adapter/form';
import { getAITablePolicyListApi } from '#/api/admin/ai';
import { getAdminKnowledgeBaseListApi } from '#/api/admin/knowledge-bases';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import {
  getSkillDetailApi,
  getSkillToolsApi,
  parseToolkitApi,
} from '#/api/admin/skills';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

defineOptions({ name: 'AdminSkillForm' });

const emits = defineEmits<{ success: [] }>();

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
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.vector'),
      value: 'vector',
    },
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.keyword'),
      value: 'keyword',
    },
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.searchModeOptions.hybrid'),
      value: 'hybrid',
    },
  ];
}

function getRewriteStrategyOptions() {
  return [
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.none'),
      value: 'none',
    },
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.multi'),
      value: 'multi',
    },
    {
      label: $t('admin.ai.skill.knowledgeBaseConfig.rewriteOptions.hyde'),
      value: 'hyde',
    },
  ];
}

function getSkillTypeOptions(currentType?: string) {
  const predefined = [
    { label: $t('admin.ai.skill.type_options.toolkit'), value: 'toolkit' },
    {
      label: $t('admin.ai.skill.type_options.knowledge_base'),
      value: 'knowledge_base',
    },
    {
      label: $t('admin.ai.skill.type_options.data_intelligence'),
      value: 'data_intelligence',
    },
    { label: $t('admin.ai.skill.type_options.builtin'), value: 'builtin' },
    { label: $t('admin.ai.skill.type_options.http'), value: 'http' },
    { label: $t('admin.ai.skill.type_options.email'), value: 'email' },
    {
      label: $t('admin.ai.skill.type_options.code_execution'),
      value: 'code_execution',
    },
  ];
  if (currentType && !predefined.some((o) => o.value === currentType)) {
    const key = `admin.ai.skill.type_options.${currentType}`;
    const text = $t(key);
    const fallbackLabel = currentType
      .replaceAll('_', ' ')
      .replaceAll(/\b\w/g, (c) => c.toUpperCase());
    predefined.push({
      label: text === key ? fallbackLabel : text,
      value: currentType,
    });
  }
  return predefined;
}

async function getSkillPackageSelectOptions(params?: Record<string, unknown>) {
  try {
    return await getSkillPackageSelectApi(params);
  } catch {
    return [];
  }
}

const currentValvesSchema = ref<null | Record<string, unknown>>(null);

interface BuiltinToolInfo {
  name: string;
  description: string;
  parameters?: {
    properties?: Record<string, { description?: string; type?: string }>;
  };
}
const builtinTools = ref<BuiltinToolInfo[]>([]);
const pluginTools = ref<PluginToolDefinition[]>([]);

const isToolkit = (v: Record<string, unknown>) =>
  v.type === 'toolkit' && !isPluginSkill.value;
const isKb = (v: Record<string, unknown>) => v.type === 'knowledge_base';
const isDi = (v: Record<string, unknown>) => v.type === 'data_intelligence';
const isDiNonSystem = (v: Record<string, unknown>) =>
  v.type === 'data_intelligence' && !isSystemSkill.value;
const isHttp = (v: Record<string, unknown>) => v.type === 'http';
const isEmail = (v: Record<string, unknown>) => v.type === 'email';
const isCode = (v: Record<string, unknown>) => v.type === 'code_execution';
const isHttpBearer = (v: Record<string, unknown>) =>
  v.type === 'http' && v.http_auth_type === 'bearer';
const isHttpApiKey = (v: Record<string, unknown>) =>
  v.type === 'http' && v.http_auth_type === 'api_key';
const isHttpBasic = (v: Record<string, unknown>) =>
  v.type === 'http' && v.http_auth_type === 'basic';

function getHttpMethodOptions() {
  return [
    { label: 'GET', value: 'GET' },
    { label: 'POST', value: 'POST' },
    { label: 'PUT', value: 'PUT' },
    { label: 'PATCH', value: 'PATCH' },
    { label: 'DELETE', value: 'DELETE' },
  ];
}

function getAuthTypeOptions() {
  return [
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.none'),
      value: 'none',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.bearer'),
      value: 'bearer',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.api_key'),
      value: 'api_key',
    },
    {
      label: $t('admin.ai.skill.httpConfig.authTypeOptions.basic'),
      value: 'basic',
    },
  ];
}

const isSystemSkill = ref(false);
const isPluginSkill = ref(false);
const pluginSourceName = ref('');

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
      dependencies: {
        triggerFields: ['_mode'],
        if: (values: Record<string, unknown>) => values._mode !== 'edit',
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
      dependencies: {
        triggerFields: ['type'],
        componentProps: (values: Record<string, unknown>) => ({
          disabled: isPluginSkill.value,
          options: getSkillTypeOptions(values.type as string),
        }),
      },
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
        if: (values: Record<string, unknown>) =>
          !!values.type && !isPluginSkill.value,
        componentProps: (values: Record<string, unknown>) => {
          const key = `admin.ai.skill.typeDesc.${values.type as string}`;
          const text = $t(key);
          return {
            type: 'info',
            showIcon: true,
            message: text === key ? '' : text,
          };
        },
      },
    },
    {
      component: 'Alert',
      fieldName: '_plugin_source',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'warning',
        showIcon: true,
        message: '',
      },
      dependencies: {
        triggerFields: ['type'],
        if: () => isPluginSkill.value,
        componentProps: () => ({
          type: 'warning',
          showIcon: true,
          message: $t('admin.ai.skill.pluginTools.managedBy', {
            plugin: pluginSourceName.value,
          }),
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
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.toolkitEditor.title'),
      }),
      dependencies: { triggerFields: ['type'], if: isToolkit },
    },
    {
      component: 'ToolkitEditor',
      fieldName: 'toolkit_content',
      label: $t('admin.ai.skill.toolkitEditor.sourceCode'),
      componentProps: {
        parseApi: parseToolkitApi,
        localePrefix: 'admin.ai.skill',
        onParseComplete: (schema: null | Record<string, unknown>) => {
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
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.knowledgeBaseConfig.title'),
      }),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      component: 'ApiSelect',
      componentProps: {
        allowClear: true,
        api: getKbSelectOptions,
        class: 'w-full',
        mode: 'multiple',
        placeholder: $t(
          'admin.ai.skill.knowledgeBaseConfig.selectKbPlaceholder',
        ),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'kb_ids',
      label: $t('admin.ai.skill.knowledgeBaseConfig.selectKb'),
      help: $t('admin.ai.skill.knowledgeBaseConfig.selectKbHelp'),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...switchField(
        'rag_enabled',
        $t('admin.ai.skill.knowledgeBaseConfig.ragEnabled'),
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField(
        'rag_top_k',
        $t('admin.ai.skill.knowledgeBaseConfig.topK'),
        { min: 1, max: 20 },
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField(
        'rag_score_threshold',
        $t('admin.ai.skill.knowledgeBaseConfig.scoreThreshold'),
        { min: 0, max: 1 },
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...select(
        'rag_search_mode',
        $t('admin.ai.skill.knowledgeBaseConfig.searchMode'),
        { options: getSearchModeOptions() },
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...select(
        'rag_rewrite_strategy',
        $t('admin.ai.skill.knowledgeBaseConfig.rewriteStrategy'),
        { options: getRewriteStrategyOptions() },
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...switchField(
        'rag_reranker_enabled',
        $t('admin.ai.skill.knowledgeBaseConfig.rerankerEnabled'),
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    {
      ...numberField(
        'rag_context_token_ratio',
        $t('admin.ai.skill.knowledgeBaseConfig.contextTokenRatio'),
        { min: 0, max: 1 },
      ),
      dependencies: { triggerFields: ['type'], if: isKb },
    },
    // ============ builtin 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_builtin_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.builtinTools.title'),
      }),
      dependencies: {
        triggerFields: ['type'],
        if: (v: Record<string, unknown>) => v.type === 'builtin',
      },
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
      dependencies: {
        triggerFields: ['type'],
        if: (v: Record<string, unknown>) => v.type === 'builtin',
      },
    },
    // ============ http 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_http_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.httpConfig.title'),
      }),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...inputField('http_url', $t('admin.ai.skill.httpConfig.url'), {
        required: true,
        placeholder: $t('admin.ai.skill.httpConfig.urlPlaceholder'),
      }),
      help: $t('admin.ai.skill.httpConfig.urlHelp'),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...select('http_method', $t('admin.ai.skill.httpConfig.method'), {
        options: getHttpMethodOptions(),
      }),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...textareaField(
        'http_headers',
        $t('admin.ai.skill.httpConfig.headers'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.headersPlaceholder'),
          rows: 3,
        },
      ),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...textareaField(
        'http_body_template',
        $t('admin.ai.skill.httpConfig.bodyTemplate'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.bodyTemplatePlaceholder'),
          rows: 4,
        },
      ),
      help: $t('admin.ai.skill.httpConfig.bodyTemplateHelp'),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...textareaField(
        'http_query_params',
        $t('admin.ai.skill.httpConfig.queryParams'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.queryParamsPlaceholder'),
          rows: 2,
        },
      ),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...select('http_auth_type', $t('admin.ai.skill.httpConfig.authType'), {
        options: getAuthTypeOptions(),
      }),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    {
      ...inputField(
        'http_auth_token',
        $t('admin.ai.skill.httpConfig.authToken'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.authTokenPlaceholder'),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: isHttpBearer,
      },
    },
    {
      ...inputField(
        'http_auth_key_name',
        $t('admin.ai.skill.httpConfig.authKeyName'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.authKeyNamePlaceholder'),
        },
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: isHttpApiKey,
      },
    },
    {
      ...inputField(
        'http_auth_key_value',
        $t('admin.ai.skill.httpConfig.authKeyValue'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: isHttpApiKey,
      },
    },
    {
      ...inputField(
        'http_auth_username',
        $t('admin.ai.skill.httpConfig.authUsername'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: isHttpBasic,
      },
    },
    {
      ...inputField(
        'http_auth_password',
        $t('admin.ai.skill.httpConfig.authPassword'),
      ),
      dependencies: {
        triggerFields: ['type', 'http_auth_type'],
        if: isHttpBasic,
      },
    },
    {
      ...inputField(
        'http_response_path',
        $t('admin.ai.skill.httpConfig.responsePath'),
        {
          placeholder: $t('admin.ai.skill.httpConfig.responsePathPlaceholder'),
        },
      ),
      help: $t('admin.ai.skill.httpConfig.responsePathHelp'),
      dependencies: { triggerFields: ['type'], if: isHttp },
    },
    // ============ email 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_email_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.emailConfig.title'),
      }),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      component: 'Alert',
      fieldName: '_email_smtp_hint',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.emailConfig.smtpHint'),
      },
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      ...inputField(
        'email_subject_prefix',
        $t('admin.ai.skill.emailConfig.subjectPrefix'),
        {
          placeholder: $t(
            'admin.ai.skill.emailConfig.subjectPrefixPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.emailConfig.subjectPrefixHelp'),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      ...inputField(
        'email_allowed_domains',
        $t('admin.ai.skill.emailConfig.allowedDomains'),
        {
          placeholder: $t(
            'admin.ai.skill.emailConfig.allowedDomainsPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.emailConfig.allowedDomainsHelp'),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      ...numberField(
        'email_max_recipients',
        $t('admin.ai.skill.emailConfig.maxRecipients'),
        {
          min: 1,
          max: 50,
        },
      ),
      help: $t('admin.ai.skill.emailConfig.maxRecipientsHelp'),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      ...switchField(
        'email_require_confirmation',
        $t('admin.ai.skill.emailConfig.requireConfirmation'),
      ),
      help: $t('admin.ai.skill.emailConfig.requireConfirmationHelp'),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    {
      ...switchField(
        'email_allow_cc',
        $t('admin.ai.skill.emailConfig.allowCc'),
      ),
      dependencies: { triggerFields: ['type'], if: isEmail },
    },
    // ============ code_execution 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_code_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.codeExecutionConfig.title'),
      }),
      dependencies: { triggerFields: ['type'], if: isCode },
    },
    {
      component: 'Alert',
      fieldName: '_code_sandbox_hint',
      label: '',
      hideLabel: true,
      componentProps: {
        type: 'info',
        showIcon: true,
        message: $t('admin.ai.skill.codeExecutionConfig.sandboxHint'),
      },
      dependencies: { triggerFields: ['type'], if: isCode },
    },
    {
      ...select(
        'code_language',
        $t('admin.ai.skill.codeExecutionConfig.language'),
        {
          options: [
            {
              label: $t(
                'admin.ai.skill.codeExecutionConfig.languageOptions.python',
              ),
              value: 'python',
            },
          ],
        },
      ),
      dependencies: { triggerFields: ['type'], if: isCode },
    },
    {
      ...numberField(
        'code_memory_limit_mb',
        $t('admin.ai.skill.codeExecutionConfig.memoryLimitMb'),
        {
          min: 64,
          max: 1024,
        },
      ),
      help: $t('admin.ai.skill.codeExecutionConfig.memoryLimitHelp'),
      dependencies: { triggerFields: ['type'], if: isCode },
    },
    {
      ...inputField(
        'code_allowed_modules',
        $t('admin.ai.skill.codeExecutionConfig.allowedModules'),
        {
          placeholder: $t(
            'admin.ai.skill.codeExecutionConfig.allowedModulesPlaceholder',
          ),
        },
      ),
      help: $t('admin.ai.skill.codeExecutionConfig.allowedModulesHelp'),
      dependencies: { triggerFields: ['type'], if: isCode },
    },
    // ============ data_intelligence 专属字段 ============
    {
      component: 'Divider',
      fieldName: '_di_config_divider',
      label: '',
      hideLabel: true,
      componentProps: { orientation: 'left', dashed: true },
      renderComponentContent: () => ({
        default: () => $t('admin.ai.skill.dataIntelligenceConfig.title'),
      }),
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
        allowClear: true,
        api: getTablePolicySelectOptions,
        class: 'w-full',
        mode: 'multiple',
        placeholder: $t(
          'admin.ai.skill.dataIntelligenceConfig.tablePoliciesPlaceholder',
        ),
        showSearch: true,
        optionFilterProp: 'label',
      },
      fieldName: 'di_table_policy_ids',
      label: $t('admin.ai.skill.dataIntelligenceConfig.tablePolicies'),
      help: $t('admin.ai.skill.dataIntelligenceConfig.tablePoliciesHelp'),
      dependencies: { triggerFields: ['type'], if: isDiNonSystem },
    },
    {
      ...numberField(
        'di_max_rows_override',
        $t('admin.ai.skill.dataIntelligenceConfig.maxRowsOverride'),
        { min: 0, max: 10_000 },
      ),
      help: $t('admin.ai.skill.dataIntelligenceConfig.maxRowsOverrideHelp'),
      dependencies: { triggerFields: ['type'], if: isDiNonSystem },
    },
  ];
}

function getFormDefaults(): Record<string, unknown> {
  // 重置插件技能状态
  isPluginSkill.value = false;
  pluginSourceName.value = '';
  pluginTools.value = [];
  builtinTools.value = [];
  diTools.value = [];
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
    // http defaults
    http_url: '',
    http_method: 'GET',
    http_headers: '',
    http_body_template: '',
    http_query_params: '',
    http_auth_type: 'none',
    http_auth_token: '',
    http_auth_key_name: 'X-API-Key',
    http_auth_key_value: '',
    http_auth_username: '',
    http_auth_password: '',
    http_response_path: '',
    // email defaults
    email_subject_prefix: '',
    email_allowed_domains: '',
    email_max_recipients: 5,
    email_require_confirmation: true,
    email_allow_cc: true,
    // code_execution defaults
    code_language: 'python',
    code_memory_limit_mb: 256,
    code_allowed_modules:
      'math,json,datetime,re,collections,itertools,functools,statistics,random,string',
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
    let config: null | Record<string, unknown> = null;
    const type = values.type as string;

    switch (type) {
      case 'code_execution': {
        const modulesRaw = (values.code_allowed_modules as string) || '';
        config = {
          language: values.code_language || 'python',
          memory_limit_mb: values.code_memory_limit_mb ?? 256,
          allowed_modules: modulesRaw
            ? modulesRaw
                .split(',')
                .map((m: string) => m.trim())
                .filter(Boolean)
            : [],
        };

        break;
      }
      case 'data_intelligence': {
        config = {
          table_policy_ids: values.di_table_policy_ids || [],
          max_rows_override: values.di_max_rows_override ?? 0,
        };

        break;
      }
      case 'email': {
        const domainsRaw = (values.email_allowed_domains as string) || '';
        config = {
          subject_prefix: values.email_subject_prefix || '',
          allowed_domains: domainsRaw
            ? domainsRaw
                .split(',')
                .map((d: string) => d.trim())
                .filter(Boolean)
            : [],
          max_recipients: values.email_max_recipients ?? 5,
          require_confirmation: values.email_require_confirmation ?? true,
          allow_cc: values.email_allow_cc ?? true,
        };

        break;
      }
      case 'http': {
        let headers: Record<string, string> = {};
        let queryParams: Record<string, string> = {};
        try {
          headers = JSON.parse((values.http_headers as string) || '{}');
        } catch {
          /* empty */
        }
        try {
          queryParams = JSON.parse(
            (values.http_query_params as string) || '{}',
          );
        } catch {
          /* empty */
        }
        const authConfig: Record<string, string> = {};
        const authType = (values.http_auth_type as string) || 'none';
        if (authType === 'bearer')
          authConfig.token = (values.http_auth_token as string) || '';
        if (authType === 'api_key') {
          authConfig.key_name =
            (values.http_auth_key_name as string) || 'X-API-Key';
          authConfig.key_value = (values.http_auth_key_value as string) || '';
        }
        if (authType === 'basic') {
          authConfig.username = (values.http_auth_username as string) || '';
          authConfig.password = (values.http_auth_password as string) || '';
        }
        config = {
          url: values.http_url || '',
          method: values.http_method || 'GET',
          headers,
          body_template: values.http_body_template || '',
          query_params: queryParams,
          auth_type: authType,
          auth_config: authConfig,
          response_path: values.http_response_path || '',
        };

        break;
      }
      case 'knowledge_base': {
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

        break;
      }
      case 'toolkit': {
        const valvesConfig = values.valves_config as
          | Record<string, unknown>
          | undefined;
        config =
          valvesConfig && Object.keys(valvesConfig).length > 0
            ? { valves: valvesConfig }
            : null;

        break;
      }
      // No default
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

    // 插件技能检测：使用 API 返回的 source_plugin 字段
    isPluginSkill.value = !!data.source_plugin;
    pluginSourceName.value = data.source_plugin || '';

    builtinTools.value =
      data.type === 'builtin' && Array.isArray(cfg.tools)
        ? (cfg.tools as BuiltinToolInfo[])
        : [];

    // 加载数据智能技能的可用工具信息
    if (data.type === 'data_intelligence') {
      loadDiTools(data.is_system, cfg.table_policy_ids as number[] | undefined);
    } else {
      diTools.value = [];
    }

    // 插件技能工具列表：优先使用 API 返回的 plugin_tools，fallback 到单独 API
    if (data.source_plugin && Array.isArray(data.plugin_tools)) {
      pluginTools.value = data.plugin_tools;
    } else {
      const standardTypes = new Set([
        'builtin',
        'code_execution',
        'data_intelligence',
        'email',
        'http',
        'knowledge_base',
        'toolkit',
      ]);
      if (data.id && !standardTypes.has(data.type)) {
        loadPluginTools(data.id);
      } else {
        pluginTools.value = [];
      }
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
      // http fields
      http_url: (cfg.url as string) || '',
      http_method: (cfg.method as string) || 'GET',
      http_headers: cfg.headers ? JSON.stringify(cfg.headers, null, 2) : '',
      http_body_template: (cfg.body_template as string) || '',
      http_query_params: cfg.query_params
        ? JSON.stringify(cfg.query_params, null, 2)
        : '',
      http_auth_type: (cfg.auth_type as string) || 'none',
      http_auth_token: (cfg.auth_config as Record<string, string>)?.token || '',
      http_auth_key_name:
        (cfg.auth_config as Record<string, string>)?.key_name || 'X-API-Key',
      http_auth_key_value:
        (cfg.auth_config as Record<string, string>)?.key_value || '',
      http_auth_username:
        (cfg.auth_config as Record<string, string>)?.username || '',
      http_auth_password:
        (cfg.auth_config as Record<string, string>)?.password || '',
      http_response_path: (cfg.response_path as string) || '',
      // email fields
      email_subject_prefix: (cfg.subject_prefix as string) || '',
      email_allowed_domains: Array.isArray(cfg.allowed_domains)
        ? (cfg.allowed_domains as string[]).join(', ')
        : '',
      email_max_recipients: (cfg.max_recipients as number) ?? 5,
      email_require_confirmation: (cfg.require_confirmation as boolean) ?? true,
      email_allow_cc: (cfg.allow_cc as boolean) ?? true,
      // code_execution fields
      code_language: (cfg.language as string) || 'python',
      code_memory_limit_mb: (cfg.memory_limit_mb as number) ?? 256,
      code_allowed_modules: Array.isArray(cfg.allowed_modules)
        ? (cfg.allowed_modules as string[]).join(',')
        : '',
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: async (id) => {
    return await getSkillDetailApi(id as number);
  },
});

async function loadDiTools(isSystem: boolean, tablePolicyIds?: number[]) {
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
        description: $t(
          'admin.ai.skill.dataIntelligenceConfig.tools.dataQuery',
        ),
        tables: readTables,
      });
    }
    const createTables = policies
      .filter((p) => p.allow_create)
      .map((p) => `${p.label} (${p.table_name})`);
    if (createTables.length > 0) {
      tools.push({
        name: 'data_create',
        description: $t(
          'admin.ai.skill.dataIntelligenceConfig.tools.dataCreate',
        ),
        tables: createTables,
      });
    }
    const updateTables = policies
      .filter((p) => p.allow_update)
      .map((p) => `${p.label} (${p.table_name})`);
    if (updateTables.length > 0) {
      tools.push({
        name: 'data_update',
        description: $t(
          'admin.ai.skill.dataIntelligenceConfig.tools.dataUpdate',
        ),
        tables: updateTables,
      });
    }
    const deleteTables = policies
      .filter((p) => p.allow_delete)
      .map((p) => `${p.label} (${p.table_name})`);
    if (deleteTables.length > 0) {
      tools.push({
        name: 'data_delete',
        description: $t(
          'admin.ai.skill.dataIntelligenceConfig.tools.dataDelete',
        ),
        tables: deleteTables,
      });
    }
    diTools.value = tools;
  } catch {
    diTools.value = [];
  }
}

async function loadPluginTools(skillId: number) {
  try {
    pluginTools.value = await getSkillToolsApi(skillId);
  } catch {
    pluginTools.value = [];
  }
}

const title = computed(() =>
  isEdit.value ? $t('admin.common.edit') : $t('admin.ai.skill.create'),
);

const currentSkillType = ref('');
watch(
  () => formApi.form?.values?.type,
  (v) => {
    currentSkillType.value = (v as string) || '';
  },
  { immediate: true },
);
const drawerWidthClass = computed(() =>
  currentSkillType.value === 'toolkit' && !isPluginSkill.value
    ? 'w-[900px]'
    : 'w-[600px]',
);
</script>

<template>
  <Drawer :title="title" :class="drawerWidthClass">
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
            <span class="text-xs text-muted-foreground">{{
              tool.description
            }}</span>
          </div>
          <div class="mt-1 flex flex-wrap gap-1">
            <Tag v-for="table in tool.tables" :key="table" class="!text-[10px]">
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

    <!-- 插件技能工具列表只读展示 -->
    <template v-if="pluginTools.length > 0">
      <Divider orientation="left" dashed>
        {{ $t('admin.ai.skill.pluginTools.toolList') }}
        <Tag color="blue" class="ml-2">{{ pluginTools.length }}</Tag>
      </Divider>
      <div class="flex flex-col gap-2">
        <div
          v-for="tool in pluginTools"
          :key="tool.name"
          class="rounded-lg border border-border/60 p-3"
        >
          <div class="mb-1 flex items-center gap-2">
            <Tag color="processing">{{ tool.name }}</Tag>
            <span v-if="tool.timeout" class="text-[10px] text-muted-foreground">
              {{ tool.timeout }}s
            </span>
          </div>
          <p class="mb-0 text-xs text-muted-foreground">
            {{ tool.description }}
          </p>
          <div v-if="tool.parameters?.length" class="mt-2 flex flex-wrap gap-1">
            <Tag
              v-for="param in tool.parameters"
              :key="param.name"
              :color="param.required ? 'orange' : 'default'"
              class="!text-[10px]"
            >
              {{ param.name }}: {{ param.type }}
            </Tag>
          </div>
        </div>
      </div>
    </template>
  </Drawer>
</template>
