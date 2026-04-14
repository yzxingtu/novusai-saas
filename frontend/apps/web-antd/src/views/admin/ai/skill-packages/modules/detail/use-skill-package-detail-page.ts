import type { ResolvedTool, ValvesSchema } from './detail-helpers';

import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { message } from 'ant-design-vue';

import {
  getSkillPackageDetailApi,
  getSkillPackageResolvedToolsApi,
  getSkillPackageSkillsApi,
  getSkillPackageValvesApi,
  updateSkillPackageValvesApi,
} from '#/api/admin/skill-packages';
import { deleteSkillApi, toggleSkillStatusApi } from '#/api/admin/skills';
import { $t } from '#/locales';
import { useAccess } from '#/utils';
import { formatRelativeTime } from '#/utils/common';

import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
} from '../../data';
import {
  buildInitialValvesConfig,
  getJsonValvePlaceholder,
  getPackageHeroClass,
  getPackageIcon,
  getPackageStatusColor,
  getPackageStatusText,
  getSortedValveFields,
  getToolRequiredParamCount,
  getToolTypeColor,
  getToolTypeIcon,
  getToolTypeText,
  getValveInputType,
  isConfiguredValveValue,
  isSecretKey,
} from './detail-helpers';

interface OverviewStat {
  icon: string;
  labelKey: string;
  value: number | string;
  valueClass: string;
}

interface SummaryStat {
  labelKey: string;
  value: number | string;
}

