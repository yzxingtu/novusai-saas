<script lang="ts" setup>
/**
 * 管理端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 * 显示分发模式/归属等元信息，系统智能体核心字段保护。
 */
import type {
  AIAgentInfo,
  AIAgentKBBindingInfo,
  AIAgentMemoryConfig,
  AIAgentSkillGrantInfo,
} from '#/api/admin/ai';
import type { AgentKnowledgeBaseBindingDraftItem } from '#/components/business/agent-kb-binding-picker';
import type { AgentSkillBindingDraftItem } from '#/components/business/agent-skill-binding-picker';
import type { InputVariable } from '#/types/ai-chat';

import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
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
  batchBindAIAgentKBsApi,
  batchBindAIAgentSkillsApi,
  getAIAgentDetailApi,
  getAIAgentKBsApi,
  getAIAgentMemoryConfigApi,
  getAIAgentSkillsApi,
  getAIModelListApi,
  unbindAIAgentKBApi,
  unbindAIAgentSkillApi,
  updateAIAgentApi,
  updateAIAgentKBBindingApi,
  updateAIAgentMemoryConfigApi,
  updateAIAgentSkillGrantApi,
} from '#/api/admin/ai';
import { smartUploadFile } from '#/api/admin/attachment';
import { getAdminSelectableKBApi } from '#/api/admin/knowledge-bases';
import {
  AgentKnowledgeBaseBindingPicker,
  bindingsToDrafts as kbBindingsToDrafts,
  draftsToBatchPayload as kbDraftsToBatchPayload,
} from '#/components/business/agent-kb-binding-picker';
import AgentRoutingTab from '#/components/business/agent-routing-tab/AgentRoutingTab.vue';
import {
  AgentSkillBindingPicker,
  draftsToBatchPayload,
  grantsToDrafts,
} from '#/components/business/agent-skill-binding-picker';
import InputVariablesEditor from '#/components/business/input-variables-editor/InputVariablesEditor.vue';
import {
  createOpenCurrentPageOperation,
  createSavePageOperation,
} from '#/composables';
import {
  applyAgentRoutingConfig,
  buildAgentRoutingModelOptions,
  buildAgentRoutingPayload,
  createAgentRoutingState,
  createEmptyAgentRoutingModelOptions,
} from '#/composables/use-agent-routing';
import { useDetailPageAi } from '#/composables/use-detail-page-ai';
import { usePageAIContext } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import {
  formatStarterQuestionsInput,
  parseStarterQuestionsInput,
} from '#/utils/ai-starter-questions';
import { showRequestError } from '#/utils/error-helpers';
import { toAvatarDisplayUrl } from '#/utils/image';
import {
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import {
  getExecutionModeText,
  getOwnerTypeColor,
  getOwnerTypeText,
  getStatusText,
} from './data';
import AccessConfigDrawer from './modules/AccessConfig.vue';
import PluginSourceBadge from './modules/PluginSourceBadge.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'AdminAgentDetail' });

// ==================== Route / 路由 ====================
const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

// ==================== State / 状态 ====================
const loading = ref(false);
const saving = ref(false);
const agent = ref<AIAgentInfo | null>(null);
const activeTab = ref('overview');
const memoryLoading = ref(false);
const memorySaving = ref(false);
const memoryConfig = ref<AIAgentMemoryConfig | null>(null);
const adminMemoryEnabled = ref(true);

// ==================== Load / 加载 ====================
async function loadMemoryConfig() {
  memoryLoading.value = true;
  try {
    memoryConfig.value = await getAIAgentMemoryConfigApi(agentId.value);
    adminMemoryEnabled.value = memoryConfig.value.admin_agent_memory_enabled;
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
  } finally {
    memoryLoading.value = false;
  }
}

async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAIAgentDetailApi(agentId.value);
    await loadMemoryConfig();
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
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
  router.push('/admin/ai/agents');
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

// ==================== Generic Save / 通用保存 ====================
async function saveFields(fields: Record<string, unknown>) {
  if (!agent.value) return;
  saving.value = true;
  try {
    agent.value = await updateAIAgentApi(agentId.value, fields);
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  } finally {
    saving.value = false;
  }
}

// ==================== Avatar Upload / 头像上传 ====================
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
    message.error($t('admin.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('admin.profile.messages.avatarSizeError'));
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
    agent.value = await updateAIAgentApi(agentId.value, {
      avatar: attachmentId,
    });
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'shared.common.uploadFailed');
  } finally {
    avatarUploading.value = false;
  }
}

async function removeAvatar() {
  if (!agent.value) return;
  avatarUploading.value = true;
  try {
    agent.value = await updateAIAgentApi(agentId.value, { avatar: null });
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  } finally {
    avatarUploading.value = false;
  }
}

async function updateAdminMemoryEnabled(checked: boolean) {
  const previous = adminMemoryEnabled.value;
  adminMemoryEnabled.value = checked;
  memorySaving.value = true;
  try {
    memoryConfig.value = await updateAIAgentMemoryConfigApi(agentId.value, {
      enabled: checked,
    });
    adminMemoryEnabled.value = memoryConfig.value.admin_agent_memory_enabled;
    message.success($t('admin.ai.agent.memory.saveSuccess'));
  } catch (error) {
    adminMemoryEnabled.value = previous;
    showRequestError(error, 'common.saveFailed');
  } finally {
    memorySaving.value = false;
  }
}

// ==================== Overview Tab / 概览页签 ====================
const editingPrompt = ref(false);
const promptDraft = ref('');

function startEditPrompt() {
  promptDraft.value = agent.value?.system_prompt || '';
  editingPrompt.value = true;
}

async function savePrompt() {
  await saveFields({ system_prompt: promptDraft.value });
  editingPrompt.value = false;
}

