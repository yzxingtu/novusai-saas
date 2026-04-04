<script lang="ts" setup>
import type {
  AdminSkillPackageInfo,
  SkillPackageResolvedToolInfo,
  SkillPackageValvesInfo,
} from '#/api/admin/skill-packages';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Empty,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Spin,
  Switch,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  getSkillPackageDetailApi,
  getSkillPackageResolvedToolsApi,
  getSkillPackageSkillsApi,
  getSkillPackageValvesApi,
  updateSkillPackageValvesApi,
} from '#/api/admin/skill-packages';
import { deleteSkillApi, toggleSkillStatusApi } from '#/api/admin/skills';
import { useDetailPageAi } from '#/composables/use-detail-page-ai';
import { usePageAIContext } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { useAccess } from '#/utils';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { formatRelativeTime } from '#/utils/common';

import { getSkillTypeText } from '../skills/data';
import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
} from './data';

defineOptions({ name: 'AdminSkillPackageDetail' });

type ResolvedTool = SkillPackageResolvedToolInfo;

type ValvesSchema = NonNullable<SkillPackageValvesInfo['valves_schema']>;
type ValvesInputType = 'json' | 'number' | 'string' | 'switch';

interface ValveField {
  default?: unknown;
  description?: string;
  isRequired: boolean;
  key: string;
  type?: string;
}

const route = useRoute();
const router = useRouter();
const { hasAccessByCodes } = useAccess();
const canViewSkillDetail = hasAccessByCodes(['ai_skill:detail']);
const canToggleSkillStatus = hasAccessByCodes(['ai_skill:update_status']);
const canDeleteSkill = hasAccessByCodes(['ai_skill:delete']);
const canUpdateSkillPackage = hasAccessByCodes(['ai_skill_package:update']);

const packageId = computed(() => Number(route.params.id));
const activeTab = ref(
  typeof route.query.tab === 'string' ? route.query.tab : 'overview',
);

const loading = ref(false);
const pkg = ref<AdminSkillPackageInfo | null>(null);
const skills = ref<AdminSkillInfo[]>([]);
const skillsLoading = ref(false);
const resolvedTools = ref<ResolvedTool[]>([]);
const toolsLoading = ref(false);
const valvesSchema = ref<null | ValvesSchema>(null);
const valvesConfig = ref<Record<string, unknown>>({});
const valvesSaving = ref(false);

function getPackageStatusColor(isActive: boolean): string {
  return isActive ? 'success' : 'default';
}

function getPackageStatusText(isActive: boolean): string {
  return isActive ? $t('admin.common.enabled') : $t('admin.common.disabled');
}

function getPackageHeroClass(): string {
  if (pkg.value?.source_plugin) {
    return 'bg-fuchsia-500/10 text-fuchsia-600 ring-fuchsia-400/20 dark:text-fuchsia-400';
  }
  if (pkg.value?.is_system) {
    return 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400';
  }
  return 'bg-primary/10 text-primary ring-primary/20';
}

function getPackageIcon(icon: null | string | undefined): string {
  return icon || 'lucide:package';
}

function getToolTypeColor(type: null | string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'purple';
    }
    case 'code_execution': {
      return 'orange';
    }
    case 'data_create':
    case 'data_delete':
    case 'data_query':
    case 'data_update': {
      return 'cyan';
    }
    case 'email': {
      return 'gold';
    }
    case 'http': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

function getToolTypeIcon(type: null | string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'lucide:sparkles';
    }
    case 'code_execution': {
      return 'lucide:square-terminal';
    }
    case 'data_create':
    case 'data_delete':
    case 'data_query':
    case 'data_update': {
      return 'lucide:database-zap';
    }
    case 'email': {
      return 'lucide:mail';
    }
    case 'http': {
      return 'lucide:globe';
    }
    default: {
      return 'lucide:wrench';
    }
  }
}

