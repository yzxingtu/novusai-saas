<script lang="ts" setup>
defineOptions({ name: 'TenantAgentDetail' });
/**
 * 租户端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 */
import type { AgentInfo, AgentSkillBindingInfo } from '#/api/tenant/agents';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Descriptions,
  DescriptionsItem,
  Empty,
  InputNumber,
  message,
  Select as ASelect,
  Spin,
  Switch,
  Tabs,
  TabPane,
  Tag,
  Textarea,
} from 'ant-design-vue';

import {
  batchBindPackagesApi,
  getAgentDetailApi,
  getAgentSkillsApi,
  unbindPackageApi,
  updateAgentApi,
} from '#/api/tenant/agents';
import { getAvailablePackagesApi } from '#/api/tenant/skill-packages';
import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

import {
  getExecutionModeText,
  getStatusText,
  getStatusColor,
} from './data';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

// ==================== Route ====================
const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

// ==================== State ====================
const loading = ref(false);
const saving = ref(false);
const agent = ref<AgentInfo | null>(null);
const activeTab = ref('overview');

// ==================== Load ====================
async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAgentDetailApi(agentId.value);
  } catch {
    message.error($t('common.loadFailed'));
  } finally {
    loading.value = false;
  }
}

onMounted(loadAgent);
watch(agentId, loadAgent);

