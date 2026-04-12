<script lang="ts" setup>
/**
 * 管理端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 配额管理
 * 显示分发模式/归属等元信息，系统智能体核心字段保护。
 */
import type { AIAgentInfo } from '#/api/admin/ai';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Empty, Spin, TabPane, Tabs, message } from 'ant-design-vue';

import { getAIAgentDetailApi, updateAIAgentApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

import AccessConfigDrawer from './modules/AccessConfig.vue';
import AgentChatConfigTab from './modules/detail/AgentChatConfigTab.vue';
import AgentDetailHeader from './modules/detail/AgentDetailHeader.vue';
import AgentKnowledgeBaseTab from './modules/detail/AgentKnowledgeBaseTab.vue';
import AgentModelParamsTab from './modules/detail/AgentModelParamsTab.vue';
import AgentOverviewTab from './modules/detail/AgentOverviewTab.vue';
import AgentQuotaTab from './modules/detail/AgentQuotaTab.vue';
import AgentRagConfigTab from './modules/detail/AgentRagConfigTab.vue';
import AgentRoutingTab from './modules/detail/AgentRoutingTab.vue';
import AgentSkillBindingsTab from './modules/detail/AgentSkillBindingsTab.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'AdminAgentDetail' });

const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

const loading = ref(false);
const saving = ref(false);
const agent = ref<AIAgentInfo | null>(null);
const activeTab = ref('overview');

async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAIAgentDetailApi(agentId.value);
  } catch (error) {
    showRequestError(error, 'common.loadFailed');
  } finally {
    loading.value = false;
  }
}

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

onMounted(async () => {
  await loadAgent();
  const tab = route.query.tab as string | undefined;
  if (tab) {
    activeTab.value = tab;
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
}

function onTabChange(key: number | string) {
  activeTab.value = String(key);
}

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
</script>

<template>
  <Page auto-content-height>
    <Spin :spinning="loading">
      <div v-if="!loading && !agent" class="py-20">
        <Empty :description="$t('common.noData')" />
      </div>

      <div v-if="agent" class="flex flex-col gap-4">
        <AgentDetailHeader
          :agent="agent"
          :is-routing-enabled="isRoutingEnabled"
          :on-back="goBack"
          :on-open-version-history="openVersionHistory"
          :on-open-access-config="openAccessConfig"
          :on-jump-to-routing-tab="jumpToRoutingTab"
          :on-save-fields="saveFields"
        />

        <div class="rounded-xl border bg-card">
          <Tabs :active-key="activeTab" class="px-2 pt-1" @change="onTabChange">
            <TabPane key="overview">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:layout-dashboard" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.overview') }}
                </span>
              </template>
              <AgentOverviewTab
                :agent="agent"
                :agent-id="agentId"
                :saving="saving"
                :active="activeTab === 'overview'"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <TabPane key="modelParams">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:sliders" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.modelParams') }}
                </span>
              </template>
              <AgentModelParamsTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'modelParams'"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <TabPane key="chatConfig">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:message-circle" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.chatConfig') }}
                </span>
              </template>
              <AgentChatConfigTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'chatConfig'"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <TabPane key="skills">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.skillBindings') }}
                </span>
              </template>
              <AgentSkillBindingsTab
                :agent-id="agentId"
                :active="activeTab === 'skills'"
              />
            </TabPane>

            <TabPane key="rag">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:search" class="size-3.5" />
                  {{ $t('admin.ai.agent.knowledgeBase.title') }}
                </span>
              </template>
              <AgentRagConfigTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'rag'"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <TabPane key="knowledgeBases">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:library" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.knowledgeBases') }}
                </span>
              </template>
              <AgentKnowledgeBaseTab
                :agent="agent"
                :agent-id="agentId"
                :active="activeTab === 'knowledgeBases'"
              />
            </TabPane>

            <TabPane key="quota">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:gauge" class="size-3.5" />
                  {{ $t('admin.ai.agent.detail.quota') }}
                </span>
              </template>
              <AgentQuotaTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'quota'"
                :on-save-fields="saveFields"
              />
            </TabPane>

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
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'routing'"
                :on-save-fields="saveFields"
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