function getToolTypeText(type: null | string | undefined): string {
  if (!type) return '-';
  return type
    .replaceAll('_', ' ')
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function getToolRequiredParamCount(tool: ResolvedTool): number {
  return tool.parameters.filter((item) => item.required).length;
}

function isSecretKey(key: string): boolean {
  const normalizedKey = key.toLowerCase().replaceAll('-', '_');
  return [
    'api_key',
    'secret',
    'password',
    'access_token',
    'auth_token',
    'private_key',
  ].some((term) => normalizedKey.includes(term));
}

function getValveInputType(type?: string): ValvesInputType {
  switch (type) {
    case 'array':
    case 'object': {
      return 'json';
    }
    case 'boolean': {
      return 'switch';
    }
    case 'integer':
    case 'number': {
      return 'number';
    }
    default: {
      return 'string';
    }
  }
}

function isConfiguredValveValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === 'object') {
    return Object.keys(value).length > 0;
  }
  return true;
}

function buildInitialValvesConfig(
  data: SkillPackageValvesInfo,
): Record<string, unknown> {
  const schema = data.valves_schema;
  const savedConfig = (data.valves_config || {}) as Record<string, unknown>;

  if (!schema?.properties) {
    return {};
  }

  const nextConfig: Record<string, unknown> = {};

  for (const [key, prop] of Object.entries(schema.properties)) {
    if (key in savedConfig) {
      nextConfig[key] = savedConfig[key];
      continue;
    }

    if (prop.default !== undefined) {
      nextConfig[key] = prop.default;
      continue;
    }

    switch (getValveInputType(prop.type)) {
      case 'json': {
        nextConfig[key] = prop.type === 'array' ? [] : {};
        break;
      }
      case 'number': {
        nextConfig[key] = null;
        break;
      }
      case 'switch': {
        nextConfig[key] = false;
        break;
      }
      default: {
        nextConfig[key] = '';
      }
    }
  }

  return nextConfig;
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

function getJsonValvePlaceholder(field: ValveField): string {
  if (field.default !== undefined) {
    return JSON.stringify(field.default, null, 2);
  }
  return field.type === 'array' ? '[]' : '{}';
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

const sortedValveFields = computed<ValveField[]>(() => {
  if (!valvesSchema.value?.properties) {
    return [];
  }

  const required = new Set(valvesSchema.value.required || []);

  return Object.entries(valvesSchema.value.properties)
    .map(([key, prop]) => ({
      key,
      ...prop,
      isRequired: required.has(key),
    }))
    .toSorted((a, b) => {
      if (a.isRequired !== b.isRequired) {
        return a.isRequired ? -1 : 1;
      }
      return a.key.localeCompare(b.key);
    });
});

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
    }
  },
);

watch(packageId, () => {
  void loadPage();
});

onMounted(() => {
  void loadPage();
});

usePageAIContext({
  resource: '/admin/ai/skill-packages',
  entityName: () => pkg.value?.name ?? $t('admin.ai.skillPackage.detail.title'),
  entityDescription: () => $t('admin.ai.skillPackage.pageDesc'),
  data: () => ({
    package_id: packageId.value,
    package_name: pkg.value?.name ?? '',
  }),
});

useDetailPageAi({
  refreshFn: async () => {
    await loadPage();
  },
  backRoute: '/admin/ai/skill-packages',
});
</script>

