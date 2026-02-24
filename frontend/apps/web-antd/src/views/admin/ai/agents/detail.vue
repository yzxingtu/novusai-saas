<script lang="ts" setup>
defineOptions({ name: 'AdminAgentDetail' });
/**
 * 管理端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 * 额外显示 scope/租户信息，系统智能体核心字段保护。
 */
import type { AIAgentInfo, AIAgentSkillBindingInfo } from '#/api/admin/ai';

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
  batchBindAIAgentSkillsApi,
  getAIAgentDetailApi,
  getAIAgentSkillsApi,
  updateAIAgentApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import type { PkgOption } from './data';

import {
  getExecutionModeText,
  getStatusText,
  getScopeColor,
  getPackageSelectOptions,
} from './data';

// ==================== Route ====================
const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

// ==================== State ====================
const loading = ref(false);
const saving = ref(false);
const agent = ref<AIAgentInfo | null>(null);
const activeTab = ref('overview');

// ==================== Load ====================
async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAIAgentDetailApi(agentId.value);
  } catch {
    message.error($t('common.loadFailed'));
  } finally {
    loading.value = false;
  }
}

onMounted(loadAgent);
watch(agentId, loadAgent);

function goBack() {
  router.push('/admin/ai/agents');
}

// ==================== Generic Save ====================
async function saveFields(fields: Record<string, unknown>) {
  if (!agent.value) return;
  saving.value = true;
  try {
    agent.value = await updateAIAgentApi(agentId.value, fields);
    message.success($t('admin.ai.agent.detail.saveSuccess'));
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

function initChatConfig() {
  if (!agent.value) return;
  chatWelcome.value = agent.value.welcome_message || '';
  chatSuggestions.value = Array.isArray(agent.value.suggested_questions)
    ? agent.value.suggested_questions.join('\n')
    : '';
}

async function saveChatConfig() {
  const sqArray = chatSuggestions.value
    .split('\n')
    .map((s: string) => s.trim())
    .filter((s: string) => s.length > 0);
  await saveFields({
    welcome_message: chatWelcome.value || null,
    suggested_questions: sqArray.length > 0 ? sqArray : null,
  });
}

// ==================== Skill Bindings Tab ====================
const bindings = ref<AIAgentSkillBindingInfo[]>([]);
const bindingsLoading = ref(false);
const packageOptions = ref<PkgOption[]>([]);
const selectedNewPkg = ref<number | undefined>();

async function loadBindings() {
  bindingsLoading.value = true;
  try {
    bindings.value = await getAIAgentSkillsApi(agentId.value);
  } catch {
    bindings.value = [];
  } finally {
    bindingsLoading.value = false;
  }
}

async function loadPackageOptions() {
  try {
    packageOptions.value = await getPackageSelectOptions();
  } catch {
    packageOptions.value = [];
  }
}

const unboundPackages = computed(() => {
  const boundIds = new Set(bindings.value.map((b) => b.package_id));
  return packageOptions.value.filter((p) => !boundIds.has(p.value));
});

async function bindPackage() {
  if (!selectedNewPkg.value) return;
  const currentIds = bindings.value.map((b) => b.package_id);
  currentIds.push(selectedNewPkg.value);
  try {
    await batchBindAIAgentSkillsApi(agentId.value, { package_ids: currentIds });
    selectedNewPkg.value = undefined;
    await loadBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch {
    message.error($t('common.saveFailed'));
  }
}

function getScopeTagProps(scope?: string, sourcePlugin?: string): { text: string; color: string } | null {
  if (sourcePlugin) return { text: $t('admin.ai.skillPackage.sourcePlugin'), color: 'purple' };
  switch (scope) {
    case 'global': return { text: $t('admin.ai.agent.scope.global'), color: 'blue' };
    case 'admin': return { text: $t('admin.ai.agent.scope.admin'), color: 'orange' };
    case 'tenant': return { text: $t('admin.ai.agent.scope.tenant'), color: 'green' };
    default: return null;
  }
}

function getStatusColor(status: string | undefined): string {
  switch (status) {
    case 'published': return 'green';
    case 'draft': return 'default';
    case 'disabled': return 'red';
    default: return 'default';
  }
}

// ==================== Tab Change ====================
function onTabChange(key: string | number) {
  activeTab.value = String(key);
  if (!agent.value) return;
  switch (key) {
    case 'modelParams': initModelParams(); break;
    case 'chatConfig': initChatConfig(); break;
    case 'skills': { loadBindings(); loadPackageOptions(); break; }
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
            <div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-lg font-bold text-primary">
              {{ (agent.name || '?')[0] }}
            </div>
            <div>
              <h2 class="text-lg font-semibold text-foreground">{{ agent.name }}</h2>
              <p v-if="agent.description" class="text-xs text-muted-foreground">{{ agent.description }}</p>
            </div>
            <Tag :color="getStatusColor(agent.status)">
              {{ getStatusText(agent.status) }}
            </Tag>
            <Tag v-if="agent.is_system" color="purple">
              {{ $t('admin.ai.agent.system') }}
            </Tag>
            <Tag :color="getScopeColor(agent.scope)">
              {{ agent.scope }}
            </Tag>
          </div>
        </div>

        <!-- Tabs -->
        <Tabs :active-key="activeTab" @change="onTabChange">
          <!-- ========== 概览 Tab ========== -->
          <TabPane key="overview" :tab="$t('admin.ai.agent.detail.overview')">
            <Card :title="$t('admin.ai.agent.detail.basicInfo')" class="mb-4">
              <Descriptions :column="2" bordered size="small">
                <DescriptionsItem :label="$t('admin.ai.agent.name')">
                  {{ agent.name }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('admin.ai.agent.status')">
                  <Tag :color="getStatusColor(agent.status)">{{ getStatusText(agent.status) }}</Tag>
                </DescriptionsItem>
                <DescriptionsItem :label="$t('admin.ai.agent.modelName')">
                  {{ agent.model_name || '-' }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('admin.ai.agent.executionMode')">
                  {{ getExecutionModeText(agent.execution_mode) }}
                </DescriptionsItem>
                <DescriptionsItem :label="$t('admin.ai.agent.scopeLabel')">
                  <Tag :color="getScopeColor(agent.scope)">{{ agent.scope }}</Tag>
                </DescriptionsItem>
                <DescriptionsItem :label="$t('admin.ai.agent.description')" :span="2">
                  {{ agent.description || '-' }}
                </DescriptionsItem>
              </Descriptions>
            </Card>

            <Card :title="$t('admin.ai.agent.systemPrompt')">
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
                  <Button size="small" @click="editingPrompt = false">{{ $t('common.cancel') }}</Button>
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
          <TabPane key="modelParams" :tab="$t('admin.ai.agent.detail.modelParams')">
            <Card>
              <div class="grid max-w-lg grid-cols-1 gap-4">
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('admin.ai.agent.temperature') }}</label>
                  <InputNumber v-model:value="modelTemp" :min="0" :max="2" :step="0.1" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('admin.ai.agent.maxTokens') }}</label>
                  <InputNumber v-model:value="modelMaxTokens" :min="1" :max="128000" class="w-full" />
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium">{{ $t('admin.ai.agent.topP') }}</label>
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
          <TabPane key="chatConfig" :tab="$t('admin.ai.agent.detail.chatConfig')">
            <div class="flex flex-col gap-4">
              <Card :title="$t('admin.ai.agent.welcomeMessage')">
                <Textarea v-model:value="chatWelcome" :rows="3" class="w-full" />
              </Card>
              <Card :title="$t('admin.ai.agent.suggestedQuestions')">
                <Textarea v-model:value="chatSuggestions" :rows="4" class="w-full" />
                <p class="mt-1 text-xs text-muted-foreground">{{ $t('admin.ai.agent.placeholder.inputSuggestedQuestions') }}</p>
              </Card>
              <div>
                <Button type="primary" :loading="saving" @click="saveChatConfig">
                  {{ $t('common.save') }}
                </Button>
              </div>
            </div>
          </TabPane>

          <!-- ========== 技能绑定 Tab ========== -->
          <TabPane key="skills" :tab="$t('admin.ai.agent.detail.skillBindings')">
            <Spin :spinning="bindingsLoading">
              <div class="flex flex-col gap-4">
                <!-- Add binding -->
                <Card size="small">
                  <div class="flex items-center gap-3">
                    <ASelect
                      v-model:value="selectedNewPkg"
                      :options="unboundPackages"
                      :placeholder="$t('admin.ai.agent.placeholder.selectSkillPackages')"
                      show-search
                      option-filter-prop="label"
                      class="flex-1"
                    >
                      <template #option="{ label: optLabel, value: optValue }">
                        <div class="flex items-center justify-between gap-2">
                          <span>{{ optLabel }}</span>
                          <Tag
                            v-if="getScopeTagProps(
                              packageOptions.find(p => p.value === optValue)?.scope,
                              packageOptions.find(p => p.value === optValue)?.sourcePlugin,
                            )"
                            :color="getScopeTagProps(
                              packageOptions.find(p => p.value === optValue)?.scope,
                              packageOptions.find(p => p.value === optValue)?.sourcePlugin,
                            )!.color"
                            class="mr-0 text-xs"
                          >
                            {{ getScopeTagProps(
                              packageOptions.find(p => p.value === optValue)?.scope,
                              packageOptions.find(p => p.value === optValue)?.sourcePlugin,
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
                <Card v-for="b in bindings" :key="b.package_id" size="small">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <div class="flex size-8 items-center justify-center rounded bg-primary/10 text-sm font-bold text-primary">
                        {{ (b.package_name || '?')[0] }}
                      </div>
                      <span class="font-medium">{{ b.package_name || `#${b.package_id}` }}</span>
                    </div>
                    <Tag :color="b.consent_mode === 'auto' ? 'green' : b.consent_mode === 'ask' ? 'orange' : 'red'">
                      {{ b.consent_mode }}
                    </Tag>
                  </div>
                </Card>

                <Empty v-if="bindings.length === 0 && !bindingsLoading" />
              </div>
            </Spin>
          </TabPane>
        </Tabs>
      </div>
    </Spin>
  </Page>
</template>
