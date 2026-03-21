<script lang="ts" setup>
/**
 * 企业端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 */
import type {
  AgentInfo,
  AgentKBBindingInfo,
  AgentMemoryConfig,
  AgentSkillBindingInfo,
} from '#/api/tenant/agents';

import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useDetailPageAi } from '#/composables/use-detail-page-ai';
import { usePageAIRegistration } from '#/composables/use-page-ai-registration';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Select as ASelect,
  Button,
  Empty,
  InputNumber,
  message,
  Popconfirm,
  Spin,
  Switch,
  TabPane,
  Tabs,
  Tag,
  Textarea,
  Upload,
} from 'ant-design-vue';

import {
  batchBindKBsApi,
  bindSingleAgentKBApi,
  getAgentDetailApi,
  getAgentKBsApi,
  getAgentMemoryConfigApi,
  getAgentSkillsApi,
  suppressPlatformKbApi,
  unbindKBApi,
  unsuppressPlatformKbApi,
  updateAgentApi,
  updateAgentKBBindingApi,
  updateAgentMemoryConfigApi,
} from '#/api/tenant/agents';
import { getKnowledgeBaseListApi } from '#/api/tenant/knowledge-bases';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { getSkillPackageSkillsApi } from '#/api/tenant/skill-packages';
import { smartUploadFile } from '#/api/tenant/attachment';
import { $t } from '#/locales';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';
import { toAvatarDisplayUrl } from '#/utils/image';
import { getScopeColor, getScopeIcon, getScopeText } from '#/utils/scope-helpers';
import type { InputVariable } from '#/components/business/ai-chat-panel/types';
import InputVariablesEditor from '#/components/business/input-variables-editor/InputVariablesEditor.vue';

import {
  getExecutionModeText,
  getStatusColor,
  getStatusText,
} from './data';
import AccessConfigDrawer from './modules/AccessConfigDrawer.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'TenantAgentDetail' });

// ==================== AccessConfig Drawer ====================
const [AccessConfigDrawerCmp, accessConfigApi] = useVbenDrawer({
  connectedComponent: AccessConfigDrawer,
});

function openAccessConfig() {
  if (!agent.value) return;
  accessConfigApi.setData({
    id: agent.value.id,
    name: agent.value.name,
  });
  accessConfigApi.open();
}

// ==================== VersionHistory Drawer ====================
const [VersionHistoryDrawerCmp, versionHistoryApi] = useVbenDrawer({
  connectedComponent: VersionHistoryDrawer,
});

function openVersionHistory() {
  if (!agent.value) return;
  versionHistoryApi.setData({
    id: agent.value.id,
    publishedVersion: agent.value.published_version ?? null,
  });
  versionHistoryApi.open();
}

// ==================== Route ====================
const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

// ==================== State ====================
const loading = ref(false);
const saving = ref(false);
const agent = ref<AgentInfo | null>(null);
const activeTab = ref('overview');
const memoryLoading = ref(false);
const memorySaving = ref(false);
const memoryConfig = ref<AgentMemoryConfig | null>(null);
const tenantMemoryDisabled = ref(false);

// ==================== Load ====================
async function loadMemoryConfig() {
  memoryLoading.value = true;
  try {
    memoryConfig.value = await getAgentMemoryConfigApi(agentId.value);
    tenantMemoryDisabled.value =
      memoryConfig.value.tenant_agent_memory_disabled;
  } catch {
    message.error($t('common.loadFailed'));
  } finally {
    memoryLoading.value = false;
  }
}

async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAgentDetailApi(agentId.value);
    await loadMemoryConfig();
  } catch {
    message.error($t('common.loadFailed'));
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadAgent();
  const tab = route.query.tab as string | undefined;
  if (tab) {
    activeTab.value = tab;
    onTabChange(tab);
  }
});
watch(agentId, loadAgent);

function goBack() {
  router.push('/tenant/ai/agents');
}

const isRoutingEnabled = computed(() =>
  Boolean(
    (agent.value?.routing_config as null | Record<string, unknown> | undefined)
      ?.enable_routing,
  ),
);

function jumpToRoutingTab() {
  activeTab.value = 'routing';
  onTabChange('routing');
}

function getExecutionModeIcon(mode: string): string {
  switch (mode) {
    case 'api': {
      return 'lucide:code';
    }
    case 'batch': {
      return 'lucide:layers';
    }
    case 'conversation': {
      return 'lucide:message-circle';
    }
    case 'task': {
      return 'lucide:list-checks';
    }
    default: {
      return 'lucide:bot';
    }
  }
}

// ==================== Generic Save ====================
async function saveFields(fields: Record<string, unknown>) {
  if (!agent.value) return;
  saving.value = true;
  try {
    agent.value = await updateAgentApi(agentId.value, fields);
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  } finally {
    saving.value = false;
  }
}

// ==================== Avatar Upload ====================
const avatarUploading = ref(false);

const avatarDisplayUrl = computed(() => {
  const val = agent.value?.avatar;
  return val ? toAvatarDisplayUrl(val) : '';
});

const avatarInitial = computed(() =>
  (agent.value?.name || '?').charAt(0).toUpperCase(),
);

