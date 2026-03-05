<script lang="ts" setup>
/**
 * 租户端技能新建/编辑表单抽屉
 */
import type { PluginToolDefinition, SkillInfo } from '#/api/tenant/skills';

import { computed, ref } from 'vue';

import { Divider, Tag } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantTablePoliciesApi } from '#/api/tenant/ai';
import { getSkillDetailApi } from '#/api/tenant/skills';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'TenantSkillForm' });

const emits = defineEmits<{ success: [] }>();
interface BuiltinToolInfo {
  name: string;
  description: string;
  parameters?: {
    properties?: Record<string, { description?: string; type?: string }>;
  };
}
const builtinTools = ref<BuiltinToolInfo[]>([]);
const pluginTools = ref<PluginToolDefinition[]>([]);
const isPluginSkill = ref(false);
const pluginSourceName = ref('');

interface DiToolInfo {
  name: string;
  description: string;
  tables: string[];
}
const diTools = ref<DiToolInfo[]>([]);

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit, openNew, openEdit } = useCrudDrawer<SkillInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  apiPath: '/tenant/ai/skills',
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
      config,
      is_active: values.is_active ?? true,
    };

    if (type === 'toolkit') {
      result.toolkit_content = values.toolkit_content || '';
    }

    return result;
  },
  toFormValues: (data) => {
    const cfg = (data.config ?? {}) as Record<string, unknown>;
    const ragCfg = (cfg.rag_config ?? {}) as Record<string, unknown>;

    // 插件技能检测
    isPluginSkill.value = !!data.source_plugin;
    pluginSourceName.value = data.source_plugin || '';

    builtinTools.value =
      data.type === 'builtin' && Array.isArray(cfg.tools)
        ? (cfg.tools as BuiltinToolInfo[])
        : [];

    if (data.type === 'data_intelligence') {
      loadDiTools(cfg.table_policy_ids as number[] | undefined);
    } else {
      diTools.value = [];
    }

    // 插件技能工具列表
    pluginTools.value =
      data.source_plugin && Array.isArray(data.plugin_tools)
        ? data.plugin_tools
        : [];

    return {
      package_id: data.package_id,
      name: data.name,
      type: data.type,
      description: data.description,
      timeout: data.timeout,
      is_active: data.is_active,
      toolkit_content: data.toolkit_content || '',
      valves_config: (cfg.valves as Record<string, unknown>) || {},
      // knowledge_base fields
      kb_ids: (cfg.knowledge_base_ids as number[]) || [],
      rag_enabled: (ragCfg.enabled as boolean) ?? true,
      rag_top_k: (ragCfg.top_k as number) ?? 5,
      rag_score_threshold: (ragCfg.score_threshold as number) ?? 0.5,
      rag_search_mode: (ragCfg.search_mode as string) || 'hybrid',
      rag_rewrite_strategy: (ragCfg.rewrite_strategy as string) || 'none',
      rag_reranker_enabled: (ragCfg.reranker_enabled as boolean) ?? false,
      rag_context_token_ratio: (ragCfg.context_token_ratio as number) ?? 0.3,
      // data_intelligence fields
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

async function loadDiTools(tablePolicyIds?: number[]) {
  try {
    const allPolicies = await getTenantTablePoliciesApi();
    const policies = allPolicies.filter((p) => p.is_active);
    const filtered =
      tablePolicyIds && tablePolicyIds.length > 0
        ? policies.filter((p) => tablePolicyIds.includes(p.id))
        : policies;
    const tools: DiToolInfo[] = [];
    const readTables = filtered
      .filter((p) => p.allow_read)
      .map((p) => `${p.label} (${p.table_name})`);
    if (readTables.length > 0)
      tools.push({
        name: 'data_query',
        description: $t(
          'tenant.ai.skill.dataIntelligenceConfig.tools.dataQuery',
        ),
        tables: readTables,
      });
    const createTables = filtered
      .filter((p) => p.allow_create)
      .map((p) => `${p.label} (${p.table_name})`);
    if (createTables.length > 0)
      tools.push({
        name: 'data_create',
        description: $t(
          'tenant.ai.skill.dataIntelligenceConfig.tools.dataCreate',
        ),
        tables: createTables,
      });
    const updateTables = filtered
      .filter((p) => p.allow_update)
      .map((p) => `${p.label} (${p.table_name})`);
    if (updateTables.length > 0)
      tools.push({
        name: 'data_update',
        description: $t(
          'tenant.ai.skill.dataIntelligenceConfig.tools.dataUpdate',
        ),
        tables: updateTables,
      });
    const deleteTables = filtered
      .filter((p) => p.allow_delete)
      .map((p) => `${p.label} (${p.table_name})`);
    if (deleteTables.length > 0)
      tools.push({
        name: 'data_delete',
        description: $t(
          'tenant.ai.skill.dataIntelligenceConfig.tools.dataDelete',
        ),
        tables: deleteTables,
      });
    diTools.value = tools;
  } catch {
    diTools.value = [];
  }
}

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value ? $t('common.edit') : $t('tenant.ai.skill.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[800px]">
    <Form />

    <!-- data_intelligence 工具列表只读展示 -->
    <template v-if="diTools.length > 0">
      <Divider orientation="left" dashed>
        {{ $t('tenant.ai.skill.dataIntelligenceConfig.toolListTitle') }}
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
        {{ $t('tenant.ai.skill.builtinTools.toolList') }}
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
        {{ $t('tenant.ai.skill.pluginTools.toolList') }}
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
