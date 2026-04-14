import type { AIAgentInfo } from '#/api/admin/ai';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import {
  deleteAIAgentApi,
  getAIAgentListApi,
  publishAIAgentApi,
  updateAIAgentStatusApi,
} from '#/api/admin/ai';
import { buildPageAIFormExtraData, useCrudList } from '#/composables';
import { $t } from '#/locales';
import {
  getAdminScopeOptions,
  getScopeColor,
  getScopeText,
} from '#/utils/scope-helpers';

import { getStatusText } from '../data';
import AgentForm from '../modules/form.vue';
import VersionHistoryDrawer from '../modules/VersionHistory.vue';

const AI_PAGE_KEY = 'admin.ai.agents';

export function useAgentListPage() {
  const agentFormRef = ref<InstanceType<typeof AgentForm>>();
  const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
    null,
  );
  const filterScope = ref<string>();
  const filterStatus = ref<string>();
  const publishModalOpen = ref(false);
  const publishChangeLog = ref('');
  const publishLoading = ref(false);
  const publishAgentId = ref<null | number>(null);

  function buildFormExtraData() {
    return buildPageAIFormExtraData({ pageKey: AI_PAGE_KEY });
  }

  function openAgentEdit(agent: AIAgentInfo) {
    agentFormRef.value?.openEdit(agent, buildFormExtraData());
  }

  const {
    list,
    total,
    loading,
    currentPage,
    pageSize,
    searchKeyword,
    loadList,
    onSearch,
    onPageChange,
    handleMenuAction,
  } = useCrudList<AIAgentInfo>({
    api: {
      list: getAIAgentListApi,
      delete: deleteAIAgentApi,
      resource: '/admin/ai/agents',
    },
    i18nPrefix: 'admin.ai.agent',
    nameField: 'name',
    defaultSort: '-created_at',
    pageSize: 12,
    recycleBin: true,
    customActions: {
      edit: openAgentEdit,
    },
  });

  const recycleBinCount = computed(
    () => recycleBinRef.value?.deletedCount ?? 0,
  );

  function openRecycleBin() {
    recycleBinRef.value?.open();
  }

  function onCreateAgent() {
    agentFormRef.value?.openNew(buildFormExtraData());
  }

  const [VersionDrawer, versionDrawerApi] = useVbenDrawer({
    connectedComponent: VersionHistoryDrawer,
  });

  function onVersions(agent: AIAgentInfo) {
    versionDrawerApi.setData({
      id: agent.id,
      publishedVersion: agent.published_version ?? null,
    });
    versionDrawerApi.open();
  }

  function onPublish(agent: AIAgentInfo) {
    publishAgentId.value = agent.id;
    publishChangeLog.value = '';
    publishModalOpen.value = true;
  }

  async function onPublishConfirm() {
    if (publishAgentId.value === null) return;

    publishLoading.value = true;
    try {
      await publishAIAgentApi(publishAgentId.value, {
        change_log: publishChangeLog.value || null,
      });
      message.success($t('admin.ai.agent.messages.publishSuccess'));
      publishModalOpen.value = false;
      await loadList();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      publishLoading.value = false;
    }
  }

  async function onToggleStatus(agent: AIAgentInfo) {
    if (agent.is_system) return;

    const nextStatus = agent.status === 'disabled' ? 'published' : 'disabled';
    try {
      await updateAIAgentStatusApi(agent.id, nextStatus);
      message.success($t('admin.ai.agent.messages.toggleSuccess'));
      await loadList();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  function doSearch() {
    const params: Record<string, unknown> = {};

    if (searchKeyword.value.trim()) {
      params['filter[name][ilike]'] = searchKeyword.value.trim();
    }
    if (filterScope.value) {
      params['filter[scope][eq]'] = filterScope.value;
    }
    if (filterStatus.value) {
      params['filter[status][eq]'] = filterStatus.value;
    }

    onSearch(params);
  }

  function onClearFilters() {
    searchKeyword.value = '';
    filterScope.value = undefined;
    filterStatus.value = undefined;
    onSearch({});
  }

  const hasActiveFilters = computed(
    () => !!searchKeyword.value || !!filterScope.value || !!filterStatus.value,
  );

  const stats = computed(() => {
    const all = list.value;

    return {
      total: total.value,
      published: all.filter((agent) => agent.status === 'published').length,
      system: all.filter((agent) => agent.is_system).length,
    };
  });

  const selectedScopeLabel = computed(() => {
    return getAdminScopeOptions().find(
      (option) => option.value === filterScope.value,
    )?.label;
  });

  const heroMetrics = computed(() => [
    {
      key: 'total',
      label: $t('admin.common.total'),
      value: stats.value.total,
    },
    {
      key: 'published',
      label: $t('admin.ai.agent.status_options.published'),
      value: stats.value.published,
    },
    {
      key: 'system',
      label: $t('admin.ai.agent.type_options.system'),
      value: stats.value.system,
    },
    {
      key: 'recycle',
      label: $t('common.recycleBin.title'),
      value: recycleBinCount.value,
    },
  ]);

  const heroChips = computed(() => {
    const chips = [
      {
        key: 'focus',
        icon: 'lucide:bot',
        className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
        text: `${$t('admin.ai.agent.executionMode')} / ${$t('admin.ai.agent.status')} / ${$t('common.scope.scope')}`,
      },
    ];

    if (searchKeyword.value.trim()) {
      chips.push({
        key: 'keyword',
        icon: 'lucide:search',
        className: 'bg-background/90 text-foreground',
        text: `${$t('admin.ai.agent.name')}: ${searchKeyword.value.trim()}`,
      });
    }

    if (selectedScopeLabel.value) {
      chips.push({
        key: 'scope',
        icon: 'lucide:building-2',
        className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        text: selectedScopeLabel.value,
      });
    }

    if (filterStatus.value) {
      chips.push({
        key: 'status',
        icon: 'lucide:badge-check',
        className: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
        text: getStatusText(filterStatus.value),
      });
    }

    return chips;
  });

  return {
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
    onEditAgent: openAgentEdit,
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
    getScopeColor,
    getScopeText,
  };
}