<template>
  <Page auto-content-height>
    <Spin :spinning="loading">
      <div v-if="!loading && !pkg" class="py-20">
        <Empty :description="$t('common.noData')" />
      </div>

      <div v-if="pkg" class="flex flex-col gap-4">
        <div
          class="relative overflow-hidden rounded-xl border bg-card shadow-sm"
        >
          <div
            class="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent"
          ></div>

          <div class="relative p-6">
            <div class="mb-5 flex items-center justify-between gap-4">
              <button
                class="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                @click="goBack"
              >
                <IconifyIcon icon="lucide:chevron-left" class="size-4" />
                {{ $t('common.back') }}
              </button>

              <div class="flex flex-wrap items-center gap-2">
                <Button size="small" @click="openWorkspace()">
                  <IconifyIcon
                    icon="lucide:layout-panel-left"
                    class="mr-1 size-3.5"
                  />
                  {{ $t('admin.ai.skillPackage.detail.openWorkspace') }}
                </Button>
                <Button size="small" @click="focusTab('tools')">
                  <IconifyIcon icon="lucide:wrench" class="mr-1 size-3.5" />
                  {{ $t('admin.ai.skillPackage.detail.tools') }}
                </Button>
                <Button
                  size="small"
                  :disabled="!hasValves"
                  @click="focusTab('valves')"
                >
                  <IconifyIcon icon="lucide:settings-2" class="mr-1 size-3.5" />
                  {{ $t('admin.ai.skillPackage.valves.title') }}
                </Button>
              </div>
            </div>

            <div class="flex items-start gap-5">
              <div
                class="flex size-16 shrink-0 items-center justify-center rounded-2xl shadow-sm ring-2 ring-offset-2 ring-offset-card"
                :class="getPackageHeroClass()"
              >
                <IconifyIcon
                  :icon="getPackageIcon(pkg.avatar)"
                  class="size-8"
                />
              </div>

              <div class="min-w-0 flex-1">
                <h1 class="mb-1 text-xl font-bold text-foreground">
                  {{ pkg.name }}
                </h1>
                <p class="mb-4 text-sm text-muted-foreground">
                  {{
                    pkg.description ||
                    $t('admin.ai.skillPackage.detail.noDescription')
                  }}
                </p>

                <div class="flex flex-wrap items-center gap-2">
                  <Tag
                    :color="getPackageRoleColor(pkg.package_role_key)"
                    class="!mr-0 !text-xs"
                  >
                    {{ getPackageRoleText(pkg.package_role_key) }}
                  </Tag>
                  <Tag
                    :color="getPackageStatusColor(pkg.is_active)"
                    class="!mr-0 !text-xs"
                  >
                    {{ getPackageStatusText(pkg.is_active) }}
                  </Tag>
                  <Tag
                    :color="
                      getRuntimeBindingModeColor(pkg.runtime_binding_mode)
                    "
                    class="!mr-0 !text-xs"
                  >
                    {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
                  </Tag>
                  <Tag
                    v-if="pkg.is_recommended"
                    color="gold"
                    class="!mr-0 !text-xs"
                  >
                    <div class="flex items-center gap-1">
                      <IconifyIcon icon="lucide:star" class="size-3" />
                      {{ $t('admin.ai.skillPackage.isRecommended') }}
                    </div>
                  </Tag>
                  <div
                    class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
                  >
                    <IconifyIcon
                      icon="lucide:boxes"
                      class="size-3.5 text-primary/70"
                    />
                    {{ pkg.skill_count }}
                    {{ $t('admin.ai.skillPackage.skillCount') }}
                  </div>
                  <div
                    class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
                  >
                    <IconifyIcon
                      icon="lucide:link-2"
                      class="size-3.5 text-primary/70"
                    />
                    {{
                      getSourceSummaryText(
                        pkg.source_summary,
                        pkg.source_plugin,
                      )
                    }}
                  </div>
                  <div
                    v-if="pkg.source_plugin"
                    class="flex items-center gap-1.5 rounded-lg border border-border/50 bg-background px-3 py-1 text-xs text-foreground"
                  >
                    <IconifyIcon
                      icon="lucide:plug"
                      class="size-3.5 text-primary/70"
                    />
                    {{ pkg.source_plugin }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-xl border bg-card">
          <Tabs v-model:active-key="activeTab" class="px-2 pt-1">
            <TabPane key="overview">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon
                    icon="lucide:layout-dashboard"
                    class="size-3.5"
                  />
                  {{ $t('admin.ai.skillPackage.detail.overview') }}
                </span>
              </template>

              <div class="flex flex-col gap-5 p-5 pt-3">
                <Alert
                  :message="$t('admin.ai.skillPackage.detail.runtimeTruthHint')"
                  type="info"
                  show-icon
                />

                <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:boxes"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">
                        {{ $t('admin.ai.skillPackage.skillCount') }}
                      </span>
                    </div>
                    <div class="text-lg font-semibold text-foreground">
                      {{ pkg.skill_count }}
                    </div>
                  </div>

                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:wrench"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">
                        {{ $t('admin.ai.skillPackage.detail.tools') }}
                      </span>
                    </div>
                    <div class="text-lg font-semibold text-foreground">
                      {{ resolvedTools.length }}
                    </div>
                  </div>

                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:key-round"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">
                        {{ $t('admin.ai.skillPackage.detail.envVars') }}
                      </span>
                    </div>
                    <div class="text-lg font-semibold text-foreground">
                      {{ valvesFieldCount }}
                    </div>
                  </div>

                  <div class="rounded-xl border bg-accent/30 p-4">
                    <div class="mb-1.5 flex items-center gap-1.5">
                      <IconifyIcon
                        icon="lucide:clock-3"
                        class="size-3.5 text-muted-foreground"
                      />
                      <span class="text-xs text-muted-foreground">
                        {{ $t('admin.ai.skillPackage.detail.updatedAt') }}
                      </span>
                    </div>
                    <div class="text-sm font-semibold text-foreground">
                      {{ formatRelativeTime(pkg.updated_at) }}
                    </div>
                  </div>
                </div>

                <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                  <div class="rounded-xl border bg-accent/30 p-5">
                    <div class="mb-4 flex items-center gap-2">
                      <div
                        class="flex size-7 items-center justify-center rounded-lg bg-primary/10"
                      >
                        <IconifyIcon
                          icon="lucide:package-open"
                          class="size-4 text-primary"
                        />
                      </div>
                      <span class="text-sm font-semibold">
                        {{ $t('admin.ai.skillPackage.detail.basicInfo') }}
                      </span>
                    </div>

                    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div
                        class="rounded-lg border bg-background px-4 py-3 md:col-span-2"
                      >
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.description') }}
                        </div>
                        <div
                          class="mt-1 text-sm leading-relaxed text-foreground"
                        >
                          {{
                            pkg.description ||
                            $t('admin.ai.skillPackage.detail.noDescription')
                          }}
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.packageRole') }}
                        </div>
                        <div class="mt-1">
                          <Tag
                            :color="getPackageRoleColor(pkg.package_role_key)"
                            class="!mr-0 !text-xs"
                          >
                            {{ getPackageRoleText(pkg.package_role_key) }}
                          </Tag>
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.runtimeBinding') }}
                        </div>
                        <div class="mt-1">
                          <Tag
                            :color="
                              getRuntimeBindingModeColor(
                                pkg.runtime_binding_mode,
                              )
                            "
                            class="!mr-0 !text-xs"
                          >
                            {{
                              getRuntimeBindingModeText(
                                pkg.runtime_binding_mode,
                              )
                            }}
                          </Tag>
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.isActive') }}
                        </div>
                        <div class="mt-1">
                          <Tag
                            :color="getPackageStatusColor(pkg.is_active)"
                            class="!mr-0 !text-xs"
                          >
                            {{ getPackageStatusText(pkg.is_active) }}
                          </Tag>
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.isRecommended') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{
                            pkg.is_recommended
                              ? $t('admin.ai.skillPackage.detail.yes')
                              : $t('admin.ai.skillPackage.detail.no')
                          }}
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.sortOrder') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{ pkg.sort_order }}
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.sourceSummary') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{
                            getSourceSummaryText(
                              pkg.source_summary,
                              pkg.source_plugin,
                            )
                          }}
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.detail.tenantName') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{
                            pkg.tenant_id === null
                              ? $t(
                                  'admin.ai.skillPackage.detail.platformManaged',
                                )
                              : `#${pkg.tenant_id}`
                          }}
                        </div>
                      </div>

                      <div class="rounded-lg border bg-background px-4 py-3">
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.common.createdAt') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{ formatRelativeTime(pkg.created_at) }}
                        </div>
                      </div>

                      <div
                        class="rounded-lg border bg-background px-4 py-3 md:col-span-2"
                      >
                        <div class="text-xs text-muted-foreground">
                          {{ $t('admin.ai.skillPackage.detail.updatedAt') }}
                        </div>
                        <div class="mt-1 text-sm font-medium text-foreground">
                          {{ formatRelativeTime(pkg.updated_at) }}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex flex-col gap-4">
                    <div class="rounded-xl border bg-accent/30 p-5">
                      <div class="mb-4 flex items-center justify-between gap-3">
                        <div class="flex items-center gap-2">
                          <div
                            class="flex size-7 items-center justify-center rounded-lg bg-cyan-500/10"
                          >
                            <IconifyIcon
                              icon="lucide:wrench"
                              class="size-4 text-cyan-500"
                            />
                          </div>
                          <span class="text-sm font-semibold">
                            {{ $t('admin.ai.skillPackage.detail.tools') }}
                          </span>
                        </div>
                        <Button
                          size="small"
                          type="link"
                          @click="focusTab('tools')"
                        >
                          {{ $t('shared.common.viewDetail') }}
                        </Button>
                      </div>

                      <div
                        v-if="resolvedTools.length === 0"
                        class="rounded-lg border border-dashed bg-background px-4 py-6 text-center text-sm text-muted-foreground"
                      >
                        {{ $t('admin.ai.skillPackage.detail.noTools') }}
                      </div>

                      <div v-else class="flex flex-col gap-3">
                        <div
                          v-for="tool in resolvedTools.slice(0, 3)"
                          :key="tool.name"
                          class="rounded-lg border bg-background px-4 py-3"
                        >
                          <div class="flex items-start justify-between gap-3">
                            <div class="min-w-0 flex-1">
                              <div class="flex items-center gap-2">
                                <IconifyIcon
                                  :icon="getToolTypeIcon(tool.tool_type)"
                                  class="size-4 text-primary/80"
                                />
                                <span
                                  class="truncate font-mono text-sm font-semibold"
                                >
                                  {{ tool.name }}
                                </span>
                              </div>
                              <div class="mt-1 text-xs text-muted-foreground">
                                {{ tool.source_skill_name }}
                              </div>
                            </div>
                            <Tag
                              v-if="tool.tool_type"
                              :color="getToolTypeColor(tool.tool_type)"
                              class="!mr-0 !text-[11px]"
                            >
                              {{ getToolTypeText(tool.tool_type) }}
                            </Tag>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="rounded-xl border bg-accent/30 p-5">
                      <div class="mb-4 flex items-center justify-between gap-3">
                        <div class="flex items-center gap-2">
                          <div
                            class="flex size-7 items-center justify-center rounded-lg bg-emerald-500/10"
                          >
                            <IconifyIcon
                              icon="lucide:key-round"
                              class="size-4 text-emerald-500"
                            />
                          </div>
                          <span class="text-sm font-semibold">
                            {{ $t('admin.ai.skillPackage.valves.title') }}
                          </span>
                        </div>
                        <Button
                          size="small"
                          type="link"
                          :disabled="!hasValves"
                          @click="focusTab('valves')"
                        >
                          {{ $t('shared.common.viewDetail') }}
                        </Button>
                      </div>

                      <div
                        v-if="!hasValves"
                        class="rounded-lg border border-dashed bg-background px-4 py-6 text-center text-sm text-muted-foreground"
                      >
                        {{ $t('admin.ai.skillPackage.valves.noSchema') }}
                      </div>

                      <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <div class="rounded-lg border bg-background px-4 py-3">
                          <div class="text-xs text-muted-foreground">
                            {{ $t('admin.ai.skillPackage.detail.envVars') }}
                          </div>
                          <div
                            class="mt-1 text-lg font-semibold text-foreground"
                          >
                            {{ valvesFieldCount }}
                          </div>
                        </div>
                        <div class="rounded-lg border bg-background px-4 py-3">
                          <div class="text-xs text-muted-foreground">
                            {{ $t('admin.ai.skillPackage.valves.required') }}
                          </div>
                          <div
                            class="mt-1 text-lg font-semibold text-foreground"
                          >
                            {{ requiredValveCount }}
                          </div>
                        </div>
                        <div class="rounded-lg border bg-background px-4 py-3">
                          <div class="text-xs text-muted-foreground">
                            {{ $t('admin.ai.skillPackage.detail.configured') }}
                          </div>
                          <div
                            class="mt-1 text-lg font-semibold text-foreground"
                          >
                            {{ configuredValveCount }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TabPane>

            <TabPane key="skills">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:blocks" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.detail.skills') }}
                </span>
              </template>

              <div class="flex flex-col gap-4 p-5 pt-3">
                <div class="flex items-start justify-between gap-4">
                  <div>
                    <div class="text-sm font-semibold text-foreground">
                      {{ $t('admin.ai.skillPackage.detail.skills') }}
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">
                      {{ pkg.skill_count }}
                      {{ $t('admin.ai.skillPackage.skillCount') }}
                    </p>
                  </div>

                  <div class="flex items-center gap-2">
                    <Button size="small" @click="openWorkspace()">
                      <IconifyIcon
                        icon="lucide:layout-panel-left"
                        class="mr-1 size-3.5"
                      />
                      {{ $t('admin.ai.skillPackage.detail.openWorkspace') }}
                    </Button>
                    <Button
                      size="small"
                      type="primary"
                      @click="openWorkspace(true)"
                    >
                      <IconifyIcon icon="lucide:plus" class="mr-1 size-3.5" />
                      {{ $t('admin.ai.skill.create') }}
                    </Button>
                  </div>
                </div>

                <Spin :spinning="skillsLoading">
                  <div v-if="skills.length === 0" class="py-12">
                    <Empty
                      :description="$t('admin.ai.skillPackage.detail.empty')"
                    />
                  </div>

                  <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <div
                      v-for="skill in skills"
                      :key="skill.id"
                      class="rounded-xl border bg-accent/30 p-4 transition-all duration-200 hover:border-primary/20 hover:shadow-sm"
                    >
                      <div class="flex items-start justify-between gap-4">
                        <div class="flex min-w-0 flex-1 items-start gap-3">
                          <div
                            class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                          >
                            <IconifyIcon
                              :icon="
                                skill.avatar || getSkillTypeIcon(skill.type)
                              "
                              class="size-5 text-primary"
                            />
                          </div>

                          <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                              <span
                                class="truncate text-sm font-semibold text-foreground"
                              >
                                {{ skill.name }}
                              </span>
                              <Tag
                                :color="getSkillTypeColor(skill.type)"
                                class="!mr-0 !text-[11px]"
                              >
                                {{ getSkillTypeText(skill.type) }}
                              </Tag>
                              <Tag
                                v-if="skill.is_system"
                                color="purple"
                                class="!mr-0 !text-[11px]"
                              >
                                {{ $t('admin.ai.skillPackage.system') }}
                              </Tag>
                              <Tag
                                v-if="skill.source_plugin"
                                color="geekblue"
                                class="!mr-0 !text-[11px]"
                              >
                                {{ skill.source_plugin }}
                              </Tag>
                            </div>

                            <p
                              class="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground"
                            >
                              {{
                                skill.description ||
                                $t('admin.ai.skillPackage.detail.noDescription')
                              }}
                            </p>

                            <div
                              class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
                            >
                              <span class="flex items-center gap-1">
                                <IconifyIcon
                                  icon="lucide:clock-3"
                                  class="size-3.5"
                                />
                                {{ skill.timeout }}s
                              </span>
                              <span class="flex items-center gap-1">
                                <IconifyIcon
                                  icon="lucide:calendar-days"
                                  class="size-3.5"
                                />
                                {{ formatRelativeTime(skill.created_at) }}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div class="flex shrink-0 items-center gap-1">
                          <Button
                            v-if="canViewSkillDetail"
                            size="small"
                            type="text"
                            @click="openSkillDetail(skill.id)"
                          >
                            <IconifyIcon
                              icon="lucide:external-link"
                              class="size-4"
                            />
                          </Button>
                          <Switch
                            :checked="skill.is_active"
                            size="small"
                            :disabled="skill.is_system || !canToggleSkillStatus"
                            @change="handleToggleSkillStatus(skill)"
                          />
                          <Popconfirm
                            v-if="!skill.is_system && canDeleteSkill"
                            :title="$t('admin.common.confirmDelete')"
                            @confirm="handleDeleteSkill(skill)"
                          >
                            <Button danger size="small" type="text">
                              <IconifyIcon
                                icon="lucide:trash-2"
                                class="size-4"
                              />
                            </Button>
                          </Popconfirm>
                        </div>
                      </div>
                    </div>
                  </div>
                </Spin>
              </div>
            </TabPane>
            <TabPane key="tools">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:wrench" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.detail.tools') }}
                </span>
              </template>

              <div class="flex flex-col gap-4 p-5 pt-3">
                <div>
                  <div class="text-sm font-semibold text-foreground">
                    {{ $t('admin.ai.skillPackage.detail.tools') }}
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">
                    {{ resolvedTools.length }}
                    {{ $t('admin.ai.skillPackage.detail.tools') }}
                  </p>
                </div>

                <Spin :spinning="toolsLoading">
                  <div v-if="resolvedTools.length === 0" class="py-12">
                    <Empty
                      :description="$t('admin.ai.skillPackage.detail.noTools')"
                    />
                  </div>

                  <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <div
                      v-for="tool in resolvedTools"
                      :key="tool.name"
                      class="rounded-xl border bg-accent/30 p-4 transition-all duration-200 hover:border-primary/20 hover:shadow-sm"
                    >
                      <div class="flex items-start gap-3">
                        <div
                          class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                        >
                          <IconifyIcon
                            :icon="getToolTypeIcon(tool.tool_type)"
                            class="size-5 text-primary"
                          />
                        </div>

                        <div class="min-w-0 flex-1">
                          <div class="flex flex-wrap items-center gap-2">
                            <span
                              class="font-mono text-sm font-semibold text-foreground"
                            >
                              {{ tool.name }}
                            </span>
                            <Tag
                              v-if="tool.tool_type"
                              :color="getToolTypeColor(tool.tool_type)"
                              class="!mr-0 !text-[11px]"
                            >
                              {{ getToolTypeText(tool.tool_type) }}
                            </Tag>
                            <Tag
                              v-if="tool.source_plugin"
                              color="geekblue"
                              class="!mr-0 !text-[11px]"
                            >
                              {{ tool.source_plugin }}
                            </Tag>
                          </div>

                          <p
                            class="mt-2 text-sm leading-relaxed text-muted-foreground"
                          >
                            {{
                              tool.description ||
                              $t('admin.ai.skillPackage.detail.noDescription')
                            }}
                          </p>

                          <div
                            class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3"
                          >
                            <div
                              class="rounded-lg border bg-background px-3 py-2"
                            >
                              <div class="text-[11px] text-muted-foreground">
                                {{
                                  $t('admin.ai.skillPackage.detail.skillName')
                                }}
                              </div>
                              <div
                                class="mt-1 truncate text-sm font-medium text-foreground"
                              >
                                {{ tool.source_skill_name }}
                              </div>
                            </div>

                            <div
                              class="rounded-lg border bg-background px-3 py-2"
                            >
                              <div class="text-[11px] text-muted-foreground">
                                {{
                                  $t('admin.ai.skillPackage.detail.toolParams')
                                }}
                              </div>
                              <div
                                class="mt-1 text-sm font-medium text-foreground"
                              >
                                {{ tool.parameters.length }}
                              </div>
                            </div>

                            <div
                              class="rounded-lg border bg-background px-3 py-2"
                            >
                              <div class="text-[11px] text-muted-foreground">
                                {{
                                  $t('admin.ai.skillPackage.valves.required')
                                }}
                              </div>
                              <div
                                class="mt-1 text-sm font-medium text-foreground"
                              >
                                {{ getToolRequiredParamCount(tool) }}
                              </div>
                            </div>
                          </div>

                          <div v-if="tool.parameters.length > 0" class="mt-3">
                            <div
                              class="mb-2 text-xs font-medium text-muted-foreground"
                            >
                              {{
                                $t('admin.ai.skillPackage.detail.toolParams')
                              }}
                            </div>
                            <div class="flex flex-wrap gap-2">
                              <div
                                v-for="param in tool.parameters"
                                :key="param.name"
                                class="rounded-full border bg-background px-3 py-1 text-xs"
                              >
                                <span class="font-mono text-foreground">
                                  {{ param.name }}
                                </span>
                                <span class="ml-1 text-muted-foreground">
                                  {{ param.type }}
                                </span>
                                <span
                                  v-if="param.required"
                                  class="ml-1 text-red-500 dark:text-red-400"
                                >
                                  *
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Spin>
              </div>
            </TabPane>

            <TabPane key="valves" :disabled="!hasValves">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:settings-2" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.valves.title') }}
                </span>
              </template>

              <div class="flex flex-col gap-4 p-5 pt-3">
                <div class="flex items-start justify-between gap-4">
                  <div>
                    <div class="text-sm font-semibold text-foreground">
                      {{ $t('admin.ai.skillPackage.valves.title') }}
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">
                      {{ configuredValveCount }}/{{ valvesFieldCount }}
                    </p>
                  </div>

                  <div class="flex items-center gap-2">
                    <Button
                      v-if="canUpdateSkillPackage"
                      size="small"
                      :disabled="!hasValves"
                      @click="resetValvesToDefaults"
                    >
                      {{ $t('admin.ai.skillPackage.valves.resetDefaults') }}
                    </Button>
                    <Button
                      v-if="canUpdateSkillPackage"
                      size="small"
                      type="primary"
                      :loading="valvesSaving"
                      :disabled="!hasValves"
                      @click="handleSaveValves"
                    >
                      {{ $t('shared.common.save') }}
                    </Button>
                  </div>
                </div>

                <template v-if="hasValves">
                  <Alert
                    :message="$t('admin.ai.skillPackage.valves.description')"
                    type="info"
                    show-icon
                  />

                  <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <div
                      v-for="field in sortedValveFields"
                      :key="field.key"
                      class="rounded-xl border bg-accent/30 p-4"
                    >
                      <div class="mb-3 flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <div class="flex flex-wrap items-center gap-2">
                            <code
                              class="rounded bg-background px-2 py-1 font-mono text-xs text-foreground"
                            >
                              {{ field.key }}
                            </code>
                            <Tag
                              v-if="field.isRequired"
                              color="red"
                              class="!mr-0 !text-[11px]"
                            >
                              {{ $t('admin.ai.skillPackage.valves.required') }}
                            </Tag>
                            <Tag
                              v-if="isSecretKey(field.key)"
                              color="gold"
                              class="!mr-0 !text-[11px]"
                            >
                              {{
                                $t('admin.ai.skillPackage.valves.sensitiveHint')
                              }}
                            </Tag>
                          </div>

                          <p
                            v-if="field.description"
                            class="mt-2 text-xs leading-relaxed text-muted-foreground"
                          >
                            {{ field.description }}
                          </p>
                        </div>

                        <Tag class="!mr-0 !text-[11px]">
                          {{ field.type || 'string' }}
                        </Tag>
                      </div>

                      <Switch
                        v-if="getValveInputType(field.type) === 'switch'"
                        :checked="getBooleanValveValue(field.key)"
                        @update:checked="
                          (value) =>
                            updateBooleanValve(field.key, Boolean(value))
                        "
                      />

                      <InputNumber
                        v-else-if="getValveInputType(field.type) === 'number'"
                        :value="getNumberValveValue(field.key)"
                        class="w-full"
                        :placeholder="
                          field.default !== undefined
                            ? String(field.default)
                            : undefined
                        "
                        @update:value="
                          (value) =>
                            updateNumberValve(
                              field.key,
                              typeof value === 'number' ? value : null,
                            )
                        "
                      />

                      <Input.TextArea
                        v-else-if="getValveInputType(field.type) === 'json'"
                        :value="getJsonValveValue(field.key)"
                        :rows="5"
                        class="font-mono text-xs"
                        :placeholder="getJsonValvePlaceholder(field)"
                        @update:value="
                          (value) => updateJsonValve(field.key, value)
                        "
                      />

                      <div
                        v-else-if="isSecretKey(field.key)"
                        class="flex items-center gap-2"
                      >
                        <Input.Password
                          :value="getStringValveValue(field.key)"
                          class="flex-1"
                          :placeholder="
                            field.default !== undefined
                              ? String(field.default)
                              : undefined
                          "
                          @update:value="
                            (value) => updateStringValve(field.key, value)
                          "
                        />
                        <Tag
                          v-if="getStringValveValue(field.key) === '******'"
                          color="green"
                          class="!mr-0 cursor-pointer !text-[11px]"
                          @click="updateStringValve(field.key, '')"
                        >
                          {{
                            $t('admin.ai.skillPackage.valves.secretConfigured')
                          }}
                        </Tag>
                      </div>

                      <Input
                        v-else
                        :value="getStringValveValue(field.key)"
                        :placeholder="
                          field.default !== undefined
                            ? String(field.default)
                            : undefined
                        "
                        @update:value="
                          (value) => updateStringValve(field.key, value)
                        "
                      />
                    </div>
                  </div>
                </template>

                <div v-else class="py-12">
                  <Empty
                    :description="$t('admin.ai.skillPackage.valves.noSchema')"
                  />
                </div>
              </div>
            </TabPane>
          </Tabs>
        </div>
      </div>
    </Spin>
  </Page>
</template>
