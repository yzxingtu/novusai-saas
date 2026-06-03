<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Button, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import { useSkillPackageDetailContext } from './detail-context';

const {
  focusTab,
  getPackageHeroClass,
  getPackageIcon,
  getPackageRoleColor,
  getPackageRoleText,
  getPackageStatusColor,
  getPackageStatusText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
  goBack,
  hasValves,
  openWorkspace,
  pkg,
} = useSkillPackageDetailContext();
</script>

<template>
  <div
    v-if="pkg"
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
          :class="getPackageHeroClass(pkg)"
        >
          <IconifyIcon :icon="getPackageIcon(pkg.avatar)" class="size-8" />
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
              :color="getRuntimeBindingModeColor(pkg.runtime_binding_mode)"
              class="!mr-0 !text-xs"
            >
              {{ getRuntimeBindingModeText(pkg.runtime_binding_mode) }}
            </Tag>
            <Tag v-if="pkg.is_recommended" color="gold" class="!mr-0 !text-xs">
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
              {{ getSourceSummaryText(pkg.source_summary, pkg.source_plugin) }}
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
</template>