function goBack() {
  router.push('/tenant/ai/agents');
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

// ==================== Scope Protection ====================
const isTenantOwned = computed(() => agent.value?.scope === 'all_tenants');

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

function safeJsonParse(str: string): unknown[] | null {
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
const availablePackages = ref<Array<{ label: string; value: number; scope?: string; source_plugin?: string }>>([]);
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

function getScopeTagProps(scope?: string, sourcePlugin?: string): { text: string; color: string } | null {
  if (sourcePlugin) return { text: $t('tenant.ai.skillPackage.scopeTag.plugin'), color: 'purple' };
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
const routingLongContextThreshold = ref(32000);

const visionModelOptions = ref<{ label: string; value: number }[]>([]);
const chatModelOptions = ref<{ label: string; value: number }[]>([]);

async function loadRoutingModelOptions() {
  try {
    const models = await getTenantAIModelsApi();
    visionModelOptions.value = models
      .filter((m) => m.type === 'chat' && m.supports_vision)
      .map((m) => ({ label: `${m.name} (${m.provider_name || '-'})`, value: m.id }));
    chatModelOptions.value = models
      .filter((m) => m.type === 'chat')
      .map((m) => ({ label: `${m.name} (${m.provider_name || '-'})`, value: m.id }));
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
  routingVisionModelId.value = (rc.vision_model_id as number | undefined) ?? undefined;
  routingLongContextModelId.value = (rc.long_context_model_id as number | undefined) ?? undefined;
  routingLongContextThreshold.value = (rc.long_context_threshold as number) ?? 32000;
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
function onTabChange(key: string | number) {
  activeTab.value = String(key);
  if (!agent.value) return;
  switch (key) {
    case 'modelParams': initModelParams(); break;
    case 'chatConfig': initChatConfig(); break;
    case 'skills': { loadBindings(); loadAvailablePackages(); break; }
    case 'quota': initQuota(); break;
    case 'routing': { initRouting(); loadRoutingModelOptions(); break; }
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
        <!-- Header -->
        <div class="flex items-center gap-3">
          <Button size="small" @click="goBack">
            <IconifyIcon icon="lucide:arrow-left" class="mr-1" />
            {{ $t('common.back') }}
          </Button>
          <div class="flex flex-1 items-center gap-3">
            <div
              v-if="agent.avatar"
              class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10"
            >
              <img :src="agent.avatar" class="size-full object-cover" />
            </div>
            <div v-else class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-lg font-bold text-primary">
              {{ (agent.name || '?')[0] }}
            </div>
            <div>
              <h2 class="text-lg font-semibold text-foreground">{{ agent.name }}</h2>
              <p v-if="agent.description" class="text-xs text-muted-foreground">{{ agent.description }}</p>
            </div>
            <Tag :color="getStatusColor(agent.status)" class="ml-2">
              {{ getStatusText(agent.status) }}
            </Tag>
            <Tag v-if="agent.published_version" color="blue">
              v{{ agent.published_version }}
            </Tag>
          </div>
        </div>

        <!-- Scope readonly banner -->
        <div v-if="!isTenantOwned && agent" class="mb-3 flex items-center gap-2 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning">
          <IconifyIcon icon="lucide:lock" class="size-3.5 shrink-0" />
          <span>{{ $t('tenant.ai.agent.readonlyHint') }}</span>
          <Tag :color="getScopeColor(agent.scope)" class="ml-auto !text-[10px]">
            {{ getScopeText(agent.scope) }}
          </Tag>
        </div>

        <!-- Tabs -->
        <Tabs :active-key="activeTab" @change="onTabChange">
          <!-- ========== 概览 Tab ========== -->
          <TabPane key="overview" :tab="$t('tenant.ai.agent.detail.overview')">
            <Card :title="$t('tenant.ai.agent.detail.basicInfo')" class="mb-4">
              <Descriptions :column="2" bordered size="small">
                <DescriptionsItem :label="$t('tenant.ai.agent.name')">
                  {{ agent.name }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('tenant.ai.agent.status')">
                  <Tag :color="getStatusColor(agent.status)">{{ getStatusText(agent.status) }}</Tag>
                </DescriptionsItem>
                <DescriptionsItem :label="$t('tenant.ai.agent.modelName')">
                  {{ agent.model_code || '-' }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('tenant.ai.agent.executionMode')">
                  {{ getExecutionModeText(agent.execution_mode) }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('tenant.ai.agent.description')" :span="2">
                  {{ agent.description || '-' }}
                </DescriptionsItem>
              </Descriptions>
            </Card>

            <Card :title="$t('tenant.ai.agent.systemPrompt')">
              <template #extra>
                <Button
                  v-if="!editingPrompt && isTenantOwned"
                  size="small"
                  type="link"
                  @click="startEditPrompt"
                >
                  <IconifyIcon icon="lucide:pencil" class="mr-1" />
                  {{ $t('common.edit') }}
                </Button>
                <div v-else-if="editingPrompt" class="flex gap-2">
                  <Button size="small" @click="cancelEditPrompt">{{ $t('common.cancel') }}</Button>
                  <Button size="small" type="primary" :loading="saving" @click="savePrompt">{{ $t('common.save') }}</Button>
                </div>
              </template>
              <div v-if="!editingPrompt" class="whitespace-pre-wrap text-sm text-foreground">
                {{ agent.system_prompt || '-' }}
              </div>
              <Textarea
                v-else
                v-model:value="promptDraft"
                :rows="8"
                class="w-full"
              />
            </Card>
          </TabPane>

          <!-- ========== 模型参数 Tab ========== -->
          <TabPane key="modelParams" :tab="$t('tenant.ai.agent.detail.modelParams')">
            <Card>
              <div class="grid max-w-lg grid-cols-1 gap-4">
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.temperature') }}</label>
                  <InputNumber v-model:value="modelTemp" :min="0" :max="2" :step="0.1" :disabled="!isTenantOwned" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.maxTokens') }}</label>
                  <InputNumber v-model:value="modelMaxTokens" :min="1" :max="128000" :disabled="!isTenantOwned" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.topP') }}</label>
                  <InputNumber v-model:value="modelTopP" :min="0" :max="1" :step="0.1" :disabled="!isTenantOwned" class="w-full" />
                </div>
                <div v-if="isTenantOwned" class="pt-2">
                  <Button type="primary" :loading="saving" @click="saveModelParams">
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </Card>
          </TabPane>

          <!-- ========== 对话配置 Tab ========== -->
          <TabPane key="chatConfig" :tab="$t('tenant.ai.agent.detail.chatConfig')">
            <div class="flex flex-col gap-4">
              <Card :title="$t('tenant.ai.agent.welcomeMessage')">
                <Textarea v-model:value="chatWelcome" :rows="3" :disabled="!isTenantOwned" class="w-full" />
              </Card>
              <Card :title="$t('tenant.ai.agent.suggestedQuestions')">
                <Textarea v-model:value="chatSuggestions" :rows="4" :disabled="!isTenantOwned" class="w-full font-mono text-xs" />
                <p class="mt-1 text-xs text-muted-foreground">JSON</p>
              </Card>
              <Card :title="$t('tenant.ai.agent.inputVariables.title')">
                <Textarea v-model:value="chatInputVars" :rows="4" :disabled="!isTenantOwned" class="w-full font-mono text-xs" />
                <p class="mt-1 text-xs text-muted-foreground">JSON</p>
              </Card>
              <Card :title="$t('tenant.ai.agent.contextConfig.title')">
                <div class="grid max-w-lg grid-cols-2 gap-4">
                  <div>
                    <label class="mb-1 block text-sm">{{ $t('tenant.ai.agent.contextConfig.maxHistoryMessages') }}</label>
                    <InputNumber v-model:value="chatContextMessages" :min="0" :disabled="!isTenantOwned" class="w-full" />
                  </div>
                  <div>
                    <label class="mb-1 block text-sm">{{ $t('tenant.ai.agent.contextConfig.maxHistoryTokens') }}</label>
                    <InputNumber v-model:value="chatContextTokens" :min="0" :disabled="!isTenantOwned" class="w-full" />
                  </div>
                </div>
              </Card>
              <div v-if="isTenantOwned">
                <Button type="primary" :loading="saving" @click="saveChatConfig">
                  {{ $t('common.save') }}
                </Button>
              </div>
            </div>
          </TabPane>

          <!-- ========== 技能绑定 Tab ========== -->
          <TabPane key="skills" :tab="$t('tenant.ai.agent.detail.skillBindings')">
            <Spin :spinning="bindingsLoading">
              <div class="flex flex-col gap-4">
                <!-- Add binding (only for tenant-owned agents) -->
                <Card v-if="isTenantOwned" size="small">
                  <div class="flex items-center gap-3">
                    <ASelect
                      v-model:value="selectedNewPkg"
                      :options="unboundPackages"
                      :placeholder="$t('tenant.ai.agent.placeholder.selectSkillPackages')"
                      show-search
                      option-filter-prop="label"
                      class="flex-1"
                    >
                      <template #option="{ label: optLabel, value: optValue }">
                        <div class="flex items-center justify-between gap-2">
                          <span>{{ optLabel }}</span>
                          <Tag
                            v-if="getScopeTagProps(
                              availablePackages.find(p => p.value === optValue)?.scope,
                              availablePackages.find(p => p.value === optValue)?.source_plugin,
                            )"
                            :color="getScopeTagProps(
                              availablePackages.find(p => p.value === optValue)?.scope,
                              availablePackages.find(p => p.value === optValue)?.source_plugin,
                            )!.color"
                            class="mr-0 text-xs"
                          >
                            {{ getScopeTagProps(
                              availablePackages.find(p => p.value === optValue)?.scope,
                              availablePackages.find(p => p.value === optValue)?.source_plugin,
                            )!.text }}
                          </Tag>
                        </div>
                      </template>
                    </ASelect>
                    <Button type="primary" :disabled="!selectedNewPkg" @click="bindPackage">
                      <IconifyIcon icon="lucide:plus" class="mr-1" />
                      {{ $t('common.add') }}
                    </Button>
                  </div>
                </Card>

                <!-- Auto-bind packages (locked) -->
                <Card v-for="b in bindings.filter(x => x.is_auto_bound)" :key="`auto-${b.package_id}`" size="small" class="!border-primary/20 !bg-primary/5">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <IconifyIcon icon="lucide:lock" class="size-4 text-primary/60" />
                      <span class="font-medium">{{ b.package_name || `#${b.package_id}` }}</span>
                      <Tag v-if="b.package_is_system" color="red" class="!text-[10px]">
                        {{ $t('tenant.ai.skillPackage.system') }}
                      </Tag>
                      <Tag v-if="b.package_scope" :color="getScopeColor(b.package_scope)" class="!text-[10px]">
                        {{ getScopeText(b.package_scope) }}
                      </Tag>
                    </div>
                    <Tag color="blue" class="!text-[10px]">
                      <IconifyIcon icon="lucide:zap" class="mr-0.5 inline size-3" />
                      {{ $t('common.bindMode.auto') }}
                    </Tag>
                  </div>
                </Card>

                <!-- Manual-bind packages -->
                <Card v-for="b in bindings.filter(x => !x.is_auto_bound)" :key="`manual-${b.package_id}`" size="small">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <div class="flex size-8 items-center justify-center rounded bg-primary/10 text-sm font-bold text-primary">
                        {{ (b.package_name || '?')[0] }}
                      </div>
                      <div>
                        <span class="font-medium">{{ b.package_name || `#${b.package_id}` }}</span>
                        <Tag
                          v-if="b.package_scope"
                          :color="getScopeColor(b.package_scope)"
                          class="ml-2 !text-[10px]"
                        >
                          {{ getScopeText(b.package_scope) }}
                        </Tag>
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <Tag :color="b.consent_mode === 'auto' ? 'green' : b.consent_mode === 'ask' ? 'orange' : 'red'">
                        {{ $t(`tenant.ai.agent.consentModeOptions.${b.consent_mode}`) }}
                      </Tag>
                      <Button v-if="isTenantOwned" size="small" danger @click="unbindPkg(b.package_id)">
                        <IconifyIcon icon="lucide:x" />
                      </Button>
                    </div>
                  </div>
                </Card>

                <Empty v-if="bindings.length === 0 && !bindingsLoading" />
              </div>
            </Spin>
          </TabPane>

          <!-- ========== 配额管理 Tab ========== -->
          <TabPane key="quota" :tab="$t('tenant.ai.agent.detail.quota')">
            <Card>
              <p class="mb-4 text-xs text-muted-foreground">{{ $t('tenant.ai.agent.detail.noQuotaLimit') }}</p>
              <div class="grid max-w-lg grid-cols-1 gap-4">
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.conversationsPerDay') }}</label>
                  <InputNumber v-model:value="quotaConversationsPerDay" :min="0" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.tokensPerDay') }}</label>
                  <InputNumber v-model:value="quotaTokensPerDay" :min="0" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.tokensPerMonth') }}</label>
                  <InputNumber v-model:value="quotaTokensPerMonth" :min="0" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.maxTurnsPerConversation') }}</label>
                  <InputNumber v-model:value="quotaMaxTurns" :min="0" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.maxConcurrent') }}</label>
                  <InputNumber v-model:value="quotaMaxConcurrent" :min="0" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.quotaConfig.userConversationsPerDay') }}</label>
                  <InputNumber v-model:value="quotaUserConversationsPerDay" :min="0" class="w-full" />
                </div>
                <div class="pt-2">
                  <Button type="primary" :loading="saving" @click="saveQuota">
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </Card>
          </TabPane>

          <!-- ========== 智能路由 Tab ========== -->
          <TabPane key="routing" :tab="$t('tenant.ai.agent.detail.routing')">
            <Card>
              <p class="mb-4 text-xs text-muted-foreground">{{ $t('tenant.ai.agent.routing.description') }}</p>
              <div class="grid max-w-xl grid-cols-1 gap-5">
                <!-- 启用智能路由 -->
                <div class="flex items-center gap-3">
                  <label class="text-sm font-medium">{{ $t('tenant.ai.agent.routing.enableRouting') }}</label>
                  <Switch
                    v-model:checked="routingEnabled"
                    :disabled="!isTenantOwned"
                  />
                </div>

                <!-- 成本上限 Tier -->
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.routing.maxTier') }}</label>
                  <ASelect
                    v-model:value="routingMaxTier"
                    :options="tierOptions"
                    class="w-full"
                    :disabled="!routingEnabled || !isTenantOwned"
                    :allow-clear="true"
                    :placeholder="$t('tenant.ai.agent.routing.noLimit')"
                  />
                  <p class="mt-1 text-xs text-muted-foreground">{{ $t('tenant.ai.agent.routing.maxTierHelp') }}</p>
                </div>

                <!-- Vision 专用模型 -->
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.routing.visionModel') }}</label>
                  <ASelect
                    v-model:value="routingVisionModelId"
                    :options="visionModelOptions"
                    class="w-full"
                    :disabled="!routingEnabled || !isTenantOwned"
                    :allow-clear="true"
                    :placeholder="$t('tenant.ai.agent.routing.autoSelect')"
                  />
                </div>

                <!-- 长上下文模型 -->
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.routing.longContextModel') }}</label>
                  <ASelect
                    v-model:value="routingLongContextModelId"
                    :options="chatModelOptions"
                    class="w-full"
                    :disabled="!routingEnabled || !isTenantOwned"
                    :allow-clear="true"
                    :placeholder="$t('tenant.ai.agent.routing.autoSelect')"
                  />
                </div>

                <!-- 长上下文触发阈值 -->
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.routing.longContextThreshold') }}</label>
                  <InputNumber
                    v-model:value="routingLongContextThreshold"
                    :min="1000"
                    :step="1000"
                    class="w-full"
                    :disabled="!routingEnabled || !isTenantOwned"
                  />
                  <p class="mt-1 text-xs text-muted-foreground">{{ $t('tenant.ai.agent.routing.longContextThresholdHelp') }}</p>
                </div>

                <div v-if="isTenantOwned" class="pt-2">
                  <Button type="primary" :loading="saving" @click="saveRouting">
                    {{ $t('common.save') }}
                  </Button>
                </div>
              </div>
            </Card>
          </TabPane>
        </Tabs>
      </div>
    </Spin>
  </Page>
</template>
