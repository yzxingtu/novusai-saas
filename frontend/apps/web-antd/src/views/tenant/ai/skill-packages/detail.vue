<script lang="ts" setup>
import type {
  SkillPackageResolvedToolInfo,
  TenantSkillPackageInfo,
} from '#/api/tenant/skill-packages';
import type { SkillInfo } from '#/api/tenant/skills';

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Empty, Spin, Tag } from 'ant-design-vue';

import {
  getSkillPackageDetailApi,
  getSkillPackageResolvedToolsApi,
  getSkillPackageSkillsApi,
} from '#/api/tenant/skill-packages';
import { useDetailPageAi } from '#/composables/use-detail-page-ai';
import { usePageAIContext } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { formatRelativeTime } from '#/utils/common';

import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSkillTypeText,
  getSourceSummaryText,
} from './data';

defineOptions({ name: 'TenantSkillPackageDetail' });

type ResolvedTool = SkillPackageResolvedToolInfo;

const route = useRoute();
const router = useRouter();

const packageId = computed(() => Number(route.params.id));
const loading = ref(false);
const skillsLoading = ref(false);
const toolsLoading = ref(false);
const pkg = ref<null | TenantSkillPackageInfo>(null);
const skills = ref<SkillInfo[]>([]);
const resolvedTools = ref<ResolvedTool[]>([]);

