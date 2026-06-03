<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';

import { useSkillPackageDetailContext } from './detail-context';

const {
  focusTab,
  getPackageRoleColor,
  getPackageRoleText,
  getPackageStatusColor,
  getPackageStatusText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
  getToolTypeColor,
  getToolTypeIcon,
  getToolTypeText,
  hasValves,
  overviewStats,
  pkg,
  resolvedTools,
  valveSummaryStats,
} = useSkillPackageDetailContext();
</script>

<template>
  <div v-if="pkg" class="flex flex-col gap-5 p-5 pt-3">
    <Alert
      :message="$t('admin.ai.skillPackage.detail.runtimeTruthHint')"
      type="info"
      show-icon
    />

    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div
        v-for="stat in overviewStats"
        :key="stat.labelKey"
        class="rounded-xl border bg-accent/30 p-4"
      >
        <div class="mb-1.5 flex items-center gap-1.5">
          <IconifyIcon
            :icon="stat.icon"
            class="size-3.5 text-muted-foreground"
          />
          <span class="text-xs text-muted-foreground">
            {{ $t(stat.labelKey) }}
          </span>
        </div>
        <div :class="stat.valueClass">
          {{ stat.value }}
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
          <div class="rounded-lg border bg-background px-4 py-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">
              {{ $t('admin.ai.skillPackage.description') }}
            </div>
            <div class="mt-1 text-sm leading-relaxed text-foreground">
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
                :color="getRuntimeBindingModeColor(pkg.runtime_binding_mode)"
                class="!mr-0 !text-xs"
              >
                {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
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
              {{ getSourceSummaryText(pkg.source_summary, pkg.source_plugin) }}
            </div>
          </div>

          <div class="rounded-lg border bg-background px-4 py-3">
            <div class="text-xs text-muted-foreground">
              {{ $t('admin.ai.skillPackage.detail.tenantName') }}
            </div>
            <div class="mt-1 text-sm font-medium text-foreground">
              {{
                pkg.tenant_id === null
                  ? $t('admin.ai.skillPackage.detail.platformManaged')
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

          <div class="rounded-lg border bg-background px-4 py-3 md:col-span-2">
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
            <Button size="small" type="link" @click="focusTab('tools')">
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
                    <span class="truncate font-mono text-sm font-semibold">
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
            <div
              v-for="stat in valveSummaryStats"
              :key="stat.labelKey"
              class="rounded-lg border bg-background px-4 py-3"
            >
              <div class="text-xs text-muted-foreground">
                {{ $t(stat.labelKey) }}
              </div>
              <div class="mt-1 text-lg font-semibold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
