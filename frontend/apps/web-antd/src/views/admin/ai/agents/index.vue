<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import { Pagination } from 'ant-design-vue';

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { $t } from '#/locales';

import { useAgentListPage } from './composables/use-agent-list-page';
import AgentListGrid from './modules/AgentListGrid.vue';
import AgentListPublishModal from './modules/AgentListPublishModal.vue';
import AgentListToolbar from './modules/AgentListToolbar.vue';
import AgentForm from './modules/form.vue';

defineOptions({ name: 'AIAgentList' });

const {
  VersionDrawer,
  agentFormRef,
  currentPage,
  doSearch,
  filterScope,
  filterStatus,
  handleMenuAction,
  heroChips,
  heroMetrics,
  hasActiveFilters,
  list,
  loadList,
  loading,
  onClearFilters,
  onCreateAgent,
  onEditAgent,
  onPageChange,
  onPublish,
  onPublishConfirm,
  onToggleStatus,
  onVersions,
  openRecycleBin,
  pageSize,
  publishChangeLog,
  publishLoading,
  publishModalOpen,
  recycleBinCount,
  recycleBinRef,
  searchKeyword,
  total,
} = useAgentListPage();
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AgentForm ref="agentFormRef" @success="loadList" />
    <VersionDrawer @success="loadList" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/agents"
      @restored="loadList"
    />

    <AgentListPublishModal
      v-model:change-log="publishChangeLog"
      v-model:open="publishModalOpen"
      :confirm-loading="publishLoading"
      @confirm="onPublishConfirm"
    />

    <AIPageHeroCard
      :chips="heroChips"
      :description="$t('admin.ai.agent.pageDesc')"
      icon="lucide:bot"
      icon-wrap-class="bg-primary/10 text-primary"
      :metrics="heroMetrics"
      :title="$t('admin.ai.agent.title')"
    />

    <AgentListToolbar
      :filter-scope="filterScope"
      :filter-status="filterStatus"
      :has-active-filters="hasActiveFilters"
      :recycle-bin-count="recycleBinCount"
      :search-keyword="searchKeyword"
      @clear-filters="onClearFilters"
      @create-agent="onCreateAgent"
      @open-recycle-bin="openRecycleBin"
      @search="doSearch"
      @update:filter-scope="filterScope = $event"
      @update:filter-status="filterStatus = $event"
      @update:search-keyword="searchKeyword = $event"
    />

    <AgentListGrid
      :agents="list"
      :loading="loading"
      @create-agent="onCreateAgent"
      @delete="handleMenuAction('delete', $event)"
      @edit="onEditAgent"
      @publish="onPublish"
      @toggle-status="onToggleStatus"
      @versions="onVersions"
    />

    <div v-if="total > pageSize" class="flex justify-end">
      <Pagination
        :current="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-size-options="['12', '24', '48']"
        :show-size-changer="false"
        size="small"
        @change="onPageChange"
      />
    </div>
  </Page>
</template>
