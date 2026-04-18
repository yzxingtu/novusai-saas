<script lang="ts" setup>
/**
 * 企业端智能体详情页
 *
 * Tab 面板：概览 / 模型参数 / 对话配置 / 技能绑定 / 知识库检索 / 知识库绑定 / 配额管理 / 智能路由
 */
import type { AgentInfo } from '#/api/tenant/agents';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Empty, message, Spin, TabPane, Tabs } from 'ant-design-vue';

import { getAgentDetailApi, updateAgentApi } from '#/api/tenant/agents';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

import AccessConfigDrawer from './modules/AccessConfigDrawer.vue';
import AgentChatConfigTab from './modules/detail/AgentChatConfigTab.vue';
import AgentDetailHeader from './modules/detail/AgentDetailHeader.vue';
import AgentKnowledgeBaseTab from './modules/detail/AgentKnowledgeBaseTab.vue';
import AgentModelParamsTab from './modules/detail/AgentModelParamsTab.vue';
import AgentOverviewTab from './modules/detail/AgentOverviewTab.vue';
import AgentQuotaTab from './modules/detail/AgentQuotaTab.vue';
import AgentRagConfigTab from './modules/detail/AgentRagConfigTab.vue';
import AgentRoutingConfigTab from './modules/detail/AgentRoutingConfigTab.vue';
import AgentSkillBindingsTab from './modules/detail/AgentSkillBindingsTab.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'TenantAgentDetail' });

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

// ==================== Route / 路由 ====================
const route = useRoute();
const router = useRouter();
const agentId = computed(() => Number(route.params.id));

// ==================== State / 状态 ====================
const loading = ref(false);
const saving = ref(false);
const agent = ref<AgentInfo | null>(null);
const activeTab = ref('overview');

// ==================== Load / 加载 ====================
async function loadAgent() {
  loading.value = true;
  try {
    agent.value = await getAgentDetailApi(agentId.value);
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

// ==================== Generic Save / 通用保存 ====================
async function saveFields(fields: Record<string, unknown>) {
  if (!agent.value) return;
  saving.value = true;
  try {
    agent.value = await updateAgentApi(agentId.value, fields);
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  } finally {
    saving.value = false;
  }
}

// ==================== Scope Protection / 作用域保护 ====================
const resolvedOwnerType = computed(() => {
  const ownerType = agent.value?.owner_type;
  if (ownerType === 'platform' || ownerType === 'tenant') {
    return ownerType;
  }
  return agent.value?.owner_tenant_id === null ||
    agent.value?.owner_tenant_id === undefined
    ? 'platform'
    : 'tenant';
});

const isTenantOwned = computed(() => resolvedOwnerType.value === 'tenant');
/** 平台下发智能体：可追加本企业知识库，不可改平台全局绑定 / Platform agent: tenant KB overlay */
const isPlatformAssignedAgent = computed(
  () => resolvedOwnerType.value === 'platform',
);
const canManageKnowledgeBases = computed(
  () => isTenantOwned.value || isPlatformAssignedAgent.value,
);

// ==================== Tab Change / 切换页签 ====================
function onTabChange(key: number | string) {
  activeTab.value = String(key);
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
        <AgentDetailHeader
          :agent="agent"
          :is-tenant-owned="isTenantOwned"
          :is-routing-enabled="isRoutingEnabled"
          :on-back="goBack"
          :on-open-version-history="openVersionHistory"
          :on-open-access-config="openAccessConfig"
          :on-jump-to-routing-tab="jumpToRoutingTab"
          :on-save-fields="saveFields"
        />

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
              <AgentOverviewTab
                :agent="agent"
                :agent-id="agentId"
                :saving="saving"
                :active="activeTab === 'overview'"
                :is-tenant-owned="isTenantOwned"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <!-- ========== 模型参数 ========== -->
            <TabPane key="modelParams">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:sliders" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.modelParams') }}
                </span>
              </template>
              <AgentModelParamsTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'modelParams'"
                :is-tenant-owned="isTenantOwned"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <!-- ========== 对话配置 ========== -->
            <TabPane key="chatConfig">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:message-circle" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.chatConfig') }}
                </span>
              </template>
              <AgentChatConfigTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'chatConfig'"
                :is-tenant-owned="isTenantOwned"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <!-- ========== 技能绑定 ========== -->
            <TabPane key="skills">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.skillBindings') }}
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
                  {{ $t('tenant.ai.agent.knowledgeBase.title') }}
                </span>
              </template>
              <AgentRagConfigTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'rag'"
                :is-tenant-owned="isTenantOwned"
                :on-save-fields="saveFields"
              />
            </TabPane>

            <!-- ========== 知识库绑定 ========== -->
            <TabPane key="knowledgeBases">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:library" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.knowledgeBases') }}
                </span>
              </template>
              <AgentKnowledgeBaseTab
                :agent-id="agentId"
                :active="activeTab === 'knowledgeBases'"
                :is-tenant-owned="isTenantOwned"
                :is-platform-assigned-agent="isPlatformAssignedAgent"
                :can-manage-knowledge-bases="canManageKnowledgeBases"
              />
            </TabPane>

            <!-- ========== 配额管理 ========== -->
            <TabPane key="quota">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:gauge" class="size-3.5" />
                  {{ $t('tenant.ai.agent.detail.quota') }}
                </span>
              </template>
              <AgentQuotaTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'quota'"
                :is-tenant-owned="isTenantOwned"
                :on-save-fields="saveFields"
              />
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
              <AgentRoutingConfigTab
                :agent="agent"
                :saving="saving"
                :active="activeTab === 'routing'"
                :is-tenant-owned="isTenantOwned"
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
