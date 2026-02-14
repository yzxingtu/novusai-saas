<script lang="ts" setup>
defineOptions({ name: 'TenantSkillForm' });
/**
 * 租户端技能新建/编辑表单抽屉
 */
import type { SkillInfo } from '#/api/tenant/skills';

import { computed, ref } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getTenantTablePoliciesApi } from '#/api/tenant/ai';
import { getSkillDetailApi } from '#/api/tenant/skills';
import { Divider, Tag } from 'ant-design-vue';

import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

interface BuiltinToolInfo {
  name: string;
  description: string;
  parameters?: { properties?: Record<string, { type?: string; description?: string }> };
}
const builtinTools = ref<BuiltinToolInfo[]>([]);

interface DiToolInfo {
  name: string;
  description: string;
  tables: string[];
}
const diTools = ref<DiToolInfo[]>([]);

const emits = defineEmits<{ success: [] }>();

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

    if (data.type === 'builtin' && Array.isArray(cfg.tools)) {
      builtinTools.value = cfg.tools as BuiltinToolInfo[];
    } else {
      builtinTools.value = [];
    }

    if (data.type === 'data_intelligence') {
      loadDiTools(cfg.table_policy_ids as number[] | undefined);
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
    const policies = (await getTenantTablePoliciesApi()).filter((p) => p.is_active);
    const filtered = tablePolicyIds && tablePolicyIds.length > 0
      ? policies.filter((p) => tablePolicyIds.includes(p.id))
      : policies;
    const tools: DiToolInfo[] = [];
    const readTables = filtered.filter((p) => p.allow_read).map((p) => `${p.label} (${p.table_name})`);
    if (readTables.length > 0) tools.push({ name: 'data_query', description: $t('tenant.ai.skill.dataIntelligenceConfig.tools.dataQuery'), tables: readTables });
    const createTables = filtered.filter((p) => p.allow_create).map((p) => `${p.label} (${p.table_name})`);
    if (createTables.length > 0) tools.push({ name: 'data_create', description: $t('tenant.ai.skill.dataIntelligenceConfig.tools.dataCreate'), tables: createTables });
    const updateTables = filtered.filter((p) => p.allow_update).map((p) => `${p.label} (${p.table_name})`);
    if (updateTables.length > 0) tools.push({ name: 'data_update', description: $t('tenant.ai.skill.dataIntelligenceConfig.tools.dataUpdate'), tables: updateTables });
    const deleteTables = filtered.filter((p) => p.allow_delete).map((p) => `${p.label} (${p.table_name})`);
    if (deleteTables.length > 0) tools.push({ name: 'data_delete', description: $t('tenant.ai.skill.dataIntelligenceConfig.tools.dataDelete'), tables: deleteTables });
    diTools.value = tools;
  } catch {
    diTools.value = [];
  }
}

defineExpose({ openNew, openEdit });

const title = computed(() =>
  isEdit.value
    ? $t('common.edit')
    : $t('tenant.ai.skill.create'),
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
  </Drawer>
</template>
