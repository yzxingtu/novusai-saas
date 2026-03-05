<script lang="ts" setup>
/**
 * 租户端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 */
import type {
  AgentInfo,
  AgentMemoryConfig,
  AgentSkillBindingInfo,
} from '#/api/tenant/agents';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

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
} from 'ant-design-vue';

import {
  batchBindPackagesApi,
  getAgentDetailApi,
  getAgentMemoryConfigApi,
  getAgentSkillsApi,
  unbindPackageApi,
  updateAgentApi,
  updateAgentMemoryConfigApi,
  updateAgentSkillBindingApi,
} from '#/api/tenant/agents';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { getAvailablePackagesApi } from '#/api/tenant/skill-packages';
import { $t } from '#/locales';
import {
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import { getExecutionModeText, getStatusColor, getStatusText } from './data';
import AccessConfigDrawer from './modules/AccessConfigDrawer.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'TenantAgentDetail' });

// ==================== AccessConfig Drawer ====================
const [AccessConfigDrawerCmp, accessConfigApi] = useVbenDrawer({
  connectedComponent: AccessConfigDrawer,
});

function openAccessConfig() {
  if (!agent.value) return;
  accessConfigApi.setData({ id: agent.value.id, name: agent.value.name });
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
const isTenantOwned = computed(
  () => agent.value?.scope === 'all_tenants' && agent.value?.tenant_id !== null,
);

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

function initModelParams() {
  if (!agent.value) return;
  modelTemp.value = agent.value.temperature ?? 0.7;
  modelMaxTokens.value = agent.value.max_tokens ?? undefined;
  modelTopP.value = agent.value.top_p ?? undefined;
}

async function saveModelParams() {
  await saveFields({
    temperature: modelTemp.value,
    max_tokens: modelMaxTokens.value ?? null,
    top_p: modelTopP.value ?? null,
  });
}

// ==================== Chat Config Tab ====================
const chatWelcome = ref('');
const chatSuggestions = ref('');
const chatInputVars = ref('');
const chatContextMessages = ref(20);
const chatContextTokens = ref(0);

function initChatConfig() {
  if (!agent.value) return;
  chatWelcome.value = agent.value.welcome_message || '';
  chatSuggestions.value = Array.isArray(agent.value.suggested_questions)
    ? JSON.stringify(agent.value.suggested_questions, null, 2)
    : '[]';
  chatInputVars.value = Array.isArray(agent.value.input_variables)
    ? JSON.stringify(agent.value.input_variables, null, 2)
    : '[]';
  const cc = (agent.value.context_config ?? {}) as Record<string, number>;
  chatContextMessages.value = cc.max_history_messages ?? 20;
  chatContextTokens.value = cc.max_history_tokens ?? 0;
}

function safeJsonParse(str: string): null | unknown[] {
  if (!str || str.trim() === '' || str.trim() === '[]') return null;
  try {
    const parsed = JSON.parse(str);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

async function saveChatConfig() {
  await saveFields({
    welcome_message: chatWelcome.value || null,
    suggested_questions: safeJsonParse(chatSuggestions.value),
    input_variables: safeJsonParse(chatInputVars.value),
    context_config: {
      max_history_messages: chatContextMessages.value,
      max_history_tokens: chatContextTokens.value,
    },
  });
}

// ==================== Skill Bindings Tab ====================
const bindings = ref<AgentSkillBindingInfo[]>([]);
const bindingsLoading = ref(false);
const availablePackages = ref<
  Array<{
    label: string;
    scope?: string;
    source_plugin?: string;
    value: number;
  }>
>([]);
const selectedNewPkg = ref<number | undefined>();

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

async function loadAvailablePackages() {
  try {
    availablePackages.value = await getAvailablePackagesApi();
  } catch {
    availablePackages.value = [];
  }
}

const unboundPackages = computed(() => {
  const boundIds = new Set(bindings.value.map((b) => b.package_id));
  return availablePackages.value.filter((p) => !boundIds.has(p.value));
});

async function bindPackage() {
  if (!selectedNewPkg.value) return;
  const currentIds = bindings.value.map((b) => b.package_id);
  currentIds.push(selectedNewPkg.value);
  try {
    await batchBindPackagesApi(agentId.value, currentIds);
    selectedNewPkg.value = undefined;
    await loadBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function unbindPkg(packageId: number) {
  try {
    await unbindPackageApi(agentId.value, packageId);
    await loadBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

async function updateConsentMode(bindingId: number, mode: string) {
  try {
    await updateAgentSkillBindingApi(agentId.value, bindingId, {
      consent_mode: mode,
    });
    await loadBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

const consentModeOptions = [
  { label: $t('tenant.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('tenant.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('tenant.ai.agent.consentModeOptions.reject'), value: 'reject' },
];

function getScopeTagProps(
  scope?: string,
  sourcePlugin?: string,
): null | { color: string; text: string } {
  if (sourcePlugin)
    return {
      text: $t('tenant.ai.skillPackage.scopeTag.plugin'),
      color: 'purple',
    };
  if (!scope) return null;
  return { text: getScopeText(scope), color: getScopeColor(scope) };
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
  } catch {
    // fallback: empty list
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
      loadAvailablePackages();
      break;
    }
  }
}
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
                  v-if="isTenantOwned"
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
              <div class="shrink-0">
                <div
                  v-if="agent.avatar"
                  class="flex size-16 items-center justify-center overflow-hidden rounded-2xl shadow-sm ring-2 ring-primary/20 ring-offset-2 ring-offset-card"
                >
                  <img :src="agent.avatar" class="size-full object-cover" />
                </div>
                <div
                  v-else
                  class="flex size-16 items-center justify-center rounded-2xl bg-primary/10 text-2xl font-bold text-primary shadow-sm ring-2 ring-primary/20 ring-offset-2 ring-offset-card"
                >
                  {{ (agent.name || '?').charAt(0).toUpperCase() }}
                </div>
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
                      <IconifyIcon
                        :icon="getScopeIcon(agent.scope)"
                        class="size-3"
                      />
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
                    <InputNumber
                      v-model:value="modelTemp"
                      :min="0"
                      :max="2"
                      :step="0.1"
                      :disabled="!isTenantOwned"
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
                    <InputNumber
                      v-model:value="modelMaxTokens"
                      :min="1"
                      :max="128000"
                      :disabled="!isTenantOwned"
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
                    <InputNumber
                      v-model:value="modelTopP"
                      :min="0"
                      :max="1"
                      :step="0.1"
                      :disabled="!isTenantOwned"
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
                    :rows="3"
                    :disabled="!isTenantOwned"
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
                  <Textarea
                    v-model:value="chatInputVars"
                    :rows="3"
                    :disabled="!isTenantOwned"
                    class="w-full font-mono text-xs"
                  />
                  <p class="mt-1 text-xs text-muted-foreground">JSON</p>
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
                    <!-- Add binding (tenant-owned only) -->
                    <div
                      v-if="isTenantOwned"
                      class="flex items-center gap-3 rounded-xl border bg-accent/30 p-4"
                    >
                      <ASelect
                        v-model:value="selectedNewPkg"
                        :options="unboundPackages"
                        :placeholder="
                          $t('tenant.ai.agent.placeholder.selectSkillPackages')
                        "
                        show-search
                        option-filter-prop="label"
                        class="flex-1"
                      >
                        <template
                          #option="{ label: optLabel, value: optValue }"
                        >
                          <div class="flex items-center justify-between gap-2">
                            <span>{{ optLabel }}</span>
                            <Tag
                              v-if="
                                getScopeTagProps(
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.scope,
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.source_plugin,
                                )
                              "
                              :color="
                                getScopeTagProps(
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.scope,
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.source_plugin,
                                )!.color
                              "
                              class="mr-0 text-xs"
                            >
                              {{
                                getScopeTagProps(
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.scope,
                                  availablePackages.find(
                                    (p) => p.value === optValue,
                                  )?.source_plugin,
                                )!.text
                              }}
                            </Tag>
                          </div>
                        </template>
                      </ASelect>
                      <Button
                        type="primary"
                        :disabled="!selectedNewPkg"
                        @click="bindPackage"
                      >
                        <IconifyIcon icon="lucide:plus" class="mr-1" />
                        {{ $t('common.add') }}
                      </Button>
                    </div>

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
                          class="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3"
                        >
                          <div class="flex items-center gap-3">
                            <IconifyIcon
                              icon="lucide:lock"
                              class="size-4 text-primary/50"
                            />
                            <span class="text-sm font-medium">{{
                              b.package_name || `#${b.package_id}`
                            }}</span>
                            <Tag
                              v-if="b.package_scope"
                              :color="getScopeColor(b.package_scope)"
                              class="!text-[10px]"
                            >
                              {{ getScopeText(b.package_scope) }}
                            </Tag>
                          </div>
                          <Tag color="blue" class="!text-[10px]">
                            <IconifyIcon
                              icon="lucide:zap"
                              class="mr-0.5 inline size-3"
                            />
                            {{ $t('common.bindMode.auto') }}
                          </Tag>
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
                          class="flex items-center justify-between rounded-xl border bg-background px-4 py-3"
                        >
                          <div class="flex items-center gap-3">
                            <div
                              class="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary"
                            >
                              {{ (b.package_name || '?').charAt(0) }}
                            </div>
                            <span class="text-sm font-medium">{{
                              b.package_name || `#${b.package_id}`
                            }}</span>
                            <Tag
                              v-if="b.package_scope"
                              :color="getScopeColor(b.package_scope)"
                              class="!text-[10px]"
                            >
                              {{ getScopeText(b.package_scope) }}
                            </Tag>
                          </div>
                          <div class="flex items-center gap-2">
                            <ASelect
                              v-if="isTenantOwned"
                              :value="b.consent_mode"
                              :options="consentModeOptions"
                              size="small"
                              class="!w-28"
                              @change="
                                (val) =>
                                  b.id !== null &&
                                  updateConsentMode(b.id, String(val))
                              "
                            />
                            <Tag
                              v-else
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
                            <Popconfirm
                              v-if="isTenantOwned"
                              :title="$t('common.confirmDelete')"
                              @confirm="unbindPkg(b.package_id)"
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

                    <Empty v-if="bindings.length === 0 && !bindingsLoading" />
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
                <p class="mb-4 text-xs text-muted-foreground">
                  {{ $t('tenant.ai.agent.detail.noQuotaLimit') }}
                </p>
                <div class="grid max-w-2xl grid-cols-1 gap-3 md:grid-cols-2">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <label class="mb-2 block text-xs text-muted-foreground">{{
                      $t('tenant.ai.agent.quotaConfig.conversationsPerDay')
                    }}</label>
                    <InputNumber
                      v-model:value="quotaConversationsPerDay"
                      :min="0"
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