export function useSkillPackageDetailPage() {
  const route = useRoute();
  const router = useRouter();
  const { hasAccessByCodes } = useAccess();

  const canViewSkillDetail = hasAccessByCodes(['ai_skill:detail']);
  const canToggleSkillStatus = hasAccessByCodes(['ai_skill:update_status']);
  const canDeleteSkill = hasAccessByCodes(['ai_skill:delete']);
  const canUpdateSkillPackage = hasAccessByCodes(['ai_skill_package:update']);

  const packageId = computed(() => Number(route.params.id));
  const activeTab = ref('overview');

  const loading = ref(false);
  const pkg = ref<AdminSkillPackageInfo | null>(null);
  const skills = ref<AdminSkillInfo[]>([]);
  const skillsLoading = ref(false);
  const resolvedTools = ref<ResolvedTool[]>([]);
  const toolsLoading = ref(false);
  const valvesSchema = ref<null | ValvesSchema>(null);
  const valvesConfig = ref<Record<string, unknown>>({});
  const valvesSaving = ref(false);

  const sortedValveFields = computed(() =>
    getSortedValveFields(valvesSchema.value),
  );
  const hasValves = computed(() => sortedValveFields.value.length > 0);
  const valvesFieldCount = computed(() => sortedValveFields.value.length);
  const requiredValveCount = computed(
    () => sortedValveFields.value.filter((field) => field.isRequired).length,
  );
  const configuredValveCount = computed(
    () =>
      sortedValveFields.value.filter((field) =>
        isConfiguredValveValue(valvesConfig.value[field.key]),
      ).length,
  );
  const overviewStats = computed<OverviewStat[]>(() => [
    {
      icon: 'lucide:boxes',
      labelKey: 'admin.ai.skillPackage.skillCount',
      value: pkg.value?.skill_count ?? 0,
      valueClass: 'text-lg font-semibold text-foreground',
    },
    {
      icon: 'lucide:wrench',
      labelKey: 'admin.ai.skillPackage.detail.tools',
      value: resolvedTools.value.length,
      valueClass: 'text-lg font-semibold text-foreground',
    },
    {
      icon: 'lucide:key-round',
      labelKey: 'admin.ai.skillPackage.detail.envVars',
      value: valvesFieldCount.value,
      valueClass: 'text-lg font-semibold text-foreground',
    },
    {
      icon: 'lucide:clock-3',
      labelKey: 'admin.ai.skillPackage.detail.updatedAt',
      value: pkg.value?.updated_at
        ? formatRelativeTime(pkg.value.updated_at)
        : '-',
      valueClass: 'text-sm font-semibold text-foreground',
    },
  ]);
  const valveSummaryStats = computed<SummaryStat[]>(() => [
    {
      labelKey: 'admin.ai.skillPackage.detail.envVars',
      value: valvesFieldCount.value,
    },
    {
      labelKey: 'admin.ai.skillPackage.valves.required',
      value: requiredValveCount.value,
    },
    {
      labelKey: 'admin.ai.skillPackage.detail.configured',
      value: configuredValveCount.value,
    },
  ]);

  async function loadPackage(): Promise<boolean> {
    loading.value = true;
    try {
      pkg.value = await getSkillPackageDetailApi(packageId.value);
      return true;
    } catch {
      router.replace('/admin/ai/skill-packages');
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function loadSkills() {
    skillsLoading.value = true;
    try {
      const response = await getSkillPackageSkillsApi(packageId.value, {
        'page[size]': 100,
        sort: 'sort_order,-created_at',
      });
      skills.value = response.items;
    } catch {
      skills.value = [];
    } finally {
      skillsLoading.value = false;
    }
  }

  async function loadValves() {
    try {
      const data = await getSkillPackageValvesApi(packageId.value);
      valvesSchema.value = data.valves_schema;
      valvesConfig.value = buildInitialValvesConfig(data);
    } catch {
      valvesSchema.value = null;
      valvesConfig.value = {};
    }
  }

  async function loadResolvedTools() {
    toolsLoading.value = true;
    try {
      const data = await getSkillPackageResolvedToolsApi(packageId.value);
      resolvedTools.value = data.tools || [];
    } catch {
      resolvedTools.value = [];
    } finally {
      toolsLoading.value = false;
    }
  }

  async function loadPage() {
    const exists = await loadPackage();
    if (!exists) {
      return;
    }
    await Promise.all([loadSkills(), loadValves(), loadResolvedTools()]);
  }

  async function handleToggleSkillStatus(skill: AdminSkillInfo) {
    try {
      await toggleSkillStatusApi(skill.id);
      message.success($t('admin.ai.skill.messages.toggleSuccess'));
      await Promise.all([loadPackage(), loadSkills(), loadResolvedTools()]);
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function handleDeleteSkill(skill: AdminSkillInfo) {
    try {
      await deleteSkillApi(skill.id);
      message.success($t('shared.common.deleteSuccess'));
      await Promise.all([loadPackage(), loadSkills(), loadResolvedTools()]);
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function handleSaveValves() {
    valvesSaving.value = true;
    try {
      await updateSkillPackageValvesApi(packageId.value, {
        valves_config: valvesConfig.value,
      });
      await loadValves();
      message.success($t('admin.ai.skillPackage.valves.saveSuccess'));
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      valvesSaving.value = false;
    }
  }

  function getStringValveValue(key: string): string {
    const value = valvesConfig.value[key];
    if (typeof value === 'string') {
      return value;
    }
    if (value === null || value === undefined) {
      return '';
    }
    return String(value);
  }

  function getNumberValveValue(key: string): number | undefined {
    const value = valvesConfig.value[key];
    return typeof value === 'number' ? value : undefined;
  }

  function getBooleanValveValue(key: string): boolean {
    return Boolean(valvesConfig.value[key]);
  }

  function getJsonValveValue(key: string): string {
    const value = valvesConfig.value[key];
    if (typeof value === 'string') {
      return value;
    }
    if (value === null || value === undefined) {
      return '';
    }
    return JSON.stringify(value, null, 2);
  }

  function updateStringValve(key: string, value: string) {
    valvesConfig.value[key] = value;
  }

  function updateNumberValve(key: string, value: null | number) {
    valvesConfig.value[key] = value;
  }

  function updateBooleanValve(key: string, value: boolean) {
    valvesConfig.value[key] = value;
  }

  function updateJsonValve(key: string, value: string) {
    try {
      valvesConfig.value[key] = value.trim() ? JSON.parse(value) : null;
    } catch {
      valvesConfig.value[key] = value;
    }
  }

  function resetValvesToDefaults() {
    valvesConfig.value = buildInitialValvesConfig({
      valves_config: null,
      valves_schema: valvesSchema.value,
    });
  }

  function focusTab(tab: string) {
    activeTab.value = tab;
  }

  function goBack() {
    router.push('/admin/ai/skill-packages');
  }

  function openWorkspace(createSkill = false) {
    const query: Record<string, string> = {
      package_id: String(packageId.value),
    };

    if (createSkill) {
      query.action = 'create_skill';
    }

    router.push({
      path: '/admin/ai/skill-packages',
      query,
    });
  }

  function openSkillDetail(skillId: number) {
    router.push(`/admin/ai/skills/${skillId}`);
  }

  watch(
    () => route.query.tab,
    (tab) => {
      if (typeof tab === 'string' && tab.length > 0) {
        activeTab.value = tab;
        return;
      }
      activeTab.value = 'overview';
    },
    { immediate: true },
  );

  watch(
    packageId,
    () => {
      void loadPage();
    },
    { immediate: true },
  );

  return {
    activeTab,
    canDeleteSkill,
    canToggleSkillStatus,
    canUpdateSkillPackage,
    canViewSkillDetail,
    configuredValveCount,
    focusTab,
    getBooleanValveValue,
    getJsonValvePlaceholder,
    getJsonValveValue,
    getNumberValveValue,
    getPackageHeroClass,
    getPackageIcon,
    getPackageRoleColor,
    getPackageRoleText,
    getPackageStatusColor,
    getPackageStatusText,
    getRuntimeBindingModeColor,
    getRuntimeBindingModeText,
    getSourceSummaryText,
    getStringValveValue,
    getToolRequiredParamCount,
    getToolTypeColor,
    getToolTypeIcon,
    getToolTypeText,
    getValveInputType,
    goBack,
    handleDeleteSkill,
    handleSaveValves,
    handleToggleSkillStatus,
    hasValves,
    isSecretKey,
    loading,
    openSkillDetail,
    openWorkspace,
    overviewStats,
    pkg,
    resetValvesToDefaults,
    resolvedTools,
    skills,
    skillsLoading,
    sortedValveFields,
    toolsLoading,
    updateBooleanValve,
    updateJsonValve,
    updateNumberValve,
    updateStringValve,
    valveSummaryStats,
    valvesConfig,
    valvesFieldCount,
    valvesSaving,
  };
}

export type UseSkillPackageDetailPageReturn = ReturnType<
  typeof useSkillPackageDetailPage
>;
