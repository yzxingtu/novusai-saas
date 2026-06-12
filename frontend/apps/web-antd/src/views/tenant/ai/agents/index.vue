<script lang="ts" setup>
import type { VNodeRef } from 'vue';

import { Page } from '@vben/common-ui';

import { Alert, Pagination } from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';

import { useAgentListPage } from './composables/use-agent-list-page';
import AgentForm from './modules/AgentForm.vue';
import AgentListGrid from './modules/AgentListGrid.vue';
import AgentListPublishModal from './modules/AgentListPublishModal.vue';
import AgentListToolbar from './modules/AgentListToolbar.vue';
import TenantAgentSetupEmptyState from './modules/TenantAgentSetupEmptyState.vue';

defineOptions({ name: 'TenantAgentList' });

const page = useAgentListPage();
const VersionHistoryDrawer = page.VersionHistoryDrawer;
const agentFormRef = page.agentFormRef;
const canCreateAgent = page.canCreateAgent;
const currentPage = page.currentPage;
const heroChips = page.heroChips;
const heroMetrics = page.heroMetrics;
const hasActiveFilters = page.hasActiveFilters;
const list = page.list;
const loading = page.loading;
const modelCheckLoading = page.modelCheckLoading;
const pageSize = page.pageSize;
const publishLoading = page.publishLoading;
const filterStatus = page.filterStatus;
const publishChangeLog = page.publishChangeLog;
const publishModalOpen = page.publishModalOpen;
const recycleBinRef = page.recycleBinRef;
const recycleBinCount = page.recycleBinCount;
const searchKeyword = page.searchKeyword;
const setupState = page.setupState;
const showSetupNotice = page.showSetupNotice;
const showSetupState = page.showSetupState;
const total = page.total;

const setAgentFormRef: VNodeRef = (value) => {
  agentFormRef.value = value as InstanceType<typeof AgentForm> | undefined;
};

const setRecycleBinRef: VNodeRef = (value) => {
  recycleBinRef.value = value as null | {
    deletedCount: number;
    open: () => void;
  };
};
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AgentForm :ref="setAgentFormRef" @success="page.loadList" />
    <VersionHistoryDrawer @success="page.loadList" />
    <RecycleBinDrawer
      :ref="setRecycleBinRef"
      resource="/tenant/ai/agents"
      @restored="page.loadList"
    />

    <AgentListPublishModal
      v-model:change-log="publishChangeLog"
      v-model:open="publishModalOpen"
      :confirm-loading="publishLoading"
      @confirm="page.onPublishConfirm"
    />

    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('tenant.ai.agent.pageDesc')"
      icon="lucide:bot"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('tenant.ai.agent.title')"
    />

    <Alert
      v-if="showSetupNotice"
      :description="$t('tenant.ai.agent.setup.missingModelDesc')"
      :message="$t('tenant.ai.agent.setup.missingModelTitle')"
      show-icon
      type="warning"
    />

    <AgentListToolbar
      v-if="!showSetupState"
      v-model:filter-status="filterStatus"
      v-model:search-keyword="searchKeyword"
      :can-create-agent="canCreateAgent"
      :has-active-filters="hasActiveFilters"
      :recycle-bin-count="recycleBinCount"
      @clear-filters="page.onClearFilters"
      @create-agent="page.onCreateAgent"
      @open-recycle-bin="page.openRecycleBin"
      @search="page.doSearch"
    />

    <TenantAgentSetupEmptyState
      v-if="showSetupState"
      :loading="modelCheckLoading"
      :state="setupState"
      @refresh="page.refreshModelStatus"
    />

    <AgentListGrid
      v-else
      :agents="list"
      :can-create-agent="canCreateAgent"
      :loading="loading"
      @create-agent="page.onCreateAgent"
      @delete="page.handleMenuAction('delete', $event)"
      @edit="page.onEditAgent"
      @publish="page.onPublish"
      @versions="page.onVersions"
    />

    <div v-if="!showSetupState && total > pageSize" class="flex justify-end">
      <Pagination
        :current="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-size-options="['12', '24', '48']"
        :show-size-changer="false"
        size="small"
        @change="page.onPageChange"
      />
    </div>
  </Page>
</template>