// ==================== Model Params Tab / 模型参数页签 ====================
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
    modelLimit !== null &&
    modelLimit !== undefined &&
    modelMaxTokens.value !== null &&
    modelMaxTokens.value !== undefined &&
    modelMaxTokens.value > modelLimit
  ) {
    message.warning(
      $t('admin.ai.agent.validation.maxTokensExceedsModelLimit', {
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

// ==================== Chat Config Tab / 对话配置页签 ====================
const chatWelcome = ref('');
const chatSuggestions = ref('');
const chatInputVars = ref<InputVariable[]>([]);
const chatSystemPrompt = ref('');
const chatContextMessages = ref(20);
const chatContextTokens = ref(0);
/** Long-term memory toggle (merged into context_config, not overwritten on save) / 长期记忆开关 */
const chatLongTermMemoryEnabled = ref(false);

/** Ref to system prompt textarea for cursor-based variable insertion / 系统提示词输入框引用，用于插入变量 */
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
    chatSystemPrompt.value.slice(0, Math.max(0, start)) +
    token +
    chatSystemPrompt.value.slice(Math.max(0, end));
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
  chatSuggestions.value = formatStarterQuestionsInput(sq as null | unknown[]);
  chatInputVars.value = Array.isArray(agent.value.input_variables)
    ? (agent.value.input_variables as unknown as InputVariable[])
    : [];
  const cc = (agent.value.context_config ?? {}) as Record<string, unknown>;
  chatContextMessages.value =
    typeof cc.max_history_messages === 'number' ? cc.max_history_messages : 20;
  chatContextTokens.value =
    typeof cc.max_history_tokens === 'number' ? cc.max_history_tokens : 0;
  chatLongTermMemoryEnabled.value = Boolean(cc.long_term_memory_enabled);
}

function buildMergedContextConfig(): Record<string, unknown> {
  const prev = (agent.value?.context_config ?? {}) as Record<string, unknown>;
  return {
    ...prev,
    max_history_messages: chatContextMessages.value,
    max_history_tokens: chatContextTokens.value,
    long_term_memory_enabled: chatLongTermMemoryEnabled.value,
  };
}

async function saveChatConfig() {
  const isSystem = agent.value?.is_system ?? true;
  await saveFields({
    ...(isSystem ? {} : { system_prompt: chatSystemPrompt.value || null }),
    welcome_message: chatWelcome.value || null,
    suggested_questions: parseStarterQuestionsInput(chatSuggestions.value),
    input_variables:
      chatInputVars.value.length > 0 ? chatInputVars.value : null,
    context_config: buildMergedContextConfig(),
  });
}

// ==================== Skill Bindings Tab / 技能绑定页签 ====================
const bindings = ref<AIAgentSkillGrantInfo[]>([]);
const bindingsLoading = ref(false);
const skillPickerOpen = ref(false);
const skillPickerDrafts = ref<AgentSkillBindingDraftItem[]>([]);
const bindingPackageCount = computed(() => {
  const keys = new Set(
    bindings.value.map(
      (binding) => binding.package_name || `skill:${binding.skill_id}`,
    ),
  );
  return keys.size;
});

async function loadBindings() {
  bindingsLoading.value = true;
  try {
    bindings.value = await getAIAgentSkillsApi(agentId.value);
  } catch (error) {
    console.error('[AdminAgentDetail] loadBindings', error);
    bindings.value = [];
    showRequestError(error, 'common.loadFailed');
  } finally {
    bindingsLoading.value = false;
  }
}

function openSkillBindingPicker() {
  skillPickerDrafts.value = grantsToDrafts(bindings.value);
  skillPickerOpen.value = true;
}

async function onSkillBindingPickerConfirm(
  _drafts: AgentSkillBindingDraftItem[],
) {
  try {
    await batchBindAIAgentSkillsApi(
      agentId.value,
      draftsToBatchPayload(_drafts),
    );
    message.success($t('admin.ai.agent.detail.saveSuccess'));
    await loadBindings();
  } catch (error) {
    console.error('[AdminAgentDetail] batchBind skills', error);
    showRequestError(error, 'common.saveFailed');
  }
}

function getSkillSourceTag(
  binding: AIAgentSkillGrantInfo,
): null | { color: string; text: string } {
  if (binding.skill_source_type === 'plugin') {
    return { text: $t('admin.ai.skillPackage.sourcePlugin'), color: 'purple' };
  }
  if (binding.package_is_system) {
    return { text: $t('admin.ai.skillPackage.system'), color: 'red' };
  }
  return null;
}

function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'disabled': {
      return 'red';
    }
    case 'draft': {
      return 'default';
    }
    case 'published': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

async function unbindSkill(skillId: number) {
  try {
    await unbindAIAgentSkillApi(agentId.value, skillId);
    await loadBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function updateConsentMode(bindingId: number, mode: string) {
  try {
    await updateAIAgentSkillGrantApi(agentId.value, bindingId, {
      default_consent_mode: mode,
    });
    await loadBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function toggleSkillEnabled(binding: AIAgentSkillGrantInfo) {
  if (binding.id === null || binding.id === undefined) return;
  try {
    await updateAIAgentSkillGrantApi(agentId.value, binding.id, {
      enabled: !binding.enabled,
    });
    await loadBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

const consentModeOptions = [
  { label: $t('admin.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('admin.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('admin.ai.agent.consentModeOptions.reject'), value: 'reject' },
];

function getSkillTypeText(type: string | undefined): string {
  if (!type) return '-';
  const key = `admin.ai.skill.type_options.${type}`;
  const text = $t(key);
  if (text === key) {
    return type
      .replaceAll('_', ' ')
      .replaceAll(/\b\w/g, (c) => c.toUpperCase());
  }
  return text;
}

// ==================== Knowledge Base Bindings Tab / 知识库绑定页签 ====================
const kbBindings = ref<AIAgentKBBindingInfo[]>([]);
const kbBindingsLoading = ref(false);
const kbPickerOpen = ref(false);
const kbPickerDrafts = ref<AgentKnowledgeBaseBindingDraftItem[]>([]);
const kbBindingScopeCount = computed(() => {
  const keys = new Set(
    kbBindings.value.map((binding) => binding.kb_scope || 'unknown'),
  );
  return keys.size;
});

async function loadKBBindings() {
  kbBindingsLoading.value = true;
  try {
    kbBindings.value = await getAIAgentKBsApi(agentId.value);
  } catch (error) {
    console.error('[AdminAgentDetail] loadKBBindings', error);
    kbBindings.value = [];
    showRequestError(error, 'common.loadFailed');
  } finally {
    kbBindingsLoading.value = false;
  }
}

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

function getKbOwnerText(binding: AIAgentKBBindingInfo): string {
  if (
    binding.kb_owner_tenant_id === null ||
    binding.kb_owner_tenant_id === undefined
  ) {
    return $t('admin.ai.agent.detail.kbOwnerPlatform');
  }
  return binding.kb_owner_tenant_name || `#${binding.kb_owner_tenant_id}`;
}

function openKBBindingPicker() {
  kbPickerDrafts.value = kbBindingsToDrafts(kbBindings.value);
  kbPickerOpen.value = true;
}

async function onKBBindingPickerConfirm(
  drafts: AgentKnowledgeBaseBindingDraftItem[],
) {
  try {
    await batchBindAIAgentKBsApi(agentId.value, kbDraftsToBatchPayload(drafts));
    message.success($t('admin.ai.agent.detail.saveSuccess'));
    await loadKBBindings();
  } catch (error) {
    console.error('[AdminAgentDetail] batchBind knowledge bases', error);
    showRequestError(error, 'common.saveFailed');
  }
}

async function unbindKB(knowledgeBaseId: number) {
  try {
    await unbindAIAgentKBApi(agentId.value, knowledgeBaseId);
    await loadKBBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function toggleKBEnabled(binding: AIAgentKBBindingInfo) {
  try {
    await updateAIAgentKBBindingApi(agentId.value, binding.id, {
      enabled: !binding.enabled,
    });
    await loadKBBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function updateKBWeight(bindingId: number, weight: number) {
  try {
    await updateAIAgentKBBindingApi(agentId.value, bindingId, { weight });
    await loadKBBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
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
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.hybrid'),
    value: 'hybrid',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.vector'),
    value: 'vector',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.searchModeOptions.keyword'),
    value: 'keyword',
  },
];

const ragRewriteOptions = [
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.none'),
    value: 'none',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.multi'),
    value: 'multi',
  },
  {
    label: $t('admin.ai.agent.knowledgeBase.rewriteOptions.hyde'),
    value: 'hyde',
  },
];

function initRagConfig() {
  if (!agent.value) return;
  const rc = (agent.value.rag_config ?? {}) as Record<string, unknown>;
  ragTopK.value = (rc.top_k as number | undefined) ?? 5;
  ragScoreThreshold.value = (rc.score_threshold as number | undefined) ?? 0.5;
  ragSearchMode.value =
    (rc.search_mode as 'hybrid' | 'keyword' | 'vector' | undefined) ?? 'hybrid';
  ragRewriteStrategy.value =
    (rc.rewrite_strategy as 'hyde' | 'multi' | 'none' | undefined) ?? 'none';
  ragRerankerEnabled.value = Boolean(rc.reranker_enabled);
  ragContextTokenRatio.value =
    (rc.context_token_ratio as number | undefined) ?? 0.6;
}

async function saveRagConfig() {
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

// ==================== Quota Tab / 配额页签 ====================
const quotaConversationsPerDay = ref<number | undefined>(undefined);
const quotaTokensPerDay = ref<number | undefined>(undefined);
const quotaTokensPerMonth = ref<number | undefined>(undefined);
const quotaMaxTurns = ref<number | undefined>(undefined);
const quotaMaxConcurrent = ref<number | undefined>(undefined);
const quotaUserConversationsPerDay = ref<number | undefined>(undefined);

function initQuota() {
  if (!agent.value) return;
  const qc = (agent.value.quota_config ?? {}) as Record<string, unknown>;
  quotaConversationsPerDay.value =
    (qc.conversations_per_day as number | undefined) ?? undefined;
  quotaTokensPerDay.value =
    (qc.tokens_per_day as number | undefined) ?? undefined;
  quotaTokensPerMonth.value =
    (qc.tokens_per_month as number | undefined) ?? undefined;
  quotaMaxTurns.value =
    (qc.max_turns_per_conversation as number | undefined) ?? undefined;
  quotaMaxConcurrent.value =
    (qc.max_concurrent as number | undefined) ?? undefined;
  quotaUserConversationsPerDay.value =
    (qc.user_conversations_per_day as number | undefined) ?? undefined;
}

async function saveQuota() {
  await saveFields({
    quota_config: {
      conversations_per_day: quotaConversationsPerDay.value ?? 0,
      tokens_per_day: quotaTokensPerDay.value ?? 0,
      tokens_per_month: quotaTokensPerMonth.value ?? 0,
      max_turns_per_conversation: quotaMaxTurns.value ?? 0,
      max_concurrent: quotaMaxConcurrent.value ?? 0,
      user_conversations_per_day: quotaUserConversationsPerDay.value ?? 0,
    },
  });
}

// ==================== Routing Config Tab / 路由配置页签 ====================
const routingState = ref(createAgentRoutingState());
const routingModelOptions = ref(createEmptyAgentRoutingModelOptions());

async function loadAdminRoutingModelOptions() {
  try {
    const chatRes = await getAIModelListApi({
      'page[size]': 200,
      'filter[type][eq]': 'chat',
      'filter[is_active][eq]': true,
    });
    const chatModels = chatRes.items || [];
    routingModelOptions.value = buildAgentRoutingModelOptions(chatModels);
    chatModelMaxOutputTokens.value =
      routingModelOptions.value.chatModelMaxOutputTokens;
  } catch {
    routingModelOptions.value = createEmptyAgentRoutingModelOptions();
    chatModelMaxOutputTokens.value = {};
  }
}

const tierOptions = [
  { label: $t('admin.ai.agent.routing.tier.fast'), value: 'fast' },
  { label: $t('admin.ai.agent.routing.tier.standard'), value: 'standard' },
  { label: $t('admin.ai.agent.routing.tier.premium'), value: 'premium' },
];

function initAdminRouting() {
  if (!agent.value) return;
  applyAgentRoutingConfig(
    routingState.value,
    (agent.value.routing_config ?? {}) as Record<string, unknown>,
  );
}

async function saveAdminRouting() {
  await saveFields({
    routing_config: buildAgentRoutingPayload(routingState.value),
  });
}

// ==================== AccessConfig Drawer / 访问配置抽屉 ====================
const [AccessConfigDrawerCmp, accessConfigApi] = useVbenDrawer({
  connectedComponent: AccessConfigDrawer,
});

function openAccessConfig() {
  openAccessConfigDrawer();
}

function openAccessConfigDrawer() {
  if (!agent.value) return;
  accessConfigApi.setData({
    id: agent.value.id,
    name: agent.value.name,
  });
  accessConfigApi.open();
}

// ==================== VersionHistory Drawer / 版本历史抽屉 ====================
const [VersionHistoryDrawerCmp, versionHistoryApi] = useVbenDrawer({
  connectedComponent: VersionHistoryDrawer,
});

function openVersionHistory() {
  openVersionHistoryDrawer();
}

function openVersionHistoryDrawer() {
  if (!agent.value) return;
  versionHistoryApi.setData({
    id: agent.value.id,
    publishedVersion: agent.value.published_version ?? null,
  });
  versionHistoryApi.open();
}

// ==================== Tab Change / 切换页签 ====================
function onTabChange(key: number | string) {
  activeTab.value = String(key);
  if (!agent.value) return;
  switch (key) {
    case 'chatConfig': {
      initChatConfig();
      break;
    }
    case 'knowledgeBases': {
      loadKBBindings();
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
    case 'rag': {
      initRagConfig();
      break;
    }
    case 'routing': {
      initAdminRouting();
      loadAdminRoutingModelOptions();
      break;
    }
    case 'skills': {
      loadBindings();
      break;
    }
  }
}

usePageAIContext({
  resource: '/admin/ai/agents',
  entityName: () => agent.value?.name ?? $t('admin.ai.agent.detail.title'),
  entityDescription: () => $t('admin.ai.agent.pageDesc'),
  data: () => ({
    agent_id: agentId.value,
    agent_name: agent.value?.name ?? '',
    status: agent.value?.status ?? '',
  }),
});

useDetailPageAi({
  refreshFn: () => loadAgent(),
  backRoute: '/admin/ai/agents',
  extra: [
    createSavePageOperation({
      name: 'save_model_params',
      label: $t('shared.pageOperation.saveModelParams'),
      description:
        'Save the current model parameters (temperature, max_tokens, top_p) / 保存当前模型参数',
      action: async () => {
        await saveModelParams();
      },
    }),
    createOpenCurrentPageOperation({
      name: 'open_access_config',
      label: $t('admin.ai.agent.accessConfig'),
      description:
        'Open the access configuration drawer for the current agent / 打开当前智能体的访问配置抽屉',
      available: () => !!agent.value,
      open: async () => {
        openAccessConfigDrawer();
      },
    }),
    createOpenCurrentPageOperation({
      name: 'open_version_history',
      label: $t('admin.ai.agent.versionHistory'),
      description:
        'Open the version history drawer for the current agent / 打开当前智能体的版本历史抽屉',
      available: () => !!agent.value,
      open: async () => {
        openVersionHistoryDrawer();
      },
    }),
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
                <Tag v-if="agent.is_system" color="purple" class="!mr-0">
                  {{ $t('admin.ai.agent.system') }}
                </Tag>
                <Tag :color="getStatusColor(agent.status)" class="!mr-0">
                  {{ getStatusText(agent.status) }}
                </Tag>
                <Button size="small" @click="openVersionHistory">
                  <IconifyIcon icon="lucide:history" class="mr-1 size-3.5" />
                  {{ $t('admin.ai.agent.versionHistory') }}
                </Button>
                <Button size="small" @click="openAccessConfig">
                  <IconifyIcon icon="lucide:shield" class="mr-1 size-3.5" />
                  {{ $t('admin.ai.agent.accessConfig') }}
                </Button>
              </div>
            </div>

            <!-- Identity block -->
            <div class="flex items-start gap-5">
              <!-- Avatar with upload overlay -->
              <div class="group relative shrink-0">
                <Upload
                  :show-upload-list="false"
                  :before-upload="beforeAvatarUpload"
                  :aria-label="$t('admin.ai.agent.detail.uploadAvatar')"
                  accept="image/*"
                >
                  <div
                    class="relative flex size-16 cursor-pointer items-center justify-center overflow-hidden rounded-2xl text-2xl font-bold shadow-sm ring-2 ring-offset-2 ring-offset-card"
                    :class="
                      agent.is_system
                        ? 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400'
                        : 'bg-primary/10 text-primary ring-primary/20'
                    "
                    :aria-label="$t('admin.ai.agent.detail.uploadAvatar')"
                    :title="$t('admin.ai.agent.detail.uploadAvatar')"
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
                <!-- Remove avatar button -->
                <button
                  v-if="avatarDisplayUrl && !avatarUploading"
                  class="absolute -right-1 -top-1 flex size-5 items-center justify-center rounded-full bg-destructive text-white opacity-0 shadow-sm transition-opacity group-hover:opacity-100"
                  type="button"
                  :aria-label="$t('admin.ai.agent.detail.removeAvatar')"
                  :title="$t('admin.ai.agent.detail.removeAvatar')"
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
                  {{ agent.description || $t('admin.ai.agent.noDescription') }}
                </p>

                <!-- Meta chips row -->
                <div class="flex flex-wrap items-center gap-2">
                  <div
                    v-if="agent.model_name"
                    class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
                  >
                    <IconifyIcon
                      icon="lucide:brain"
                      class="size-3.5 text-primary/70"
                    />
                    {{ agent.model_name }}
                  </div>
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
                      <IconifyIcon
                        :icon="getScopeIcon(agent.scope)"
                        class="size-3"
                      />
                      {{ getScopeText(agent.scope) }}
                    </div>
                  </Tag>
                  <Tag
                    :color="getOwnerTypeColor(agent.owner_type)"
                    class="!mr-0 !text-xs"
                  >
                    <div class="flex items-center gap-1">
                      <IconifyIcon icon="lucide:building-2" class="size-3" />
                      {{ getOwnerTypeText(agent.owner_type) }}
                    </div>
                  </Tag>
                  <PluginSourceBadge
                    v-if="agent.source_plugin"
                    :source-plugin="agent.source_plugin"
                    :source-plugin-display-name="
                      agent.source_plugin_display_name
                    "
                    :source-plugin-enabled="agent.source_plugin_enabled"
                  />
                  <!-- Routing status chip (clickable) -->
                  <button
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
                      $t('admin.ai.agent.routing.statusEnabled')
                    }}</span>
                    <span v-else>{{
                      $t('admin.ai.agent.routing.statusDisabled')
                    }}</span>
                  </button>
                </div>
                <Alert
                  v-if="agent.source_plugin"
                  type="info"
                  show-icon
                  class="mt-3 text-sm"
                >
                  <template #message>
                    {{
                      `${$t('admin.ai.skillPackage.sourcePlugin')}：${
                        agent.source_plugin_display_name || agent.source_plugin
                      }`
                    }}
                  </template>
                  <template #description>
                    <div class="flex flex-wrap items-center gap-2">
                      <span>{{
                        $t('admin.ai.agent.sourcePluginScopeLocked')
                      }}</span>
                      <Tag
                        class="!mr-0 !text-xs"
                        :color="getScopeColor(agent.scope)"
                      >
                        {{
                          getScopeText(agent.source_plugin_scope || agent.scope)
                        }}
                      </Tag>
                      <span v-if="agent.assigned_tenant_ids?.length">
                        {{
                          `${agent.assigned_tenant_ids.length} ${$t(
                            'common.scope.assignedTenantsLabel',
                          )}`
                        }}
                      </span>
                    </div>
                  </template>
                </Alert>
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
                  {{ $t('admin.ai.agent.detail.overview') }}
                </span>
              </template>
              <div class="flex flex-col gap-5 p-5 pt-3">
                <!-- Basic Info Cards -->
                <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:activity"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">{{
                        $t('admin.ai.agent.status')
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
                        $t('admin.ai.agent.executionMode')
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
                        $t('admin.ai.agent.modelName')
                      }}</span>
                    </div>
                    <span class="text-sm font-medium">{{
                      agent.model_name || '-'
                    }}</span>
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:globe"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">{{
                        $t('common.scope.label')
                      }}</span>
                    </div>
                    <Tag
                      :color="getScopeColor(agent.scope)"
                      class="!mr-0 !text-xs"
                    >
                      {{ getScopeText(agent.scope) }}
                    </Tag>
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
                          $t('admin.ai.agent.memory.title')
                        }}</span>
                      </div>
                      <p class="text-xs text-muted-foreground">
                        {{ $t('admin.ai.agent.memory.desc') }}
                      </p>
                    </div>
                    <Switch
                      :checked="adminMemoryEnabled"
                      :loading="memorySaving"
                      :aria-label="$t('admin.ai.agent.memory.agentSwitch')"
                      @change="(val) => updateAdminMemoryEnabled(Boolean(val))"
                    />
                  </div>
                  <Spin :spinning="memoryLoading" class="mt-3 block">
                    <div
                      v-if="memoryConfig"
                      class="grid grid-cols-1 gap-2 text-xs md:grid-cols-3"
                    >
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('admin.ai.agent.memory.platformDefault') }}
                        </div>
                        <div class="mt-1 font-medium">
                          {{
                            memoryConfig.platform_default_memory_enabled
                              ? $t('admin.ai.agent.memory.enabled')
                              : $t('admin.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('admin.ai.agent.memory.agentSwitch') }}
                        </div>
                        <div class="mt-1 font-medium">
                          {{
                            memoryConfig.admin_agent_memory_enabled
                              ? $t('admin.ai.agent.memory.enabled')
                              : $t('admin.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                      <div class="rounded-lg border bg-background px-3 py-2">
                        <div class="text-muted-foreground">
                          {{ $t('admin.ai.agent.memory.effective') }}
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
                              ? $t('admin.ai.agent.memory.enabled')
                              : $t('admin.ai.agent.memory.disabled')
                          }}
                        </div>
                      </div>
                    </div>
                  </Spin>
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
                        $t('admin.ai.agent.systemPrompt')
                      }}</span>
                    </div>
                    <Button
                      v-if="!editingPrompt"
                      size="small"
                      type="link"
                      @click="startEditPrompt"
                    >
                      <IconifyIcon icon="lucide:pencil" class="mr-1 size-3.5" />
                      {{ $t('common.edit') }}
                    </Button>
                    <div v-else class="flex gap-2">
                      <Button size="small" @click="editingPrompt = false">
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
                  {{ $t('admin.ai.agent.detail.modelParams') }}
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
                        $t('admin.ai.agent.temperature')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('admin.ai.agent.help.temperature') }}
                    </p>
                    <InputNumber
                      v-model:value="modelTemp"
                      :min="0"
                      :max="2"
                      :step="0.1"
                      :placeholder="
                        $t('admin.ai.agent.placeholder.inputTemperature')
                      "
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
                        $t('admin.ai.agent.maxTokens')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('admin.ai.agent.help.maxTokens') }}
                    </p>
                    <InputNumber
                      v-model:value="modelMaxTokens"
                      :min="1"
                      :max="128000"
                      :placeholder="
                        $t('admin.ai.agent.placeholder.inputMaxTokens')
                      "
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
                        $t('admin.ai.agent.topP')
                      }}</label>
                    </div>
                    <p class="mb-2 text-xs text-muted-foreground">
                      {{ $t('admin.ai.agent.help.topP') }}
                    </p>
                    <InputNumber
                      v-model:value="modelTopP"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      :placeholder="$t('admin.ai.agent.placeholder.inputTopP')"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="mt-5">
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
                  {{ $t('admin.ai.agent.detail.chatConfig') }}
                </span>
              </template>
              <div class="flex flex-col gap-4 p-5 pt-3">
                <!-- System Prompt (editable, with variable quick-insert) -->
                <div
                  class="rounded-xl border border-primary/20 bg-primary/5 p-4"
                >
                  <div class="mb-2 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <IconifyIcon
                        icon="lucide:message-square-code"
                        class="size-4 text-primary"
                      />
                      <span class="text-sm font-semibold text-primary">{{
                        $t('admin.ai.agent.systemPrompt')
                      }}</span>
                      <span
                        v-if="agent?.is_system"
                        class="rounded-full bg-amber-500/10 px-1.5 py-px text-[10px] text-amber-600"
                        >{{
                          $t('admin.ai.agent.systemAgentDesc').split('，')[0]
                        }}</span
                      >
                    </div>
                  </div>
                  <!-- Variable quick-insert chips -->
                  <div
                    v-if="chatInputVars.length > 0"
                    class="mb-2 flex flex-wrap gap-1.5"
                  >
                    <span class="text-xs text-muted-foreground"
                      >{{
                        $t('admin.ai.agent.detail.chatConfigPromptHint')
                      }}:</span
                    >
                    <button
                      v-for="v in chatInputVars"
                      :key="v.name"
                      :disabled="agent?.is_system"
                      class="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                      @click="insertVarAtCursor(v.name)"
                    >
                      <span v-text="formatVarChip(v.name)"></span>
                    </button>
                  </div>
                  <Textarea
                    :ref="
                      (el) => {
                        chatSystemPromptRef = el as HTMLTextAreaElement | null;
                      }
                    "
                    v-model:value="chatSystemPrompt"
                    :rows="6"
                    :disabled="agent?.is_system"
                    :placeholder="
                      $t('admin.ai.agent.placeholder.inputSystemPrompt')
                    "
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
                      $t('admin.ai.agent.welcomeMessage')
                    }}</label>
                  </div>
                  <Textarea
                    v-model:value="chatWelcome"
                    :rows="3"
                    :placeholder="
                      $t('admin.ai.agent.placeholder.inputWelcomeMessage')
                    "
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
                      $t('admin.ai.agent.suggestedQuestions')
                    }}</label>
                  </div>
                  <Textarea
                    v-model:value="chatSuggestions"
                    :rows="4"
                    :placeholder="
                      $t('admin.ai.agent.placeholder.inputSuggestedQuestions')
                    "
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
                      $t('admin.ai.agent.inputVariables.title')
                    }}</label>
                  </div>
                  <InputVariablesEditor v-model="chatInputVars" />
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
                      $t('admin.ai.agent.contextConfig.title')
                    }}</label>
                  </div>
                  <div
                    class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/60 bg-background/50 px-3 py-2"
                  >
                    <div class="min-w-0">
                      <div class="text-sm font-medium">
                        {{
                          $t(
                            'admin.ai.agent.contextConfig.longTermMemoryEnabled',
                          )
                        }}
                      </div>
                      <p class="mt-0.5 text-xs text-muted-foreground">
                        {{
                          $t('admin.ai.agent.contextConfig.longTermMemoryHint')
                        }}
                      </p>
                    </div>
                    <Switch v-model:checked="chatLongTermMemoryEnabled" />
                  </div>
                  <div class="grid grid-cols-2 gap-4">
                    <div>
                      <label class="mb-1 block text-xs text-muted-foreground">{{
                        $t('admin.ai.agent.contextConfig.maxHistoryMessages')
                      }}</label>
                      <InputNumber
                        v-model:value="chatContextMessages"
                        :min="0"
                        class="w-full"
                      />
                    </div>
                    <div>
                      <label class="mb-1 block text-xs text-muted-foreground">{{
                        $t('admin.ai.agent.contextConfig.maxHistoryTokens')
                      }}</label>
                      <InputNumber
                        v-model:value="chatContextTokens"
                        :min="0"
                        class="w-full"
                      />
                    </div>
                  </div>
                </div>
                <div>
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
                  {{ $t('admin.ai.agent.detail.skillBindings') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <AgentSkillBindingPicker
                  v-model:open="skillPickerOpen"
                  v-model="skillPickerDrafts"
                  @confirm="onSkillBindingPickerConfirm"
                />
                <Spin :spinning="bindingsLoading">
                  <div class="flex flex-col gap-4">
                    <div
                      class="rounded-2xl border border-border/70 bg-muted/20 p-4"
                    >
                      <div
                        class="flex flex-wrap items-start justify-between gap-3"
                      >
                        <div class="min-w-0 flex-1">
                          <div class="flex flex-wrap items-center gap-2">
                            <span class="text-sm font-semibold text-foreground">
                              {{ $t('admin.ai.agent.detail.skillBindings') }}
                            </span>
                            <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                              {{
                                $t('admin.ai.agent.skillPicker.selectedCount', {
                                  count: bindings.length,
                                })
                              }}
                            </Tag>
                            <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                              {{
                                $t(
                                  'admin.ai.agent.skillPicker.selectionSummary',
                                  {
                                    skills: bindings.length,
                                    packages: bindingPackageCount,
                                  },
                                )
                              }}
                            </Tag>
                          </div>
                          <p
                            class="mt-1 text-xs leading-5 text-muted-foreground"
                          >
                            {{ $t('admin.ai.agent.help.skillBindings') }}
                          </p>
                        </div>
                        <Button type="primary" @click="openSkillBindingPicker">
                          <IconifyIcon
                            icon="lucide:settings-2"
                            class="mr-1 size-4"
                          />
                          {{ $t('admin.ai.agent.skillPicker.manageBindings') }}
                        </Button>
                      </div>
                    </div>

                    <div v-if="bindings.length > 0" class="flex flex-col gap-2">
                      <div
                        v-for="binding in bindings"
                        :key="binding.skill_id"
                        class="rounded-xl border bg-background px-4 py-3 transition-colors"
                      >
                        <div class="flex items-center justify-between gap-4">
                          <div class="flex min-w-0 flex-1 items-center gap-3">
                            <div
                              class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10"
                            >
                              <IconifyIcon
                                :icon="
                                  getSkillTypeIcon(
                                    binding.skill_type || 'toolkit',
                                  )
                                "
                                class="size-4"
                                :style="{
                                  color: `var(--ant-color-${getSkillTypeColor(binding.skill_type || 'toolkit')})`,
                                }"
                              />
                            </div>
                            <div class="min-w-0 flex-1">
                              <div class="flex items-center gap-2">
                                <span class="truncate text-sm font-medium">
                                  {{
                                    binding.skill_name || `#${binding.skill_id}`
                                  }}
                                </span>
                                <Tag
                                  :color="
                                    getSkillTypeColor(
                                      binding.skill_type || 'toolkit',
                                    )
                                  "
                                  class="!mr-0 !text-[10px]"
                                >
                                  {{
                                    getSkillTypeText(
                                      binding.skill_type || undefined,
                                    )
                                  }}
                                </Tag>
                                <Tag
                                  v-if="binding.package_name"
                                  class="!mr-0 !text-[10px]"
                                >
                                  {{ binding.package_name }}
                                </Tag>
                                <Tag
                                  v-if="getSkillSourceTag(binding)"
                                  :color="getSkillSourceTag(binding)!.color"
                                  class="!mr-0 !text-[10px]"
                                >
                                  {{ getSkillSourceTag(binding)!.text }}
                                </Tag>
                              </div>
                              <p
                                v-if="
                                  binding.skill_description ||
                                  binding.package_description
                                "
                                class="mt-0.5 truncate text-xs text-muted-foreground"
                              >
                                {{
                                  binding.skill_description ||
                                  binding.package_description
                                }}
                              </p>
                            </div>
                          </div>
                          <div class="flex items-center gap-2">
                            <Switch
                              :checked="binding.enabled"
                              size="small"
                              :aria-label="`${binding.skill_name ?? binding.skill_id}`"
                              @change="toggleSkillEnabled(binding)"
                            />
                            <ASelect
                              :value="binding.default_consent_mode"
                              :options="consentModeOptions"
                              size="small"
                              class="!w-28"
                              @change="
                                (val) =>
                                  binding.id !== null &&
                                  updateConsentMode(binding.id, String(val))
                              "
                            />
                            <Popconfirm
                              :title="$t('common.confirmDelete')"
                              @confirm="unbindSkill(binding.skill_id)"
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
                    </div>

                    <div
                      v-if="bindings.length === 0 && !bindingsLoading"
                      class="rounded-2xl border border-dashed border-border/70 bg-background px-6 py-10 text-center"
                    >
                      <div
                        class="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
                      >
                        <IconifyIcon icon="lucide:puzzle" class="size-6" />
                      </div>
                      <div class="mt-4 text-sm font-semibold text-foreground">
                        {{ $t('admin.ai.agent.skillPicker.emptySelected') }}
                      </div>
                      <div
                        class="mx-auto mt-2 max-w-xl text-xs leading-6 text-muted-foreground"
                      >
                        {{ $t('admin.ai.agent.skillPicker.detailEmptyHint') }}
                      </div>
                      <Button
                        class="mt-5"
                        type="primary"
                        @click="openSkillBindingPicker"
                      >
                        <IconifyIcon
                          icon="lucide:sparkles"
                          class="mr-1 size-4"
                        />
                        {{ $t('admin.ai.agent.skillPicker.manageBindings') }}
                      </Button>
                    </div>
                  </div>
                </Spin>
              </div>
            </TabPane>

            <TabPane key="rag">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:search" class="size-3.5" />
                  {{ $t('admin.ai.agent.knowledgeBase.title') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <p class="mb-4 text-xs text-muted-foreground">
                  {{ $t('admin.ai.agent.detail.ragHint') }}
                </p>
                <div class="grid max-w-3xl grid-cols-1 gap-3 md:grid-cols-2">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="admin-agent-rag-search-mode"
                      class="mb-2 block text-xs text-muted-foreground"
                      >{{
                        $t('admin.ai.agent.knowledgeBase.searchMode')
                      }}</label
                    >
                    <ASelect
                      id="admin-agent-rag-search-mode"
                      v-model:value="ragSearchMode"
                      :options="ragSearchModeOptions"
                      :aria-label="
                        $t('admin.ai.agent.knowledgeBase.searchMode')
                      "
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="admin-agent-rag-rewrite-strategy"
                      class="mb-2 block text-xs text-muted-foreground"
                      >{{
                        $t('admin.ai.agent.knowledgeBase.rewriteStrategy')
                      }}</label
                    >
                    <ASelect
                      id="admin-agent-rag-rewrite-strategy"
                      v-model:value="ragRewriteStrategy"
                      :options="ragRewriteOptions"
                      :aria-label="
                        $t('admin.ai.agent.knowledgeBase.rewriteStrategy')
                      "
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="admin-agent-rag-top-k"
                      class="mb-2 block text-xs text-muted-foreground"
                      >{{ $t('admin.ai.agent.knowledgeBase.topK') }}</label
                    >
                    <InputNumber
                      id="admin-agent-rag-top-k"
                      v-model:value="ragTopK"
                      :min="1"
                      :max="20"
                      :aria-label="$t('admin.ai.agent.knowledgeBase.topK')"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="admin-agent-rag-score-threshold"
                      class="mb-2 block text-xs text-muted-foreground"
                      >{{
                        $t('admin.ai.agent.knowledgeBase.scoreThreshold')
                      }}</label
                    >
                    <InputNumber
                      id="admin-agent-rag-score-threshold"
                      v-model:value="ragScoreThreshold"
                      :min="0"
                      :max="1"
                      :step="0.05"
                      :precision="2"
                      :aria-label="
                        $t('admin.ai.agent.knowledgeBase.scoreThreshold')
                      "
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label
                      for="admin-agent-rag-context-token-ratio"
                      class="mb-2 block text-xs text-muted-foreground"
                      >{{
                        $t('admin.ai.agent.knowledgeBase.contextTokenRatio')
                      }}</label
                    >
                    <InputNumber
                      id="admin-agent-rag-context-token-ratio"
                      v-model:value="ragContextTokenRatio"
                      :min="0.1"
                      :max="0.9"
                      :step="0.05"
                      :precision="2"
                      :aria-label="
                        $t('admin.ai.agent.knowledgeBase.contextTokenRatio')
                      "
                      class="w-full"
                    />
                  </div>
                  <div
                    class="flex flex-col items-start gap-3 rounded-xl border bg-accent/30 p-4"
                  >
                    <div class="min-w-0">
                      <label class="mb-2 block text-xs text-muted-foreground">{{
                        $t('admin.ai.agent.knowledgeBase.rerankerEnabled')
                      }}</label>
                      <p class="text-xs text-muted-foreground">
                        {{
                          $t('admin.ai.agent.knowledgeBase.rerankerEnabledHelp')
                        }}
                      </p>
                    </div>
                    <Switch
                      v-model:checked="ragRerankerEnabled"
                      class="!w-auto shrink-0"
                      :aria-label="
                        $t('admin.ai.agent.knowledgeBase.rerankerEnabled')
                      "
                    />
                  </div>
                </div>
                <div class="mt-5">
                  <Button
                    type="primary"
                    :loading="saving"
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
                  {{ $t('admin.ai.agent.detail.knowledgeBases') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <AgentKnowledgeBaseBindingPicker
                  v-model:open="kbPickerOpen"
                  v-model="kbPickerDrafts"
                  :fetch-candidates="
                    () => getAdminSelectableKBApi({ agent_id: agentId })
                  "
                  @confirm="onKBBindingPickerConfirm"
                />
                <Spin :spinning="kbBindingsLoading">
                  <div class="flex flex-col gap-4">
                    <Alert
                      v-if="agent.owner_type === 'platform'"
                      type="info"
                      show-icon
                      class="text-sm"
                      :message="
                        $t('admin.ai.agent.detail.knowledgeBasesGlobalHint')
                      "
                    />
                    <div
                      class="rounded-2xl border border-border/70 bg-muted/20 p-4"
                    >
                      <div
                        class="flex flex-wrap items-start justify-between gap-3"
                      >
                        <div class="min-w-0 flex-1">
                          <div class="flex flex-wrap items-center gap-2">
                            <span class="text-sm font-semibold text-foreground">
                              {{ $t('admin.ai.agent.detail.knowledgeBases') }}
                            </span>
                            <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                              {{
                                $t('admin.ai.agent.kbPicker.selectedCount', {
                                  count: kbBindings.length,
                                })
                              }}
                            </Tag>
                            <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                              {{
                                $t('admin.ai.agent.kbPicker.selectionSummary', {
                                  count: kbBindings.length,
                                  scopes: kbBindingScopeCount,
                                })
                              }}
                            </Tag>
                          </div>
                          <p
                            class="mt-1 text-xs leading-5 text-muted-foreground"
                          >
                            {{ $t('admin.ai.agent.detail.kbWeightFusionHint') }}
                          </p>
                        </div>
                        <Button type="primary" @click="openKBBindingPicker">
                          <IconifyIcon
                            icon="lucide:settings-2"
                            class="mr-1 size-4"
                          />
                          {{ $t('admin.ai.agent.kbPicker.manageBindings') }}
                        </Button>
                      </div>
                    </div>

                    <div
                      v-if="kbBindings.length > 0"
                      class="flex flex-col gap-2"
                    >
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
                            <div class="flex items-center gap-2">
                              <span class="text-sm font-medium">{{
                                b.kb_name || `#${b.knowledge_base_id}`
                              }}</span>
                              <Tag
                                v-if="b.kb_document_count != null"
                                class="!mr-0 !text-[10px]"
                              >
                                {{ b.kb_document_count }}
                                {{ $t('admin.ai.agent.detail.kbDocCount') }}
                              </Tag>
                            </div>
                            <p
                              v-if="b.kb_description"
                              class="mt-0.5 truncate text-xs text-muted-foreground"
                            >
                              {{ b.kb_description }}
                            </p>
                            <div class="mt-1 flex flex-wrap gap-1.5">
                              <Tag class="!mr-0 !text-[10px]">
                                {{ $t('admin.ai.agent.detail.kbCreatorTenant') }}:
                                {{ getKbOwnerText(b) }}
                              </Tag>
                              <Tag
                                v-if="b.kb_embedding_model_name"
                                class="!mr-0 !text-[10px]"
                              >
                                {{
                                  $t('admin.ai.agent.detail.kbEmbeddingModel')
                                }}:
                                {{ b.kb_embedding_model_name }}
                              </Tag>
                              <Tag
                                v-if="b.kb_embedding_dimensions != null"
                                class="!mr-0 !text-[10px]"
                              >
                                {{
                                  $t(
                                    'admin.ai.agent.detail.kbEmbeddingDimensions',
                                  )
                                }}:
                                {{ b.kb_embedding_dimensions }}
                              </Tag>
                              <Tag
                                v-if="b.kb_chunk_strategy"
                                class="!mr-0 !text-[10px]"
                              >
                                {{
                                  $t('admin.ai.agent.detail.kbChunkStrategy')
                                }}:
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
                              $t('admin.ai.agent.detail.kbWeight')
                            }}</span>
                            <InputNumber
                              :value="b.weight"
                              :min="0.1"
                              :max="2"
                              :step="0.1"
                              size="small"
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
                            :aria-label="`${$t('admin.ai.agent.detail.kbEnabled')}: ${b.kb_name ?? b.knowledge_base_id}`"
                            @change="toggleKBEnabled(b)"
                          />
                          <!-- Unbind -->
                          <Popconfirm
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

                    <div
                      v-if="kbBindings.length === 0 && !kbBindingsLoading"
                      class="rounded-2xl border border-dashed border-border/70 bg-background px-6 py-10 text-center"
                    >
                      <div
                        class="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
                      >
                        <IconifyIcon icon="lucide:library-big" class="size-6" />
                      </div>
                      <div class="mt-4 text-sm font-semibold text-foreground">
                        {{ $t('admin.ai.agent.kbPicker.emptySelected') }}
                      </div>
                      <div
                        class="mx-auto mt-2 max-w-xl text-xs leading-6 text-muted-foreground"
                      >
                        {{ $t('admin.ai.agent.kbPicker.detailEmptyHint') }}
                      </div>
                      <Button
                        class="mt-5"
                        type="primary"
                        @click="openKBBindingPicker"
                      >
                        <IconifyIcon
                          icon="lucide:sparkles"
                          class="mr-1 size-4"
                        />
                        {{ $t('admin.ai.agent.kbPicker.manageBindings') }}
                      </Button>
                    </div>
                  </div>
                </Spin>
              </div>
            </TabPane>

            <!-- ========== 配额管理 ========== -->
            <TabPane key="quota">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:gauge" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.quota') }}
                </span>
              </template>
              <div class="p-5 pt-3">
                <p class="mb-4 text-xs text-muted-foreground">
                  {{ $t('admin.ai.agent.detail.noQuotaLimit') }}
                </p>
                <div class="grid max-w-2xl grid-cols-1 gap-3 md:grid-cols-2">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.conversationsPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaConversationsPerDay"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.tokensPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaTokensPerDay"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.tokensPerMonth')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaTokensPerMonth"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.maxTurnsPerConversation')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaMaxTurns"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.maxConcurrent')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaMaxConcurrent"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('admin.ai.agent.quotaConfig.userConversationsPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaUserConversationsPerDay"
                      :min="0"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="mt-5">
                  <Button type="primary" :loading="saving" @click="saveQuota">
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
                  {{ $t('admin.ai.agent.detail.routing') }}
                  <span
                    v-if="isRoutingEnabled"
                    class="inline-block size-2 rounded-full bg-green-500"
                  ></span>
                </span>
              </template>
              <AgentRoutingTab
                v-model:state="routingState"
                i18n-prefix="admin.ai.agent"
                :model-options="routingModelOptions"
                :saving="saving"
                :tier-options="tierOptions"
                @save="saveAdminRouting"
              />
            </TabPane>
          </Tabs>
        </div>
      </div>
    </Spin>
    <AccessConfigDrawerCmp />
    <VersionHistoryDrawerCmp @success="loadAgent" />
  </Page>
</template>