function getPackageStatusText(isActive: boolean): string {
  return isActive ? $t('common.enabled') : $t('common.disabled');
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

function getToolTypeText(type: null | string | undefined): string {
  if (!type) {
    return '-';
  }
  return type.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

async function loadPackage(): Promise<boolean> {
  loading.value = true;
  try {
    pkg.value = await getSkillPackageDetailApi(packageId.value);
    return true;
  } catch {
    router.replace('/tenant/ai/skill-packages');
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
  await Promise.all([loadSkills(), loadResolvedTools()]);
}

function goBack() {
  router.push('/tenant/ai/skill-packages');
}

watch(packageId, () => {
  void loadPage();
});

onMounted(() => {
  void loadPage();
});

usePageAIContext({
  resource: '/tenant/ai/skill-packages',
  entityName: () => pkg.value?.name ?? $t('tenant.ai.skillPackage.detail.title'),
  entityDescription: () => $t('tenant.ai.skillPackage.pageDesc'),
  data: () => ({
    package_id: packageId.value,
    package_name: pkg.value?.name ?? '',
  }),
});

useDetailPageAi({
  refreshFn: async () => {
    await loadPage();
  },
  backRoute: '/tenant/ai/skill-packages',
});
</script>

<template>
  <Page auto-content-height>
    <Spin :spinning="loading">
      <div v-if="!loading && !pkg" class="py-20">
        <Empty :description="$t('common.noData')" />
      </div>

      <div v-if="pkg" class="flex flex-col gap-4">
        <div class="rounded-xl border bg-card p-6 shadow-sm">
          <button
            class="mb-5 flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            @click="goBack"
          >
            <IconifyIcon icon="lucide:chevron-left" class="size-4" />
            {{ $t('tenant.ai.skillPackage.detail.backToList') }}
          </button>

          <div class="flex items-start gap-5">
            <div
              class="flex size-16 shrink-0 items-center justify-center rounded-2xl shadow-sm ring-2 ring-offset-2 ring-offset-card"
              :class="getPackageHeroClass()"
            >
              <IconifyIcon :icon="pkg.avatar || 'lucide:package'" class="size-8" />
            </div>

            <div class="min-w-0 flex-1">
              <h1 class="mb-1 text-xl font-bold text-foreground">
                {{ pkg.name }}
              </h1>
              <p class="mb-4 text-sm text-muted-foreground">
                {{
                  pkg.description ||
                  $t('tenant.ai.skillPackage.detail.noDescription')
                }}
              </p>

              <div class="flex flex-wrap items-center gap-2">
                <Tag :color="getPackageRoleColor(pkg.package_role_key)" class="!mr-0 !text-xs">
                  {{ getPackageRoleText(pkg.package_role_key) }}
                </Tag>
                <Tag
                  :color="getRuntimeBindingModeColor(pkg.runtime_binding_mode)"
                  class="!mr-0 !text-xs"
                >
                  {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
                </Tag>
                <Tag :color="pkg.is_active ? 'success' : 'default'" class="!mr-0 !text-xs">
                  {{ getPackageStatusText(pkg.is_active) }}
                </Tag>
                <Tag v-if="pkg.is_recommended" color="gold" class="!mr-0 !text-xs">
                  {{ $t('tenant.ai.skillPackage.isRecommended') }}
                </Tag>
                <Tag v-if="pkg.source_plugin" color="geekblue" class="!mr-0 !text-xs">
                  {{ pkg.source_plugin }}
                </Tag>
              </div>
            </div>
          </div>
        </div>

        <Alert
          :message="$t('tenant.ai.skillPackage.detail.runtimeTruthHint')"
          type="info"
          show-icon
        />

        <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="rounded-xl border bg-card p-4">
            <div class="text-xs text-muted-foreground">
              {{ $t('tenant.ai.skillPackage.skillCount') }}
            </div>
            <div class="mt-1 text-lg font-semibold text-foreground">
              {{ pkg.skill_count }}
            </div>
          </div>
          <div class="rounded-xl border bg-card p-4">
            <div class="text-xs text-muted-foreground">
              {{ $t('tenant.ai.skillPackage.detail.tools') }}
            </div>
            <div class="mt-1 text-lg font-semibold text-foreground">
              {{ resolvedTools.length }}
            </div>
          </div>
          <div class="rounded-xl border bg-card p-4">
            <div class="text-xs text-muted-foreground">
              {{ $t('tenant.ai.skillPackage.detail.envVars') }}
            </div>
            <div class="mt-1 text-lg font-semibold text-foreground">
              {{ pkg.configured_valves_count }}/{{ pkg.valves_field_count }}
            </div>
          </div>
          <div class="rounded-xl border bg-card p-4">
            <div class="text-xs text-muted-foreground">
              {{ $t('tenant.ai.skillPackage.detail.updatedAt') }}
            </div>
            <div class="mt-1 text-sm font-semibold text-foreground">
              {{ formatRelativeTime(pkg.updated_at) }}
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1fr]">
          <div class="rounded-xl border bg-card p-5">
            <div class="mb-4 text-sm font-semibold text-foreground">
              {{ $t('tenant.ai.skillPackage.detail.basicInfo') }}
            </div>
            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div class="rounded-lg border bg-accent/20 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.skillPackage.sourceSummary') }}
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ getSourceSummaryText(pkg.source_summary, pkg.source_plugin) }}
                </div>
              </div>
              <div class="rounded-lg border bg-accent/20 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.skillPackage.runtimeBinding') }}
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
                </div>
              </div>
              <div class="rounded-lg border bg-accent/20 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.skillPackage.isActive') }}
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ getPackageStatusText(pkg.is_active) }}
                </div>
              </div>
              <div class="rounded-lg border bg-accent/20 px-4 py-3">
                <div class="text-xs text-muted-foreground">
                  {{ $t('common.createdAt') }}
                </div>
                <div class="mt-1 text-sm font-medium text-foreground">
                  {{ formatRelativeTime(pkg.created_at) }}
                </div>
              </div>
            </div>
          </div>

          <div class="rounded-xl border bg-card p-5">
            <div class="mb-4 text-sm font-semibold text-foreground">
              {{ $t('tenant.ai.skillPackage.detail.skills') }}
            </div>
            <Spin :spinning="skillsLoading">
              <div v-if="skills.length === 0" class="py-12">
                <Empty :description="$t('tenant.ai.skillPackage.detail.empty')" />
              </div>
              <div v-else class="flex flex-col gap-3">
                <div
                  v-for="skill in skills"
                  :key="skill.id"
                  class="rounded-xl border bg-accent/20 p-4"
                >
                  <div class="flex items-start gap-3">
                    <div
                      class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                    >
                      <IconifyIcon
                        :icon="skill.avatar || getSkillTypeIcon(skill.type)"
                        class="size-5 text-primary"
                      />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="truncate text-sm font-semibold text-foreground">
                          {{ skill.name }}
                        </span>
                        <Tag :color="getSkillTypeColor(skill.type)" class="!mr-0 !text-[11px]">
                          {{ getSkillTypeText(skill.type) }}
                        </Tag>
                        <Tag v-if="skill.source_plugin" color="geekblue" class="!mr-0 !text-[11px]">
                          {{ skill.source_plugin }}
                        </Tag>
                      </div>
                      <p class="mt-2 text-sm text-muted-foreground">
                        {{
                          skill.description ||
                          $t('tenant.ai.skillPackage.detail.noDescription')
                        }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </Spin>
          </div>
        </div>

        <div class="rounded-xl border bg-card p-5">
          <div class="mb-4 text-sm font-semibold text-foreground">
            {{ $t('tenant.ai.skillPackage.detail.tools') }}
          </div>
          <Spin :spinning="toolsLoading">
            <div v-if="resolvedTools.length === 0" class="py-12">
              <Empty :description="$t('tenant.ai.skillPackage.detail.noTools')" />
            </div>
            <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <div
                v-for="tool in resolvedTools"
                :key="tool.name"
                class="rounded-xl border bg-accent/20 p-4"
              >
                <div class="flex items-start gap-3">
                  <div
                    class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
                  >
                    <IconifyIcon
                      :icon="getSkillTypeIcon(tool.tool_type || 'toolkit')"
                      class="size-5 text-primary"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="font-mono text-sm font-semibold text-foreground">
                        {{ tool.name }}
                      </span>
                      <Tag
                        :color="getToolTypeColor(tool.tool_type)"
                        class="!mr-0 !text-[11px]"
                      >
                        {{ getToolTypeText(tool.tool_type) }}
                      </Tag>
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">
                      {{
                        tool.description ||
                        $t('tenant.ai.skillPackage.detail.noDescription')
                      }}
                    </p>
                    <div class="mt-3 text-xs text-muted-foreground">
                      {{ $t('tenant.ai.skillPackage.detail.skillName') }}:
                      {{ tool.source_skill_name }}
                    </div>
                    <div class="mt-1 text-xs text-muted-foreground">
                      {{ $t('tenant.ai.skillPackage.detail.toolParams') }}:
                      {{ tool.parameters.length }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Spin>
        </div>
      </div>
    </Spin>
  </Page>
</template>
