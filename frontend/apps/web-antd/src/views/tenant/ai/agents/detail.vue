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
import { $t } from '#/locales';

import {
  getExecutionModeText,
  getStatusText,
  getStatusColor,
} from './data';

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
  switch (scope) {
    case 'global': return { text: $t('tenant.ai.skillPackage.scope_options.global'), color: 'blue' };
    case 'admin': return { text: $t('tenant.ai.skillPackage.scope_options.admin'), color: 'orange' };
    default: return null;
  }
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

// ==================== Tab Change: Init ====================
function onTabChange(key: string | number) {
  activeTab.value = String(key);
  if (!agent.value) return;
  switch (key) {
    case 'modelParams': initModelParams(); break;
    case 'chatConfig': initChatConfig(); break;
    case 'skills': { loadBindings(); loadAvailablePackages(); break; }
    case 'quota': initQuota(); break;
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
                  v-if="!editingPrompt"
                  size="small"
                  type="link"
                  @click="startEditPrompt"
                >
                  <IconifyIcon icon="lucide:pencil" class="mr-1" />
                  {{ $t('common.edit') }}
                </Button>
                <div v-else class="flex gap-2">
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
                  <InputNumber v-model:value="modelTemp" :min="0" :max="2" :step="0.1" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.maxTokens') }}</label>
                  <InputNumber v-model:value="modelMaxTokens" :min="1" :max="128000" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('tenant.ai.agent.topP') }}</label>
                  <InputNumber v-model:value="modelTopP" :min="0" :max="1" :step="0.1" class="w-full" />
                </div>
                <div class="pt-2">
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
                <Textarea v-model:value="chatWelcome" :rows="3" class="w-full" />
              </Card>
              <Card :title="$t('tenant.ai.agent.suggestedQuestions')">
                <Textarea v-model:value="chatSuggestions" :rows="4" class="w-full font-mono text-xs" />
                <p class="mt-1 text-xs text-muted-foreground">JSON</p>
              </Card>
              <Card :title="$t('tenant.ai.agent.inputVariables.title')">
                <Textarea v-model:value="chatInputVars" :rows="4" class="w-full font-mono text-xs" />
                <p class="mt-1 text-xs text-muted-foreground">JSON</p>
              </Card>
              <Card :title="$t('tenant.ai.agent.contextConfig.title')">
                <div class="grid max-w-lg grid-cols-2 gap-4">
                  <div>
                    <label class="mb-1 block text-sm">{{ $t('tenant.ai.agent.contextConfig.maxHistoryMessages') }}</label>
                    <InputNumber v-model:value="chatContextMessages" :min="0" class="w-full" />
                  </div>
                  <div>
                    <label class="mb-1 block text-sm">{{ $t('tenant.ai.agent.contextConfig.maxHistoryTokens') }}</label>
                    <InputNumber v-model:value="chatContextTokens" :min="0" class="w-full" />
                  </div>
                </div>
              </Card>
              <div>
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
                <!-- Add binding -->
                <Card size="small">
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

                <!-- Bound packages list -->
                <Card v-for="b in bindings" :key="b.id" size="small">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <div class="flex size-8 items-center justify-center rounded bg-primary/10 text-sm font-bold text-primary">
                        {{ (b.package?.name || '?')[0] }}
                      </div>
                      <div>
                        <span class="font-medium">{{ b.package?.name || `#${b.package_id}` }}</span>
                        <Tag
                          v-if="getScopeTagProps(b.package?.scope)"
                          :color="getScopeTagProps(b.package?.scope)!.color"
                          class="ml-2 text-xs"
                        >
                          {{ getScopeTagProps(b.package?.scope)!.text }}
                        </Tag>
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <Tag :color="b.consent_mode === 'auto' ? 'green' : b.consent_mode === 'ask' ? 'orange' : 'red'">
                        {{ b.consent_mode }}
                      </Tag>
                      <Button size="small" danger @click="unbindPkg(b.package_id)">
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
        </Tabs>
      </div>
    </Spin>
  </Page>
</template>
