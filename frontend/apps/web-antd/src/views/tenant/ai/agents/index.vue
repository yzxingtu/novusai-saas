<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import { Pagination } from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';

import { useAgentListPage } from './composables/use-agent-list-page';
import AgentListGrid from './modules/AgentListGrid.vue';
import AgentListPublishModal from './modules/AgentListPublishModal.vue';
import AgentListToolbar from './modules/AgentListToolbar.vue';
import AgentForm from './modules/AgentForm.vue';

defineOptions({ name: 'TenantAgentList' });

const page = useAgentListPage();
const VersionHistoryDrawer = page.VersionHistoryDrawer;
const agentFormRef = page.agentFormRef;
const filterStatus = page.filterStatus;
const publishChangeLog = page.publishChangeLog;
const publishModalOpen = page.publishModalOpen;
const recycleBinRef = page.recycleBinRef;
const searchKeyword = page.searchKeyword;
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AgentForm ref="agentFormRef" @success="page.loadList" />
    <VersionHistoryDrawer @success="page.loadList" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/tenant/ai/agents"
      @restored="page.loadList"
    />

    <AgentListPublishModal
      v-model:change-log="publishChangeLog"
      v-model:open="publishModalOpen"
      :confirm-loading="page.publishLoading"
      @confirm="page.onPublishConfirm"
    />

    <AIPageHeroCard
      :chips="page.heroChips"
      :description="$t('tenant.ai.agent.pageDesc')"
      icon="lucide:bot"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="page.heroMetrics"
      :title="$t('tenant.ai.agent.title')"
    />

    <AgentListToolbar
      v-model:filter-status="filterStatus"
      v-model:search-keyword="searchKeyword"
      :has-active-filters="page.hasActiveFilters"
      :recycle-bin-count="page.recycleBinCount"
      @clear-filters="page.onClearFilters"
      @create-agent="page.onCreateAgent"
      @open-recycle-bin="page.openRecycleBin"
      @search="page.doSearch"
    />

    <AgentListGrid
      :agents="page.list"
      :loading="page.loading"
      @create-agent="page.onCreateAgent"
      @delete="page.handleMenuAction('delete', $event)"
      @edit="page.onEditAgent"
      @publish="page.onPublish"
      @versions="page.onVersions"
    />

    <div v-if="page.total > page.pageSize" class="flex justify-end">
      <Pagination
        :current="page.currentPage"
        :page-size="page.pageSize"
        :total="page.total"
        :page-size-options="['12', '24', '48']"
        :show-size-changer="false"
        size="small"
        @change="page.onPageChange"
      />
    </div>
  </Page>
</template>