function beforeAvatarUpload(file: File) {
  const isImage = file.type.startsWith('image/');
  if (!isImage) {
    message.error($t('tenant.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('tenant.profile.messages.avatarSizeError'));
    return false;
  }
  handleAvatarUpload(file);
  return false;
}

async function handleAvatarUpload(file: File) {
  if (!agent.value) return;
  avatarUploading.value = true;
  try {
    const result = await smartUploadFile({
      file,
      visibility: 'public',
      business_type: 'avatar',
    });
    const attachmentId = String(result.attachment?.id || '');
    if (!attachmentId) throw new Error('Upload failed');
    agent.value = await updateAgentApi(agentId.value, { avatar: attachmentId });
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('shared.common.uploadFailed'));
  } finally {
    avatarUploading.value = false;
  }
}

async function removeAvatar() {
  if (!agent.value) return;
  avatarUploading.value = true;
  try {
    agent.value = await updateAgentApi(agentId.value, { avatar: null });
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  } finally {
    avatarUploading.value = false;
  }
}

async function updateTenantMemoryDisabled(disabled: boolean) {
  if (!isTenantOwned.value) return;
  const previous = tenantMemoryDisabled.value;
  tenantMemoryDisabled.value = disabled;
  memorySaving.value = true;
  try {
    memoryConfig.value = await updateAgentMemoryConfigApi(agentId.value, {
      disabled,
    });
    tenantMemoryDisabled.value =
      memoryConfig.value.tenant_agent_memory_disabled;
    message.success($t('tenant.ai.agent.memory.saveSuccess'));
  } catch {
    tenantMemoryDisabled.value = previous;
    message.error($t('common.saveFailed'));
  } finally {
    memorySaving.value = false;
  }
}

// ==================== Scope Protection ====================
const isTenantOwned = computed(() => agent.value?.owner_type === 'tenant');
/** 平台下发智能体：可追加本企业知识库，不可改平台全局绑定 / Platform agent: tenant KB overlay */
const isPlatformAssignedAgent = computed(
  () => agent.value?.owner_type === 'platform',
);
const canManageKnowledgeBases = computed(
  () => isTenantOwned.value || isPlatformAssignedAgent.value,
);
function isKbBindingReadonly(binding: AgentKBBindingInfo) {
  return binding.binding_scope === 'platform';
}

// ==================== Overview Tab ====================
const editingPrompt = ref(false);
const promptDraft = ref('');

function startEditPrompt() {
  promptDraft.value = agent.value?.system_prompt || '';
  editingPrompt.value = true;
}

function cancelEditPrompt() {
  editingPrompt.value = false;
}

async function savePrompt() {
  await saveFields({ system_prompt: promptDraft.value });
  editingPrompt.value = false;
}

// ==================== Model Params Tab ====================
const modelTemp = ref(0.7);
const modelMaxTokens = ref<number | undefined>(undefined);
const modelTopP = ref<number | undefined>(undefined);
const chatModelMaxOutputTokens = ref<Record<number, number | undefined>>({});

function initModelParams() {
  if (!agent.value) return;
  modelTemp.value = agent.value.temperature ?? 0.7;
  modelMaxTokens.value = agent.value.max_tokens ?? undefined;
  modelTopP.value = agent.value.top_p ?? undefined;
}

async function saveModelParams() {
  const modelLimit = agent.value?.model_id
    ? chatModelMaxOutputTokens.value[agent.value.model_id]
    : undefined;
  if (
    modelLimit != null &&
    modelMaxTokens.value != null &&
    modelMaxTokens.value > modelLimit
  ) {
    message.warning(
      $t('tenant.ai.agent.validation.maxTokensExceedsModelLimit', {
        limit: modelLimit,
      }),
    );
    return;
  }
  await saveFields({
    temperature: modelTemp.value,
    max_tokens: modelMaxTokens.value ?? null,
    top_p: modelTopP.value ?? null,
  });
}

// ==================== Chat Config Tab ====================
const chatWelcome = ref('');
const chatSuggestions = ref('');
const chatInputVars = ref<InputVariable[]>([]);
const chatSystemPrompt = ref('');
const chatContextMessages = ref(20);
const chatContextTokens = ref(0);

/** Ref to the system prompt textarea for cursor-based variable insertion / 系统提示词输入框引用，用于插入变量 */
const chatSystemPromptRef = ref<HTMLTextAreaElement | null>(null);

function formatVarChip(name: string) {
  return `{{${name}}}`;
}

function insertVarAtCursor(varName: string) {
  const el = chatSystemPromptRef.value;
  const token = `{{${varName}}}`;
  if (!el) {
    chatSystemPrompt.value += token;
    return;
  }
  const start = el.selectionStart ?? chatSystemPrompt.value.length;
  const end = el.selectionEnd ?? start;
  chatSystemPrompt.value =
    chatSystemPrompt.value.substring(0, start) +
    token +
    chatSystemPrompt.value.substring(end);
  nextTick(() => {
    el.focus();
    const newPos = start + token.length;
    el.setSelectionRange(newPos, newPos);
  });
}

function initChatConfig() {
  if (!agent.value) return;
  chatSystemPrompt.value = agent.value.system_prompt || '';
  chatWelcome.value = agent.value.welcome_message || '';
  const sq = agent.value.suggested_questions;
  chatSuggestions.value = formatStarterQuestionsInput(
    sq as null | unknown[],
  );
  chatInputVars.value = Array.isArray(agent.value.input_variables)
    ? (agent.value.input_variables as InputVariable[])
    : [];
  const cc = (agent.value.context_config ?? {}) as Record<string, number>;
  chatContextMessages.value = cc.max_history_messages ?? 20;
  chatContextTokens.value = cc.max_history_tokens ?? 0;
}

async function saveChatConfig() {
  await saveFields({
    ...(isTenantOwned.value ? { system_prompt: chatSystemPrompt.value || null } : {}),
    welcome_message: chatWelcome.value || null,
    suggested_questions: parseStarterQuestionsInput(chatSuggestions.value),
    input_variables: chatInputVars.value.length > 0 ? chatInputVars.value : null,
    context_config: {
      max_history_messages: chatContextMessages.value,
      max_history_tokens: chatContextTokens.value,
    },
  });
}

const bindings = ref<AgentSkillBindingInfo[]>([]);
const bindingsLoading = ref(false);

const expandedPackages = reactive(new Set<number>());
const packageSkills = reactive(new Map<number, Array<{ id: number; is_active: boolean; name: string; type: string }>>());
const packageSkillsLoading = reactive(new Set<number>());

async function loadBindings() {
  bindingsLoading.value = true;
  try {
    bindings.value = await getAgentSkillsApi(agentId.value);
  } catch {
    bindings.value = [];
  } finally {
    bindingsLoading.value = false;
  }
}

async function togglePackageSkills(packageId: number) {
  if (expandedPackages.has(packageId)) {
    expandedPackages.delete(packageId);
    return;
  }
  expandedPackages.add(packageId);
  if (packageSkills.has(packageId)) return;
  packageSkillsLoading.add(packageId);
  try {
    const res = await getSkillPackageSkillsApi(packageId, { 'page[size]': 100 });
    packageSkills.set(packageId, res.items || []);
  } catch {
    packageSkills.set(packageId, []);
  } finally {
    packageSkillsLoading.delete(packageId);
  }
}


// ==================== Knowledge Base Bindings Tab ====================
const kbBindings = ref<AgentKBBindingInfo[]>([]);
const kbBindingsLoading = ref(false);
const kbOptions = ref<{ label: string; value: number }[]>([]);
const selectedNewKBs = ref<number[]>([]);
const platformKbSuppressLoadingKbId = ref<number | null>(null);

async function loadKBBindings() {
  kbBindingsLoading.value = true;
  try {
    kbBindings.value = await getAgentKBsApi(agentId.value);
  } catch {
    kbBindings.value = [];
  } finally {
    kbBindingsLoading.value = false;
  }
}

async function loadKBOptions() {
  try {
    const res = await getKnowledgeBaseListApi({ 'page[size]': 200 });
    kbOptions.value = (res.items || []).map((kb) => ({
      label: kb.name,
      value: kb.id,
    }));
  } catch {
    kbOptions.value = [];
  }
}

const unboundKBs = computed(() => {
  const boundIds = new Set(kbBindings.value.map((b) => b.knowledge_base_id));
  return kbOptions.value.filter((kb) => !boundIds.has(kb.value));
});

function getKbChunkStrategyText(strategy: null | string | undefined): string {
  switch (strategy) {
    case 'paragraph': {
      return $t('tenant.knowledgeBase.field.chunkStrategyParagraph');
    }
    case 'recursive': {
      return $t('tenant.knowledgeBase.field.chunkStrategyRecursive');
    }
    case 'semantic': {
      return $t('tenant.knowledgeBase.field.chunkStrategySemantic');
    }
    case 'sentence': {
      return $t('tenant.knowledgeBase.field.chunkStrategySentence');
    }
    default: {
      return strategy || '-';
    }
  }
}

async function bindKB() {
  if (selectedNewKBs.value.length === 0) return;
  try {
    if (isTenantOwned.value) {
      const currentIds = kbBindings.value.map((b) => b.knowledge_base_id);
      for (const kbId of selectedNewKBs.value) {
        if (!currentIds.includes(kbId)) currentIds.push(kbId);
      }
      await batchBindKBsApi(agentId.value, currentIds);
    } else {
      for (const kbId of selectedNewKBs.value) {
        await bindSingleAgentKBApi(agentId.value, {
          knowledge_base_id: kbId,
        });
      }
    }
    selectedNewKBs.value = [];
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function unbindKB(knowledgeBaseId: number) {
  try {
    await unbindKBApi(agentId.value, knowledgeBaseId);
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function toggleKBEnabled(binding: AgentKBBindingInfo) {
  if (isKbBindingReadonly(binding)) return;
  try {
    await updateAgentKBBindingApi(agentId.value, binding.id, {
      enabled: !binding.enabled,
    });
    await loadKBBindings();
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function updateKBWeight(bindingId: number, weight: number) {
  const row = kbBindings.value.find((x) => x.id === bindingId);
  if (row && isKbBindingReadonly(row)) return;
  try {
    await updateAgentKBBindingApi(agentId.value, bindingId, { weight });
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function togglePlatformKbOptOut(
  binding: AgentKBBindingInfo,
  optOut: boolean,
) {
  if (!isKbBindingReadonly(binding)) return;
  platformKbSuppressLoadingKbId.value = binding.knowledge_base_id;
  try {
    if (optOut) {
      await suppressPlatformKbApi(agentId.value, binding.knowledge_base_id);
    } else {
      await unsuppressPlatformKbApi(agentId.value, binding.knowledge_base_id);
    }
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  } finally {
    platformKbSuppressLoadingKbId.value = null;
  }
}

const ragTopK = ref(5);
const ragScoreThreshold = ref(0.5);
const ragSearchMode = ref<'hybrid' | 'keyword' | 'vector'>('hybrid');
const ragRewriteStrategy = ref<'hyde' | 'multi' | 'none'>('none');
const ragRerankerEnabled = ref(false);
const ragContextTokenRatio = ref(0.6);

const ragSearchModeOptions = [
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.hybrid'),
    value: 'hybrid',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.vector'),
    value: 'vector',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.searchModeOptions.keyword'),
    value: 'keyword',
  },
];

const ragRewriteOptions = [
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.none'),
    value: 'none',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.multi'),
    value: 'multi',
  },
  {
    label: $t('tenant.ai.agent.knowledgeBase.rewriteOptions.hyde'),
    value: 'hyde',
  },
];

function initRagConfig() {
  if (!agent.value) return;
  const rc = (agent.value.rag_config ?? {}) as Record<string, unknown>;
  ragTopK.value = (rc.top_k as number | undefined) ?? 5;
  ragScoreThreshold.value = (rc.score_threshold as number | undefined) ?? 0.5;
  ragSearchMode.value =
    ((rc.search_mode as 'hybrid' | 'keyword' | 'vector' | undefined) ??
      'hybrid');
  ragRewriteStrategy.value =
    ((rc.rewrite_strategy as 'hyde' | 'multi' | 'none' | undefined) ??
      'none');
  ragRerankerEnabled.value = Boolean(rc.reranker_enabled);
  ragContextTokenRatio.value =
    (rc.context_token_ratio as number | undefined) ?? 0.6;
}

async function saveRagConfig() {
  if (!isTenantOwned.value) return;
  await saveFields({
    rag_config: {
      search_mode: ragSearchMode.value,
      top_k: ragTopK.value,
      score_threshold: ragScoreThreshold.value,
      rewrite_strategy: ragRewriteStrategy.value,
      reranker_enabled: ragRerankerEnabled.value,
      context_token_ratio: ragContextTokenRatio.value,
    },
  });
}

// ==================== Quota Tab ====================
const quotaConversationsPerDay = ref(0);
const quotaTokensPerDay = ref(0);
const quotaTokensPerMonth = ref(0);
const quotaMaxTurns = ref(50);
const quotaMaxConcurrent = ref(10);
const quotaUserConversationsPerDay = ref(0);

function initQuota() {
  if (!agent.value) return;
  const qc = (agent.value.quota_config ?? {}) as Record<string, number>;
  quotaConversationsPerDay.value = qc.conversations_per_day ?? 0;
  quotaTokensPerDay.value = qc.daily_token_limit ?? 0;
  quotaTokensPerMonth.value = qc.monthly_token_limit ?? 0;
  quotaMaxTurns.value = qc.max_turns_per_conversation ?? 50;
  quotaMaxConcurrent.value = qc.max_concurrent ?? 10;
  quotaUserConversationsPerDay.value = qc.user_conversations_per_day ?? 0;
}

async function saveQuota() {
  if (!agent.value || !isTenantOwned.value) return;
  await saveFields({
    quota_config: {
      conversations_per_day: quotaConversationsPerDay.value,
      daily_token_limit: quotaTokensPerDay.value,
      monthly_token_limit: quotaTokensPerMonth.value,
      max_turns_per_conversation: quotaMaxTurns.value,
      max_concurrent: quotaMaxConcurrent.value,
      user_conversations_per_day: quotaUserConversationsPerDay.value,
    },
  });
}

// ==================== Routing Config Tab ====================
const routingEnabled = ref(false);
const routingMaxTier = ref<string | undefined>(undefined);
const routingVisionModelId = ref<number | undefined>(undefined);
const routingLongContextModelId = ref<number | undefined>(undefined);
const routingLongContextThreshold = ref(32_000);

const visionModelOptions = ref<{ label: string; value: number }[]>([]);
const chatModelOptions = ref<{ label: string; value: number }[]>([]);

async function loadRoutingModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    visionModelOptions.value = models
      .filter((m) => m.type === 'chat' && m.supports_vision)
      .map((m) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
    chatModelOptions.value = models
      .filter((m) => m.type === 'chat')
      .map((m) => ({
        label: `${m.name} (${m.provider_name || '-'})`,
        value: m.id,
      }));
    chatModelMaxOutputTokens.value = Object.fromEntries(
      models
        .filter((m) => m.type === 'chat')
        .map((m) => [m.id, m.max_output_tokens ?? undefined]),
    );
  } catch {
    // fallback: empty list
    chatModelMaxOutputTokens.value = {};
  }
}

const tierOptions = [
  { label: $t('tenant.ai.agent.routing.tier.fast'), value: 'fast' },
  { label: $t('tenant.ai.agent.routing.tier.standard'), value: 'standard' },
  { label: $t('tenant.ai.agent.routing.tier.premium'), value: 'premium' },
];

function initRouting() {
  if (!agent.value) return;
  const rc = (agent.value.routing_config ?? {}) as Record<string, unknown>;
  routingEnabled.value = Boolean(rc.enable_routing);
  routingMaxTier.value = (rc.max_tier as string | undefined) ?? undefined;
  routingVisionModelId.value =
    (rc.vision_model_id as number | undefined) ?? undefined;
  routingLongContextModelId.value =
    (rc.long_context_model_id as number | undefined) ?? undefined;
  routingLongContextThreshold.value =
    (rc.long_context_threshold as number) ?? 32_000;
}

async function saveRouting() {
  await saveFields({
    routing_config: {
      enable_routing: routingEnabled.value,
      max_tier: routingMaxTier.value || null,
      vision_model_id: routingVisionModelId.value ?? null,
      long_context_model_id: routingLongContextModelId.value ?? null,
      long_context_threshold: routingLongContextThreshold.value,
    },
  });
}

// ==================== Tab Change: Init ====================
function onTabChange(key: number | string) {
  activeTab.value = String(key);
  if (!agent.value) return;
  switch (key) {
    case 'chatConfig': {
      initChatConfig();
      break;
    }
    case 'modelParams': {
      initModelParams();
      break;
    }
    case 'quota': {
      initQuota();
      break;
    }
    case 'routing': {
      initRouting();
      loadRoutingModelOptions();
      break;
    }
    case 'skills': {
      loadBindings();
      break;
    }
    case 'knowledgeBases': {
      loadKBBindings();
      loadKBOptions();
      break;
    }
    case 'rag': {
      initRagConfig();
      break;
    }
  }
}

usePageAIRegistration({
  pageKey: 'tenant.ai.agents.detail',
  title: () => agent.value?.name ?? $t('tenant.ai.agent.detail.title'),
  resource: '/tenant/ai/agents',
  entityName: () => agent.value?.name ?? $t('tenant.ai.agent.detail.title'),
  entityDescription: () => $t('tenant.ai.agent.pageDesc'),
  data: () => ({
    agent_id: agentId.value,
    agent_name: agent.value?.name ?? '',
    status: agent.value?.status ?? '',
  }),
});

useDetailPageAi({
  pageKey: 'tenant.ai.agents.detail',
  refreshFn: () => loadAgent(),
  backRoute: '/tenant/ai/agents',
  extra: [
    {
      name: 'save_model_params',
      label: $t('shared.pageOperation.saveModelParams'),
      description: 'Save the current model parameters (temperature, max_tokens, top_p) / 保存当前模型参数',
      readonly: false,
      handler: async () => {
        await saveModelParams();
        return { success: true, message: 'Model params saved / 模型参数已保存' };
      },
    },
  ],
});
</script>

<template>
  <Page auto-content-height>
    <Spin :spinning="loading">
      <div v-if="!loading && !agent" class="py-20">
        <Empty :description="$t('common.noData')" />
      </div>

      <div v-if="agent" class="flex flex-col gap-4">
        <!-- ==================== Hero Header ==================== -->
        <div
          class="relative overflow-hidden rounded-xl border bg-card shadow-sm"
        >
          <div
            class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent"
          ></div>
          <div class="relative p-6">
            <!-- Top row: back + right badges -->
            <div class="mb-5 flex items-center justify-between">
              <button
                class="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                @click="goBack"
              >
                <IconifyIcon icon="lucide:chevron-left" class="size-4" />
                {{ $t('common.back') }}
              </button>
              <div class="flex items-center gap-2">
                <Tag v-if="agent.published_version" color="blue" class="!mr-0">
                  v{{ agent.published_version }}
                </Tag>
                <Tag :color="getStatusColor(agent.status)" class="!mr-0">
                  {{ getStatusText(agent.status) }}
                </Tag>
                <Button size="small" @click="openVersionHistory">
                  <IconifyIcon icon="lucide:history" class="mr-1 size-3.5" />
                  {{ $t('tenant.ai.agent.versionHistory') }}
                </Button>
                <Button
                  size="small"
                  @click="openAccessConfig"
                >
                  <IconifyIcon icon="lucide:shield" class="mr-1 size-3.5" />
                  {{ $t('tenant.ai.agent.accessConfig') }}
                </Button>
              </div>
            </div>

            <!-- Identity block -->
            <div class="flex items-start gap-5">
              <!-- Avatar with upload overlay -->
              <div class="group relative shrink-0">
                <Upload
                  v-if="isTenantOwned"
                  :show-upload-list="false"
                  :before-upload="beforeAvatarUpload"
                  :aria-label="$t('tenant.ai.agent.detail.uploadAvatar')"
                  accept="image/*"
                >
                  <div
                    class="relative flex size-16 cursor-pointer items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card"
                    :class="
                      agent.is_system
                        ? 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400'
                        : 'bg-primary/10 text-primary ring-primary/20'
                    "
                    :aria-label="$t('tenant.ai.agent.detail.uploadAvatar')"
                    :title="$t('tenant.ai.agent.detail.uploadAvatar')"
                  >
                    <img
                      v-if="avatarDisplayUrl"
                      :src="avatarDisplayUrl"
                      :alt="agent.name"
                      class="size-full object-cover"
                    />
                    <span v-else>{{ avatarInitial }}</span>
                    <!-- Upload overlay -->
                    <div
                      class="absolute inset-0 flex items-center justify-center rounded-2xl bg-black/40 opacity-0 transition-all group-hover:opacity-100"
                    >
                      <Spin v-if="avatarUploading" size="small" />
                      <IconifyIcon
                        v-else
                        icon="lucide:camera"
                        class="size-5 text-white"
                      />
                    </div>
                  </div>
                </Upload>
                <!-- Read-only avatar (system or non-owned agents) -->
                <div
                  v-else
                  class="flex size-16 items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card"
                  :class="
                    agent.is_system
                      ? 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400'
                      : 'bg-primary/10 text-primary ring-primary/20'
                  "
                >
                  <img
                    v-if="avatarDisplayUrl"
                    :src="avatarDisplayUrl"
                    :alt="agent.name"
                    class="size-full object-cover"
                  />
                  <span v-else>{{ avatarInitial }}</span>
                </div>
                <!-- Remove avatar button (tenant-owned only) -->
                <button
                  v-if="isTenantOwned && avatarDisplayUrl && !avatarUploading"
                  class="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-destructive text-white opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
                  type="button"
                  :aria-label="$t('tenant.ai.agent.detail.removeAvatar')"
                  :title="$t('tenant.ai.agent.detail.removeAvatar')"
                  @click.stop="removeAvatar"
                >
                  <IconifyIcon icon="lucide:x" class="size-3" />
                </button>
              </div>

              <div class="min-w-0 flex-1">
                <h1 class="mb-1 text-xl font-bold text-foreground">
                  {{ agent.name }}
                </h1>
                <p class="mb-4 text-sm text-muted-foreground">
                  {{ agent.description || $t('tenant.ai.agent.noDescription') }}
                </p>

                <!-- Meta chips row -->
                <div class="flex flex-wrap items-center gap-2">
                  <div
                    class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
                  >
                    <IconifyIcon
                      :icon="getExecutionModeIcon(agent.execution_mode)"
                      class="size-3.5 text-primary/70"
                    />
                    {{ getExecutionModeText(agent.execution_mode) }}
                  </div>
                  <Tag
                    :color="getScopeColor(agent.scope)"
                    class="!mr-0 !text-xs"
                  >
                    <div class="flex items-center gap-1">
                      <IconifyIcon :icon="getScopeIcon(agent.scope)" class="size-3" />
                      {{ getScopeText(agent.scope) }}
                    </div>
                  </Tag>
                  <!-- Readonly badge for non-owned agents -->
                  <div
                    v-if="!isTenantOwned"
                    class="flex items-center gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-medium text-warning"
                  >
                    <IconifyIcon icon="lucide:lock" class="size-3.5" />
                    {{ $t('tenant.ai.agent.readonlyHint') }}
                  </div>
                  <!-- Routing status chip (clickable, only for tenant-owned) -->
                  <button
                    v-if="isTenantOwned"
                    class="flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-medium transition-all duration-200 hover:opacity-80"
                    :class="
                      isRoutingEnabled
                        ? 'border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
                        : 'border-border/50 bg-background text-muted-foreground'
                    "
                    @click="jumpToRoutingTab"
                  >
                    <IconifyIcon icon="lucide:git-branch" class="size-3.5" />
                    <span v-if="isRoutingEnabled">{{
                      $t('tenant.ai.agent.routing.statusEnabled')
                    }}</span>
                    <span v-else>{{
                      $t('tenant.ai.agent.routing.statusDisabled')
                    }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ==================== Tabs ==================== -->
        <div class="rounded-xl border bg-card">
          <Tabs :active-key="activeTab" class="px-2 pt-1" @change="onTabChange">
            <!-- ========== 概览 ========== -->
            <TabPane key="overview">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon
                    icon="lucide:layout-dashboard"
                    class="size-3.5"
                  />
                  {{ $t('tenant.ai.agent.detail.overview') }}
                </span>
              </template>
              <div class="flex flex-col gap-5 p-5 pt-3">
                <!-- Basic Info Cards -->
                <div class="grid grid-cols-2 gap-3 md:grid-cols-3">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:activity"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.status')
                      }}</span>
                    </div>
                    <Tag
                      :color="getStatusColor(agent.status)"
                      class="!mr-0 !text-xs"
                    >
                      {{ getStatusText(agent.status) }}
                    </Tag>
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:workflow"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.executionMode')
                      }}</span>
                    </div>
                    <span class="text-sm font-medium">{{
                      getExecutionModeText(agent.execution_mode)
                    }}</span>
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:brain"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.modelName')
                      }}</span>
                    </div>
                    <span class="text-sm font-medium">{{
                      agent.model_code || '-'
                    }}</span>
                  </div>
                </div>

                <!-- Session Memory -->
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="flex items-start justify-between gap-4">
                    <div>
                      <div class="mb-1 flex items-center gap-2">
                        <div
                          class="flex size-7 items-center justify-center rounded-lg bg-indigo-500/10"
                        >
                          <IconifyIcon
                            icon="lucide:brain-circuit"
                            class="size-4 text-indigo-500"
                          />
                        </div>
                        <span class="text-sm font-semibold">{{
                          $t('tenant.ai.agent.memory.title')
                        }}</span>
                      </div>
                      <p class="text-xs text-muted-foreground">
                        {{ $t('tenant.ai.agent.memory.desc') }}
                      </p>
                      <p
                        v-if="!isTenantOwned"
                        class="mt-1 text-xs text-muted-foreground"
                      >
                        {{ $t('tenant.ai.agent.memory.readonlyHint') }}
                      </p>
                    </div>
                    <Switch
                      :checked="tenantMemoryDisabled"
                      :loading="memorySaving"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.memory.tenantSwitch')"
                      @change="
                        (val) => updateTenantMemoryDisabled(Boolean(val))
                      "
                    />
                  </div>
                  <Spin :spinning="memoryLoading" class="mt-3 block">
                    <div
                      v-if="memoryConfig"
                      class="grid grid-cols-1 gap-2 text-xs md:grid-cols-4"
                    >
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('tenant.ai.agent.memory.platformDefault') }}
                        </div>
                        <div class="mt-1 font-medium">
                          {{
                            memoryConfig.platform_default_memory_enabled
                              ? $t('tenant.ai.agent.memory.enabled')
                              : $t('tenant.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('tenant.ai.agent.memory.adminSwitch') }}
                        </div>
                        <div class="mt-1 font-medium">
                          {{
                            memoryConfig.admin_agent_memory_enabled
                              ? $t('tenant.ai.agent.memory.enabled')
                              : $t('tenant.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('tenant.ai.agent.memory.tenantSwitch') }}
                        </div>
                        <div class="mt-1 font-medium">
                          {{
                            memoryConfig.tenant_agent_memory_disabled
                              ? $t('tenant.ai.agent.memory.disabled')
                              : $t('tenant.ai.agent.memory.enabled')
                          }}
                        </div>
                      </div>
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('tenant.ai.agent.memory.effective') }}
                        </div>
                        <div
                          class="mt-1 font-semibold"
                          :class="
                            memoryConfig.effective_memory_enabled
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-amber-600 dark:text-amber-400'
                          "
                        >
                          {{
                            memoryConfig.effective_memory_enabled
                              ? $t('tenant.ai.agent.memory.enabled')
                              : $t('tenant.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                    </div>
                  </Spin>
                  <div
                    v-if="isTenantOwned && tenantMemoryDisabled"
                    class="mt-3"
                  >
                    <Button
                      size="small"
                      :loading="memorySaving"
                      @click="updateTenantMemoryDisabled(false)"
                    >
                      {{ $t('tenant.ai.agent.memory.restoreDefault') }}
                    </Button>
                  </div>
                </div>

                <!-- System Prompt -->
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="mb-3 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <div
                        class="flex size-7 items-center justify-center rounded-lg bg-primary/10"
                      >
                        <IconifyIcon
                          icon="lucide:message-square-code"
                          class="size-4 text-primary"
                        />
                      </div>
                      <span class="text-sm font-semibold">{{
                        $t('tenant.ai.agent.systemPrompt')
                      }}</span>
                    </div>
                    <Button
                      v-if="!editingPrompt && isTenantOwned"
                      size="small"
                      type="link"
                      @click="startEditPrompt"
                    >
                      <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
                      {{ $t('common.edit') }}
                    </Button>
                    <div v-else-if="editingPrompt" class="flex gap-2">
                      <Button size="small" @click="cancelEditPrompt">
                        {{ $t('common.cancel') }}
                      </Button>
                      <Button
                        size="small"
                        type="primary"
                        :loading="saving"
                        @click="savePrompt"
                      >
                        {{ $t('common.save') }}
                      </Button>
                    </div>
                  </div>
                  <div
                    v-if="!editingPrompt"
                    class="min-h-[60px] whitespace-pre-wrap text-sm leading-relaxed text-foreground"
                  >
                    {{ agent.system_prompt || '-' }}
                  </div>
                  <Textarea
                    v-else
                    v-model:value="promptDraft"
                    :rows="8"
                    class="w-full"
                  />
                </div>
              </div>
            </TabPane>

            <!-- ========== 模型参数 ========== -->
            <TabPane key="modelParams">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:sliders" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.modelParams') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <div class="grid max-w-2xl grid-cols-1 gap-4 md:grid-cols-3">
                  <div class="rounded-xl border bg-accent/30 p-5">
                    <div class="mb-3 flex items-center gap-2">
                      <div
                        class="flex size-7 items-center justify-center rounded-lg bg-orange-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:thermometer"
                          class="size-4 text-orange-500"
                        />
                      </div>
                      <label class="text-sm font-medium">{{
                        $t('tenant.ai.agent.temperature')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('tenant.ai.agent.help.temperature') }}
                    </p>
                    <InputNumber
                      v-model:value="modelTemp"
                      :min="0"
                      :max="2"
                      :step="0.1"
                      :disabled="!isTenantOwned"
                      :placeholder="$t('tenant.ai.agent.placeholder.inputTemperature')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-5">
                    <div class="mb-3 flex items-center gap-2">
                      <div
                        class="flex size-7 items-center justify-center rounded-lg bg-blue-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:hash"
                          class="size-4 text-blue-500"
                        />
                      </div>
                      <label class="text-sm font-medium">{{
                        $t('tenant.ai.agent.maxTokens')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('tenant.ai.agent.help.maxTokens') }}
                    </p>
                    <InputNumber
                      v-model:value="modelMaxTokens"
                      :min="1"
                      :max="128000"
                      :disabled="!isTenantOwned"
                      :placeholder="$t('tenant.ai.agent.placeholder.inputMaxTokens')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-5">
                    <div class="mb-3 flex items-center gap-2">
                      <div
                        class="flex size-7 items-center justify-center rounded-lg bg-purple-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:percent"
                          class="size-4 text-purple-500"
                        />
                      </div>
                      <label class="text-sm font-medium">{{
                        $t('tenant.ai.agent.topP')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('tenant.ai.agent.help.topP') }}
                    </p>
                    <InputNumber
                      v-model:value="modelTopP"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      :disabled="!isTenantOwned"
                      :placeholder="$t('tenant.ai.agent.placeholder.inputTopP')"
                      class="w-full"
                    />
                  </div>
                </div>
                <div v-if="isTenantOwned" class="mt-5">
                  <Button
                    type="primary"
                    :loading="saving"
                    @click="saveModelParams"
                  >
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </TabPane>

            <!-- ========== 对话配置 ========== -->
            <TabPane key="chatConfig">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:message-circle" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.chatConfig') }}
                </span>
              </template>
              <div class="flex flex-col gap-4 p-5 pt-3">
                <!-- System Prompt (editable inline) -->
                <div class="rounded-xl border border-primary/20 bg-primary/5 p-4">
                  <div class="mb-2 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:message-square-code" class="size-4 text-primary" />
                      <label class="text-sm font-semibold text-primary">{{ $t('tenant.ai.agent.systemPrompt') }}</label>
                    </div>
                    <span
                      v-if="!isTenantOwned"
                      class="rounded-full bg-primary/10 px-2 py-px text-[10px] text-primary"
                    >{{ $t('tenant.ai.agent.readonlyHint') }}</span>
                  </div>
                  <!-- Variable quick-insert chips -->
                  <div v-if="chatInputVars.length > 0" class="mb-2 flex flex-wrap gap-1.5">
                    <span class="text-xs text-muted-foreground">{{ $t('tenant.ai.agent.detail.chatConfigPromptHint') }}:</span>
                    <button
                      v-for="v in chatInputVars"
                      :key="v.name"
                      :disabled="!isTenantOwned"
                      class="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                      @click="insertVarAtCursor(v.name)"
                    >
                      <span v-text="formatVarChip(v.name)" />
                    </button>
                  </div>
                  <Textarea
                    :ref="(el) => { chatSystemPromptRef = el as HTMLTextAreaElement | null }"
                    v-model:value="chatSystemPrompt"
                    :rows="6"
                    :disabled="!isTenantOwned"
                    :placeholder="$t('tenant.ai.agent.placeholder.inputSystemPrompt')"
                    class="w-full text-xs"
                  />
                </div>
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="mb-3 flex items-center gap-2">
                    <div
                      class="flex size-7 items-center justify-center rounded-lg bg-green-500/10"
                    >
                      <IconifyIcon
                        icon="lucide:smile"
                        class="size-4 text-green-500"
                      />
                    </div>
                    <label class="text-sm font-medium">{{
                      $t('tenant.ai.agent.welcomeMessage')
                    }}</label>
                  </div>
                  <Textarea
                    v-model:value="chatWelcome"
                    :rows="3"
                    :disabled="!isTenantOwned"
                    :placeholder="$t('tenant.ai.agent.placeholder.inputWelcomeMessage')"
                    class="w-full"
                  />
                </div>
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="mb-3 flex items-center gap-2">
                    <div
                      class="flex size-7 items-center justify-center rounded-lg bg-cyan-500/10"
                    >
                      <IconifyIcon
                        icon="lucide:help-circle"
                        class="size-4 text-cyan-500"
                      />
                    </div>
                    <label class="text-sm font-medium">{{
                      $t('tenant.ai.agent.suggestedQuestions')
                    }}</label>
                  </div>
                  <Textarea
                    v-model:value="chatSuggestions"
                    :rows="4"
                    :disabled="!isTenantOwned"
                    :placeholder="$t('tenant.ai.agent.placeholder.inputSuggestedQuestions')"
                    class="w-full font-mono text-xs"
                  />
                  <p class="mt-1 text-xs text-muted-foreground">JSON</p>
                </div>
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="mb-3 flex items-center gap-2">
                    <div
                      class="flex size-7 items-center justify-center rounded-lg bg-violet-500/10"
                    >
                      <IconifyIcon
                        icon="lucide:variable"
                        class="size-4 text-violet-500"
                      />
                    </div>
                    <label class="text-sm font-medium">{{
                      $t('tenant.ai.agent.inputVariables.title')
                    }}</label>
                  </div>
                  <InputVariablesEditor
                    v-model="chatInputVars"
                    :disabled="!isTenantOwned"
                  />
                </div>
                <div class="rounded-xl border bg-accent/30 p-5">
                  <div class="mb-3 flex items-center gap-2">
                    <div
                      class="flex size-7 items-center justify-center rounded-lg bg-amber-500/10"
                    >
                      <IconifyIcon
                        icon="lucide:history"
                        class="size-4 text-amber-500"
                      />
                    </div>
                    <label class="text-sm font-medium">{{
                      $t('tenant.ai.agent.contextConfig.title')
                    }}</label>
                  </div>
                  <div class="grid grid-cols-2 gap-4">
                    <div>
                      <label class="mb-1 block text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.contextConfig.maxHistoryMessages')
                      }}</label>
                      <InputNumber
                        v-model:value="chatContextMessages"
                        :min="0"
                        :disabled="!isTenantOwned"
                        class="w-full"
                      />
                    </div>
                    <div>
                      <label class="mb-1 block text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.contextConfig.maxHistoryTokens')
                      }}</label>
                      <InputNumber
                        v-model:value="chatContextTokens"
                        :min="0"
                        :disabled="!isTenantOwned"
                        class="w-full"
                      />
                    </div>
                  </div>
                </div>
                <div v-if="isTenantOwned">
                  <Button
                    type="primary"
                    :loading="saving"
                    @click="saveChatConfig"
                  >
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </TabPane>

            <!-- ========== 技能绑定 ========== -->
            <TabPane key="skills">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.skillBindings') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <Spin :spinning="bindingsLoading">
                  <div class="flex flex-col gap-4">
                    <!-- Auto-bound -->
                    <div v-if="bindings.some((x) => x.is_auto_bound)">
                      <div
                        class="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground"
                      >
                        <IconifyIcon
                          icon="lucide:zap"
                          class="size-3.5 text-primary/60"
                        />
                        {{ $t('common.bindMode.auto') }}
                      </div>
                      <div class="flex flex-col gap-2">
                        <div
                          v-for="b in bindings.filter((x) => x.is_auto_bound)"
                          :key="`auto-${b.package_id}`"
                          class="overflow-hidden rounded-xl border border-primary/20 bg-primary/5"
                        >
                          <div
                            class="flex cursor-pointer items-center justify-between px-4 py-3"
                            @click="togglePackageSkills(b.package_id)"
                          >
                            <div class="flex items-center gap-3">
                              <IconifyIcon
                                icon="lucide:lock"
                                class="size-4 shrink-0 text-primary/50"
                              />
                              <div class="min-w-0">
                                <div class="flex items-center gap-2">
                                  <span class="text-sm font-medium">{{ b.package_name || `#${b.package_id}` }}</span>
                                  <Tag v-if="b.package_target_audience" color="processing" class="!text-[10px]">
                                    {{ b.package_target_audience }}
                                  </Tag>
                                </div>
                                <p v-if="b.package_description" class="mt-0.5 truncate text-xs text-muted-foreground">{{ b.package_description }}</p>
                              </div>
                            </div>
                            <div class="flex shrink-0 items-center gap-2">
                              <Tag color="blue" class="!text-[10px]">
                                <IconifyIcon icon="lucide:zap" class="mr-0.5 inline size-3" />
                                {{ $t('common.bindMode.auto') }}
                              </Tag>
                              <IconifyIcon
                                :icon="expandedPackages.has(b.package_id) ? 'lucide:chevron-up' : 'lucide:chevron-down'"
                                class="size-4 text-muted-foreground"
                              />
                            </div>
                          </div>
                          <div v-if="expandedPackages.has(b.package_id)" class="border-t border-primary/10 bg-background/50 px-4 py-2">
                            <Spin v-if="packageSkillsLoading.has(b.package_id)" size="small" class="flex justify-center py-3" />
                            <div v-else-if="packageSkills.get(b.package_id)?.length === 0" class="py-3 text-center text-xs text-muted-foreground">
                              {{ $t('tenant.ai.agent.detail.noSkills') }}
                            </div>
                            <div v-else class="flex flex-col gap-1">
                              <div v-for="skill in packageSkills.get(b.package_id)" :key="skill.id" class="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent/40">
                                <span class="min-w-0 flex-1 truncate text-xs font-medium">{{ skill.name }}</span>
                                <span :class="skill.is_active ? 'bg-green-500' : 'bg-muted-foreground/30'" class="inline-block size-1.5 shrink-0 rounded-full"></span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Manual-bound -->
                    <div v-if="bindings.some((x) => !x.is_auto_bound)">
                      <div
                        class="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground"
                      >
                        <IconifyIcon icon="lucide:link" class="size-3.5" />
                        {{ $t('common.bindMode.manual') }}
                      </div>
                      <div class="flex flex-col gap-2">
                        <div
                          v-for="b in bindings.filter((x) => !x.is_auto_bound)"
                          :key="`manual-${b.package_id}`"
                          class="overflow-hidden rounded-xl border bg-background"
                        >
                          <div class="flex items-center justify-between px-4 py-3">
                            <div
                              class="flex flex-1 cursor-pointer items-center gap-3"
                              @click="togglePackageSkills(b.package_id)"
                            >
                              <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
                                {{ (b.package_name || '?').charAt(0) }}
                              </div>
                              <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-2">
                                  <span class="text-sm font-medium">{{ b.package_name || `#${b.package_id}` }}</span>
                                  <Tag v-if="b.package_target_audience" color="processing" class="!text-[10px]">
                                    {{ b.package_target_audience }}
                                  </Tag>
                                </div>
                                <p v-if="b.package_description" class="mt-0.5 truncate text-xs text-muted-foreground">{{ b.package_description }}</p>
                              </div>
                              <IconifyIcon
                                :icon="expandedPackages.has(b.package_id) ? 'lucide:chevron-up' : 'lucide:chevron-down'"
                                class="size-4 shrink-0 text-muted-foreground"
                              />
                            </div>
                            <div class="flex items-center gap-2">
                            <Tag
                              :color="
                                b.consent_mode === 'auto'
                                  ? 'green'
                                  : b.consent_mode === 'ask'
                                    ? 'orange'
                                    : 'red'
                              "
                            >
                              {{
                                $t(
                                  `tenant.ai.agent.consentModeOptions.${b.consent_mode}`,
                                )
                              }}
                            </Tag>
                          </div>
                          </div>
                          <!-- Skills expansion -->
                          <div v-if="expandedPackages.has(b.package_id)" class="border-t bg-accent/20 px-4 py-2">
                            <Spin v-if="packageSkillsLoading.has(b.package_id)" size="small" class="flex justify-center py-3" />
                            <div v-else-if="packageSkills.get(b.package_id)?.length === 0" class="py-3 text-center text-xs text-muted-foreground">
                              {{ $t('tenant.ai.agent.detail.noSkills') }}
                            </div>
                            <div v-else class="flex flex-col gap-1">
                              <div v-for="skill in packageSkills.get(b.package_id)" :key="skill.id" class="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent/40">
                                <span class="min-w-0 flex-1 truncate text-xs font-medium">{{ skill.name }}</span>
                                <span :class="skill.is_active ? 'bg-green-500' : 'bg-muted-foreground/30'" class="inline-block size-1.5 shrink-0 rounded-full"></span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <Empty v-if="bindings.length === 0 && !bindingsLoading" />
                  </div>
                </Spin>
              </div>
            </TabPane>

            <TabPane key="rag">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:search" class="size-3.5" />
                  {{ $t('tenant.ai.agent.knowledgeBase.title') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <div class="mb-4 flex flex-wrap items-center gap-2">
                  <p class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.agent.detail.ragHint') }}
                  </p>
                  <span
                    v-if="!isTenantOwned"
                    class="rounded-full bg-warning/15 px-2 py-px text-[10px] font-medium text-warning"
                  >{{ $t('tenant.ai.agent.readonlyHint') }}</span>
                </div>
                <div class="grid max-w-3xl grid-cols-1 gap-3 md:grid-cols-2">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="tenant-agent-rag-search-mode"
                      class="mb-2 block text-xs text-muted-foreground"
                    >{{
                      $t('tenant.ai.agent.knowledgeBase.searchMode')
                    }}</label>
                    <ASelect
                      id="tenant-agent-rag-search-mode"
                      v-model:value="ragSearchMode"
                      :options="ragSearchModeOptions"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.searchMode')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="tenant-agent-rag-rewrite-strategy"
                      class="mb-2 block text-xs text-muted-foreground"
                    >{{
                      $t('tenant.ai.agent.knowledgeBase.rewriteStrategy')
                    }}</label>
                    <ASelect
                      id="tenant-agent-rag-rewrite-strategy"
                      v-model:value="ragRewriteStrategy"
                      :options="ragRewriteOptions"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.rewriteStrategy')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="tenant-agent-rag-top-k"
                      class="mb-2 block text-xs text-muted-foreground"
                    >{{
                      $t('tenant.ai.agent.knowledgeBase.topK')
                    }}</label>
                    <InputNumber
                      id="tenant-agent-rag-top-k"
                      v-model:value="ragTopK"
                      :min="1"
                      :max="20"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.topK')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="tenant-agent-rag-score-threshold"
                      class="mb-2 block text-xs text-muted-foreground"
                    >{{
                      $t('tenant.ai.agent.knowledgeBase.scoreThreshold')
                    }}</label>
                    <InputNumber
                      id="tenant-agent-rag-score-threshold"
                      v-model:value="ragScoreThreshold"
                      :min="0"
                      :max="1"
                      :step="0.05"
                      :precision="2"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.scoreThreshold')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="tenant-agent-rag-context-token-ratio"
                      class="mb-2 block text-xs text-muted-foreground"
                    >{{
                      $t('tenant.ai.agent.knowledgeBase.contextTokenRatio')
                    }}</label>
                    <InputNumber
                      id="tenant-agent-rag-context-token-ratio"
                      v-model:value="ragContextTokenRatio"
                      :min="0.1"
                      :max="0.9"
                      :step="0.05"
                      :precision="2"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.contextTokenRatio')"
                      class="w-full"
                    />
                  </div>
                  <div
                    class="flex flex-col justify-between rounded-xl border bg-accent/30 p-4"
                  >
                    <div>
                      <label class="mb-2 block text-xs text-muted-foreground">{{
                        $t('tenant.ai.agent.knowledgeBase.rerankerEnabled')
                      }}</label>
                      <p class="mb-3 text-xs text-muted-foreground">
                        {{
                          $t(
                            'tenant.ai.agent.knowledgeBase.rerankerEnabledHelp',
                          )
                        }}
                      </p>
                    </div>
                    <Switch
                      v-model:checked="ragRerankerEnabled"
                      :disabled="!isTenantOwned"
                      :aria-label="$t('tenant.ai.agent.knowledgeBase.rerankerEnabled')"
                    />
                  </div>
                </div>
                <div class="mt-5">
                  <Button
                    type="primary"
                    :loading="saving"
                    :disabled="!isTenantOwned"
                    @click="saveRagConfig"
                  >
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </TabPane>

            <!-- ========== 知识库绑定 ========== -->
            <TabPane key="knowledgeBases">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:library" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.knowledgeBases') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <Spin :spinning="kbBindingsLoading">
                  <div class="flex flex-col gap-4">
                    <p
                      v-if="isPlatformAssignedAgent"
                      class="text-xs text-muted-foreground"
                    >
                      {{ $t('tenant.ai.agent.detail.kbTenantOverlayHint') }}
                    </p>
                    <p class="text-xs text-muted-foreground">
                      {{ $t('tenant.ai.agent.detail.kbWeightFusionHint') }}
                    </p>
                    <!-- Add binding row -->
                    <div
                      v-if="canManageKnowledgeBases"
                      class="flex items-center gap-3 rounded-xl border bg-accent/30 p-4"
                    >
                      <ASelect
                        v-model:value="selectedNewKBs"
                        :options="unboundKBs"
                        :placeholder="
                          $t('tenant.ai.agent.detail.selectKnowledgeBase')
                        "
                        mode="multiple"
                        show-search
                        option-filter-prop="label"
                        allow-clear
                        class="flex-1"
                      />
                      <Button
                        type="primary"
                        :disabled="selectedNewKBs.length === 0"
                        @click="bindKB"
                      >
                        <IconifyIcon icon="lucide:plus" class="mr-1" />
                        {{ $t('tenant.ai.agent.detail.bindKnowledgeBase') }}
                      </Button>
                    </div>

                    <!-- Binding list -->
                    <div v-if="kbBindings.length > 0" class="flex flex-col gap-2">
                      <div
                        v-for="b in kbBindings"
                        :key="b.id"
                        class="flex items-center justify-between rounded-xl border bg-background px-4 py-3 transition-colors"
                      >
                        <div class="flex items-center gap-3">
                          <div
                            class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-blue-500/10"
                          >
                            <IconifyIcon
                              icon="lucide:book-open"
                              class="size-4 text-blue-500"
                            />
                          </div>
                          <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                              <span class="text-sm font-medium">{{
                                b.kb_name || `#${b.knowledge_base_id}`
                              }}</span>
                              <Tag
                                v-if="isKbBindingReadonly(b)"
                                color="orange"
                                class="!mr-0 !text-[10px]"
                              >
                                {{ $t('tenant.ai.agent.detail.kbPlatformBadge') }}
                              </Tag>
                              <Tag
                                v-if="b.kb_document_count != null"
                                class="!mr-0 !text-[10px]"
                              >
                                {{ b.kb_document_count }}
                                {{ $t('tenant.ai.agent.detail.kbDocCount') }}
                              </Tag>
                            </div>
                            <p
                              v-if="b.kb_description"
                              class="mt-0.5 truncate text-xs text-muted-foreground"
                            >
                              {{ b.kb_description }}
                            </p>
                            <div class="mt-1 flex flex-wrap gap-1.5">
                              <Tag
                                v-if="b.kb_embedding_model_name"
                                class="!mr-0 !text-[10px]"
                              >
                                {{ $t('tenant.ai.agent.detail.kbEmbeddingModel') }}:
                                {{ b.kb_embedding_model_name }}
                              </Tag>
                              <Tag
                                v-if="b.kb_embedding_dimensions != null"
                                class="!mr-0 !text-[10px]"
                              >
                                {{
                                  $t(
                                    'tenant.ai.agent.detail.kbEmbeddingDimensions',
                                  )
                                }}:
                                {{ b.kb_embedding_dimensions }}
                              </Tag>
                              <Tag
                                v-if="b.kb_chunk_strategy"
                                class="!mr-0 !text-[10px]"
                              >
                                {{ $t('tenant.ai.agent.detail.kbChunkStrategy') }}:
                                {{
                                  getKbChunkStrategyText(b.kb_chunk_strategy)
                                }}
                              </Tag>
                            </div>
                          </div>
                        </div>
                        <div class="flex items-center gap-3">
                          <!-- Weight -->
                          <div class="flex items-center gap-1.5">
                            <span class="text-xs text-muted-foreground">{{
                              $t('tenant.ai.agent.detail.kbWeight')
                            }}</span>
                            <InputNumber
                              :value="b.weight"
                              :min="0.1"
                              :max="2"
                              :step="0.1"
                              size="small"
                              :disabled="
                                !canManageKnowledgeBases ||
                                isKbBindingReadonly(b)
                              "
                              class="!w-20"
                              @change="
                                (val) =>
                                  val != null &&
                                  updateKBWeight(b.id, Number(val))
                              "
                            />
                          </div>
                          <!-- Enabled switch -->
                          <Switch
                            :checked="b.enabled"
                            size="small"
                            :disabled="
                              !canManageKnowledgeBases ||
                              isKbBindingReadonly(b)
                            "
                            :aria-label="`${$t('tenant.ai.agent.detail.kbEnabled')}: ${b.kb_name ?? b.knowledge_base_id}`"
                            @change="toggleKBEnabled(b)"
                          />
                          <!-- Platform KB: tenant opt-out from RAG -->
                          <div
                            v-if="isKbBindingReadonly(b) && canManageKnowledgeBases"
                            class="flex max-w-[11rem] flex-col gap-0.5"
                          >
                            <span class="text-[10px] text-muted-foreground">{{
                              $t('tenant.ai.agent.detail.kbPlatformOptOut')
                            }}</span>
                            <Switch
                              :checked="Boolean(b.platform_suppressed)"
                              size="small"
                              :loading="
                                platformKbSuppressLoadingKbId ===
                                b.knowledge_base_id
                              "
                              :aria-label="`${$t('tenant.ai.agent.detail.kbPlatformOptOut')}: ${b.kb_name ?? b.knowledge_base_id}`"
                              @change="
                                (val) =>
                                  togglePlatformKbOptOut(b, Boolean(val))
                              "
                            />
                            <span class="text-[10px] leading-tight text-muted-foreground">{{
                              $t('tenant.ai.agent.detail.kbPlatformOptOutHint')
                            }}</span>
                          </div>
                          <!-- Unbind -->
                          <Popconfirm
                            v-if="
                              canManageKnowledgeBases &&
                              !isKbBindingReadonly(b)
                            "
                            :title="$t('common.confirmDelete')"
                            @confirm="unbindKB(b.knowledge_base_id)"
                          >
                            <Button size="small" danger type="text">
                              <IconifyIcon
                                icon="lucide:unlink"
                                class="size-3.5"
                              />
                            </Button>
                          </Popconfirm>
                        </div>
                      </div>
                    </div>

                    <Empty
                      v-if="kbBindings.length === 0 && !kbBindingsLoading"
                      :description="
                        $t('tenant.ai.agent.detail.noKnowledgeBases')
                      "
                    />
                  </div>
                </Spin>
              </div>
            </TabPane>

            <!-- ========== 配额管理 ========== -->
            <TabPane key="quota">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:gauge" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.quota') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <div class="mb-4 flex flex-wrap items-center gap-2">
                  <p class="text-xs text-muted-foreground">
                    {{ $t('tenant.ai.agent.detail.noQuotaLimit') }}
                  </p>
                  <span
                    v-if="!isTenantOwned"
                    class="rounded-full bg-warning/15 px-2 py-px text-[10px] font-medium text-warning"
                  >{{ $t('tenant.ai.agent.readonlyHint') }}</span>
                </div>
                <div class="grid max-w-2xl grid-cols-1 gap-3 md:grid-cols-2">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.conversationsPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaConversationsPerDay"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.tokensPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaTokensPerDay"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.tokensPerMonth')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaTokensPerMonth"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.maxTurnsPerConversation')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaMaxTurns"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.maxConcurrent')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaMaxConcurrent"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.userConversationsPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaUserConversationsPerDay"
                      :min="0"
                      :disabled="!isTenantOwned"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="mt-5">
                  <Button
                    type="primary"
                    :loading="saving"
                    :disabled="!isTenantOwned"
                    @click="saveQuota"
                  >
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </TabPane>

            <!-- ========== 智能路由 ========== -->
            <TabPane key="routing">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:git-branch" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.routing') }}
                  <span
                    v-if="isRoutingEnabled"
                    class="inline-block size-2 rounded-full bg-green-500"
                  ></span>
                </span>
              </template>
              <div class="p-5 pt-3">
                <!-- Master toggle card -->
                <div
                  class="mb-5 rounded-xl border-2 p-5 transition-all duration-300"
                  :class="
                    routingEnabled
                      ? 'border-green-500/30 bg-green-500/5'
                      : 'border-border bg-accent/20'
                  "
                >
                  <div class="flex items-start gap-4">
                    <div
                      class="flex size-12 shrink-0 items-center justify-center rounded-xl transition-all duration-300"
                      :class="
                        routingEnabled
                          ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                          : 'bg-muted text-muted-foreground'
                      "
                    >
                      <IconifyIcon icon="lucide:git-branch" class="size-6" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center justify-between gap-4">
                        <div>
                          <h3 class="text-base font-semibold text-foreground">
                            {{ $t('tenant.ai.agent.routing.enableRouting') }}
                          </h3>
                          <p class="mt-0.5 text-sm text-muted-foreground">
                            {{ $t('tenant.ai.agent.routing.description') }}
                          </p>
                        </div>
                        <Switch
                          v-model:checked="routingEnabled"
                          :disabled="!isTenantOwned"
                          class="shrink-0"
                          :aria-label="$t('tenant.ai.agent.routing.enableRouting')"
                        />
                      </div>
                      <div
                        v-if="routingEnabled"
                        class="mt-3 inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-600 dark:text-green-400"
                      >
                        <span
                          class="inline-block size-1.5 rounded-full bg-green-500"
                        ></span>
                        {{ $t('tenant.ai.agent.routing.statusEnabled') }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Feature cards (only when enabled) -->
                <div
                  v-if="routingEnabled"
                  class="grid grid-cols-1 gap-4 md:grid-cols-2"
                >
                  <div class="rounded-xl border bg-background p-5 shadow-sm">
                    <div class="mb-4 flex items-center gap-3">
                      <div
                        class="flex size-9 items-center justify-center rounded-xl bg-amber-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:layers"
                          class="size-5 text-amber-500"
                        />
                      </div>
                      <div>
                        <div class="text-sm font-semibold">
                          {{ $t('tenant.ai.agent.routing.maxTier') }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{ $t('tenant.ai.agent.routing.maxTierHelp') }}
                        </div>
                      </div>
                    </div>
                    <ASelect
                      v-model:value="routingMaxTier"
                      :options="tierOptions"
                      class="w-full"
                      :allow-clear="true"
                      :placeholder="$t('tenant.ai.agent.routing.noLimit')"
                      :disabled="!isTenantOwned"
                    />
                  </div>

                  <div class="rounded-xl border bg-background p-5 shadow-sm">
                    <div class="mb-4 flex items-center gap-3">
                      <div
                        class="flex size-9 items-center justify-center rounded-xl bg-violet-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:eye"
                          class="size-5 text-violet-500"
                        />
                      </div>
                      <div>
                        <div class="text-sm font-semibold">
                          {{ $t('tenant.ai.agent.routing.visionModel') }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{ $t('tenant.ai.agent.routing.visionModelHelp') }}
                        </div>
                      </div>
                    </div>
                    <ASelect
                      v-model:value="routingVisionModelId"
                      :options="visionModelOptions"
                      class="w-full"
                      :allow-clear="true"
                      :placeholder="$t('tenant.ai.agent.routing.autoSelect')"
                      show-search
                      option-filter-prop="label"
                      :disabled="!isTenantOwned"
                    />
                  </div>

                  <div class="rounded-xl border bg-background p-5 shadow-sm">
                    <div class="mb-4 flex items-center gap-3">
                      <div
                        class="flex size-9 items-center justify-center rounded-xl bg-blue-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:scroll-text"
                          class="size-5 text-blue-500"
                        />
                      </div>
                      <div>
                        <div class="text-sm font-semibold">
                          {{ $t('tenant.ai.agent.routing.longContextModel') }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{
                            $t('tenant.ai.agent.routing.longContextModelHelp')
                          }}
                        </div>
                      </div>
                    </div>
                    <ASelect
                      v-model:value="routingLongContextModelId"
                      :options="chatModelOptions"
                      class="w-full"
                      :allow-clear="true"
                      :placeholder="$t('tenant.ai.agent.routing.autoSelect')"
                      show-search
                      option-filter-prop="label"
                      :disabled="!isTenantOwned"
                    />
                  </div>

                  <div class="rounded-xl border bg-background p-5 shadow-sm">
                    <div class="mb-4 flex items-center gap-3">
                      <div
                        class="flex size-9 items-center justify-center rounded-xl bg-cyan-500/10"
                      >
                        <IconifyIcon
                          icon="lucide:gauge"
                          class="size-5 text-cyan-500"
                        />
                      </div>
                      <div>
                        <div class="text-sm font-semibold">
                          {{
                            $t('tenant.ai.agent.routing.longContextThreshold')
                          }}
                        </div>
                        <div class="text-xs text-muted-foreground">
                          {{
                            $t(
                              'tenant.ai.agent.routing.longContextThresholdHelp',
                            )
                          }}
                        </div>
                      </div>
                    </div>
                    <InputNumber
                      v-model:value="routingLongContextThreshold"
                      :min="1000"
                      :step="1000"
                      class="w-full"
                      :disabled="!isTenantOwned"
                    />
                  </div>
                </div>

                <div v-if="isTenantOwned" class="mt-5">
                  <Button type="primary" :loading="saving" @click="saveRouting">
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </TabPane>
          </Tabs>
        </div>
      </div>
    </Spin>
    <AccessConfigDrawerCmp />
    <VersionHistoryDrawerCmp @success="loadAgent" />
  </Page>
</template>
