import type { AgentListItem } from '#/api/tenant/agents';

import { computed, onMounted, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { getTenantAIModelsApi } from '#/api/tenant/ai';
import {
  deleteAgentApi,
  getAgentListApi,
  publishAgentApi,
} from '#/api/tenant/agents';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { buildFormExtraData } from '#/utils/form-extra-data';

import { getFormDefaults, getStatusText } from '../data';
import AgentForm from '../modules/AgentForm.vue';
import VersionHistory from '../modules/VersionHistory.vue';
import {
  hasTenantActiveChatModel,
  resolveTenantAgentSetupState,
} from './setup-state';

export type { TenantAgentSetupState } from './setup-state';

export function useAgentListPage() {
  const agentFormRef = ref<InstanceType<typeof AgentForm>>();
  const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
    null,
  );
  const hasActiveChatModel = ref<boolean | null>(null);
  const modelCheckError = ref(false);
  const modelCheckLoading = ref(false);
  const filterStatus = ref<string>();
  const publishModalOpen = ref(false);
  const publishChangeLog = ref('');
  const publishLoading = ref(false);
  const publishAgentId = ref<null | number>(null);

  function buildCreateExtraData(defaults?: Record<string, unknown>) {
    if (!defaults || Object.keys(defaults).length === 0) {
      return buildFormExtraData();
    }

    return buildFormExtraData({
      baseDefaults: getFormDefaults(),
      defaults,
    });
  }

  function openAgentEdit(agent: AgentListItem) {
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
  } = useCrudList<AgentListItem>({
    api: {
      list: getAgentListApi,
      delete: deleteAgentApi,
      resource: '/tenant/ai/agents',
    },
    i18nPrefix: 'tenant.ai.agent',
    nameField: 'name',
    defaultSort: '-created_at',
    pageSize: 12,
    recycleBin: true,
    customActions: {
      edit: openAgentEdit,
    },
  });

  async function refreshModelStatus() {
    modelCheckLoading.value = true;
    modelCheckError.value = false;
    try {
      const models = await getTenantAIModelsApi(undefined, {
        showCodeMessage: false,
      });
      hasActiveChatModel.value = hasTenantActiveChatModel(models);
    } catch {
      modelCheckError.value = true;
      hasActiveChatModel.value = null;
    } finally {
      modelCheckLoading.value = false;
    }
  }

  const recycleBinCount = computed(
    () => recycleBinRef.value?.deletedCount ?? 0,
  );

  function openRecycleBin() {
    recycleBinRef.value?.open();
  }

  function onCreateAgent(defaults: Record<string, unknown> = {}) {
    if (hasActiveChatModel.value !== true) {
      message.warning($t('tenant.ai.agent.setup.missingModelTitle'));
      return;
    }
    agentFormRef.value?.openNew(buildCreateExtraData(defaults));
  }

  const [VersionHistoryDrawer, versionHistoryApi] = useVbenDrawer({
    connectedComponent: VersionHistory,
  });

  function onVersions(agent: AgentListItem) {
    versionHistoryApi.setData({
      id: agent.id,
      publishedVersion: agent.published_version ?? null,
    });
    versionHistoryApi.open();
  }

  function onPublish(agent: AgentListItem) {
    publishAgentId.value = agent.id;
    publishChangeLog.value = '';
    publishModalOpen.value = true;
  }

  async function onPublishConfirm() {
    if (publishAgentId.value === null) {
      return;
    }

    publishLoading.value = true;
    try {
      await publishAgentApi(publishAgentId.value, {
        change_log: publishChangeLog.value || null,
      });
      message.success($t('tenant.ai.agent.messages.publishSuccess'));
      publishModalOpen.value = false;
      await loadList();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      publishLoading.value = false;
    }
  }

  function doSearch() {
    const params: Record<string, unknown> = {};
    if (searchKeyword.value.trim()) {
      params['filter[name][ilike]'] = searchKeyword.value.trim();
    }
    if (filterStatus.value) {
      params['filter[status][eq]'] = filterStatus.value;
    }
    onSearch(params);
  }

  function onClearFilters() {
    searchKeyword.value = '';
    filterStatus.value = undefined;
    onSearch({});
  }

  const hasActiveFilters = computed(
    () => !!searchKeyword.value || !!filterStatus.value,
  );

  const setupState = computed(() =>
    resolveTenantAgentSetupState(
      hasActiveChatModel.value,
      modelCheckLoading.value,
      modelCheckError.value,
    ),
  );

  const showSetupState = computed(
    () =>
      setupState.value === 'checking' ||
      (setupState.value === 'missing-model' &&
        list.value.length === 0 &&
        total.value === 0),
  );
  const showSetupNotice = computed(
    () => setupState.value === 'missing-model' && !showSetupState.value,
  );
  const canCreateAgent = computed(() => hasActiveChatModel.value === true);

  const stats = computed(() => ({
    total: total.value,
    published: list.value.filter((agent) => agent.status === 'published')
      .length,
    system: list.value.filter((agent) => agent.is_system).length,
  }));

  const heroMetrics = computed(() => [
    {
      key: 'total',
      label: $t('common.total'),
      value: stats.value.total,
    },
    {
      key: 'published',
      label: $t('tenant.ai.agent.status_options.published'),
      value: stats.value.published,
    },
    {
      key: 'system',
      label: $t('tenant.ai.agent.system'),
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
        text: `${$t('tenant.ai.agent.executionMode')} / ${$t('tenant.ai.agent.status')} / ${$t('tenant.ai.agent.targetAudience')}`,
      },
    ];

    if (searchKeyword.value.trim()) {
      chips.push({
        key: 'keyword',
        icon: 'lucide:search',
        className: 'bg-background/90 text-foreground',
        text: `${$t('tenant.ai.agent.name')}: ${searchKeyword.value.trim()}`,
      });
    }

    if (filterStatus.value) {
      chips.push({
        key: 'status',
        icon: 'lucide:badge-check',
        className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
        text: getStatusText(filterStatus.value),
      });
    }

    return chips;
  });

  onMounted(() => {
    refreshModelStatus();
  });

  return {
    VersionHistoryDrawer,
    agentFormRef,
    canCreateAgent,
    currentPage,
    doSearch,
    filterStatus,
    handleMenuAction,
    heroChips,
    heroMetrics,
    hasActiveFilters,
    list,
    loadList,
    loading,
    modelCheckLoading,
    onClearFilters,
    onCreateAgent,
    onEditAgent: openAgentEdit,
    onPageChange,
    onPublish,
    onPublishConfirm,
    onVersions,
    openRecycleBin,
    pageSize,
    publishChangeLog,
    publishLoading,
    publishModalOpen,
    recycleBinCount,
    recycleBinRef,
    refreshModelStatus,
    searchKeyword,
    setupState,
    showSetupNotice,
    showSetupState,
    total,
  };
}
